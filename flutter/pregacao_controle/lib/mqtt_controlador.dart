// Ponte MQTT com o equipamento (o mesmo protocolo do agente: docs/AGENTE.md).
//
// O app e apenas um observador com botoes: assina
// `pregacao/<id>/{avail,state,events,ack}` e publica em `pregacao/<id>/cmd`.
// Audio nunca trafega por aqui.
//
// Reconexao automatica e feita pelo proprio cliente (autoReconnect): se a
// Internet do celular cair e voltar, a tela volta a atualizar sozinha.
// O "ts" enviado em cada comando e o prazo de validade conferido pelo agente
// (COMANDO_TTL_SEGUNDOS la do outro lado); o ack sem resposta em
// `ackTimeoutSegundos` avisa o operador em vez de deixar o botao morto.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';
import 'package:typed_data/typed_data.dart';

import 'configuracao.dart';
import 'protocolo.dart';

/// Etapas da conexao, expostas ao operador para diagnosticar SEM adivinhar:
/// resolver DNS -> TCP -> TLS + autenticacao MQTT -> conectado. Cada falha
/// mostra a etapa e o motivo tecnico (nunca o token).
enum FaseConexao {
  parado,
  resolvendoDns,
  conectandoTcp,
  tlsMqtt,
  conectado,
  desconectado,
  erro,
}

class MqttControlador extends ChangeNotifier {
  MqttControlador(this.cfg) {
    // Vigia de rede: se por QUALQUER motivo (troca Wi-Fi<->4G, app
    // voltando do fundo, queda silenciosa do socket) o app ficar 30 s
    // sem conexao e sem tentativa em andamento, recomeca o ciclo sozinho.
    _vigia = Timer.periodic(const Duration(seconds: 30), (_) {
      if (!cfg.pronto) return;
      if (conectadoBroker || _conectando || _retry != null) return;
      debugPrint('[mqtt] vigia: 30s sem conexao - nova tentativa');
      _desconectarCliente();
      _conectar();
    });
  }

  Configuracao cfg;
  MqttServerClient? _client;

  bool conectadoBroker = false;
  bool equipamentoOnline = false;
  EstadoEquipamento? estado;
  String ultimaMensagem = '';
  String nomeArquivo = '';
  final List<String> eventos = []; // ultimos 6, mais novos primeiro

  final StreamController<Ack> _acks = StreamController<Ack>.broadcast();
  final Map<String, Completer<Ack>> _pendentes = {};

  // Progresso do estudo por job (topic jobs, retido - S3).
  final StreamController<ProgressoJob> _progresso = StreamController<ProgressoJob>.broadcast();
  ProgressoJob? _ultimoProgresso;

  Topicos get topicos => Topicos(cfg.aparelho.trim());

  /// Stream do progresso do estudo (job_progress do agente). O ultimo valor
  /// fica em cache: ao reconectar o broker entrega o retido e a UI pinta
  /// sem esperar o proximo marco.
  Stream<ProgressoJob> get progresso => _progresso.stream;
  ProgressoJob? get ultimoProgresso => _ultimoProgresso;

  /// Acks brutos, para telas que queiram observar (filtro por req_id).
  Stream<Ack> get acks => _acks.stream;

  Timer? _retry;
  int _delayRetry = 5;
  bool _conectando = false; // trava anti-tentativas simultaneas
  bool _assinado = false;   // subscribe feito nesta conexao
  int _geracao = 0;         // invalida tentativa em voo quando a config muda
  Timer? _vigia;

  /// Etapa atual da conexao (para a interface mostrar o progresso).
  FaseConexao fase = FaseConexao.parado;
  String detalheFase = '';

  /// Rotulo legivel da etapa atual, exibido sob o badge.
  String get rotuloFase {
    switch (fase) {
      case FaseConexao.resolvendoDns:
        return 'resolvendo DNS ($detalheFase)...';
      case FaseConexao.conectandoTcp:
        return 'conectando ($detalheFase)...';
      case FaseConexao.tlsMqtt:
        return 'TLS + autenticacao ($detalheFase)...';
      case FaseConexao.conectado:
        return 'conectado ao broker';
      case FaseConexao.desconectado:
        return 'desconectado';
      case FaseConexao.erro:
        return 'falha: $detalheFase';
      case FaseConexao.parado:
        return 'parado';
    }
  }

  /// Liga ao broker com as configuracoes atuais.
  void conectar() {
    if (!cfg.pronto) return;
    _cancelarRetry();
    _desconectarCliente();
    _geracao++; // invalida tentativa em voo, se houver
    _conectando = false;
    _conectar();
  }

  Future<void> _conectar() async {
    if (_conectando) return; // nunca duas tentativas simultaneas
    _conectando = true;
    _assinado = false;
    final geracao = ++_geracao;
    final servidor = cfg.servidor.trim();
    final porta = cfg.porta;

    try {
      // Etapa 1: DNS. Falha aqui NAO e' rede do celular nem token: e' o
      // nome do servidor que nao resolve (caso real: emqx.com em vez de
      // emqxsl.com - o hostname tentado aparece na mensagem).
      _fase(FaseConexao.resolvendoDns, detalhe: servidor);
      InternetAddress alvo;
      try {
        final enderecos = await InternetAddress.lookup(servidor)
            .timeout(const Duration(seconds: 10));
        alvo = enderecos.firstWhere(
          (a) => a.type == InternetAddressType.IPv4,
          orElse: () => enderecos.first,
        );
      } catch (e) {
        _falhou('DNS', "'$servidor': ${_detalheErro(e)}${_dicaDns(servidor)}");
        return;
      }
      if (geracao != _geracao) return; // config mudou no meio da espera

      // Etapa 2: TCP. Prova a porta antes do cliente MQTT para separar
      // "porta bloqueada" de "TLS/autenticacao recusada".
      _fase(FaseConexao.conectandoTcp, detalhe: '${alvo.address}:$porta');
      try {
        final s = await Socket.connect(alvo, porta,
            timeout: const Duration(seconds: 10));
        s.destroy();
      } catch (e) {
        _falhou('TCP ${alvo.address}:$porta', _detalheErro(e));
        return;
      }
      if (geracao != _geracao) return;

      // Etapa 3: TLS + CONNACK. O cliente precisa do NOME (SNI/certificado),
      // por isso a conexao e' feita com o hostname, nao com o IP da sonda.
      _fase(FaseConexao.tlsMqtt, detalhe: servidor);
      final clientId =
          'fl-${DateTime.now().millisecondsSinceEpoch.toRadixString(16)}';
      final client = MqttServerClient.withPort(servidor, clientId, porta);
      client.secure = cfg.tls;
      client.keepAlivePeriod = 60;
      client.connectTimeoutPeriod = 15000; // ms
      // Reconexao interna do pacote DESLIGADA de proposito: todo o
      // ciclo (retry + vigia) e nosso, para mostrar as etapas ao
      // operador e nunca criar clientes duplicados no broker.
      client.autoReconnect = false;
      client.logging(on: false);
      client.onConnected = _aoConectar;
      client.onDisconnected = _aoDesconectar;

      // _client ANTES do connect: no mqtt_client 10.x o onConnected
      // dispara quando o CONNACK chega, ANTES do future resolver -
      // se _client ficasse null ate la, _aoConectar abortava e o
      // SUBSCRIBE NUNCA era enviado (bug real: broker mostrava
      // cliente conectado com 0 inscricoes e o app ficava OFFLINE).
      _client = client;
      try {
        final status =
            await client.connect(cfg.usuario.trim(), cfg.token);
        if (geracao != _geracao) {
          // tentativa invalidada por troca de config/rede no meio
          _client = null;
          try {
            client.disconnect();
          } catch (_) {}
          return;
        }
        if (status?.state != MqttConnectionState.connected) {
          _client = null;
          try {
            client.disconnect();
          } catch (_) {}
          _falhou('MQTT CONNACK',
              '${_traduzirStatus(status)} (codigo: ${status?.returnCode})');
          return;
        }
        _cancelarRetry();
        _delayRetry = 5;
        _assinar(client); // idempotente: o callback pode ja ter assinado
        _fase(FaseConexao.conectado);
        client.updates?.listen(_aoReceber, onError: (Object e) {
          _avisar('falha no fluxo MQTT: $e');
        });
      } catch (e) {
        if (geracao != _geracao) return;
        _client = null;
        try {
          client.disconnect();
        } catch (_) {}
        _falhou('TLS/MQTT', _traduzirExcecao(e));
      }
    } finally {
      if (geracao == _geracao) _conectando = false;
    }
  }

  /// Assina os topicos do equipamento (idempotente). Feita TANTO pelo
  /// callback onConnected quanto pelo caminho de sucesso do connect:
  /// qualquer uma das duas vias garante o SUBSCRIBE.
  void _assinar(MqttServerClient client) {
    if (_assinado) return;
    _assinado = true;
    for (final t in [
      topicos.avail,
      topicos.state,
      topicos.ack,
      topicos.events,
      topicos.jobs, // S3: progresso do estudo por job (retido)
    ]) {
      try {
        final r = client.subscribe(t, MqttQos.atLeastOnce);
        debugPrint('[mqtt] SUBSCRIBE $t -> $r');
      } catch (e) {
        debugPrint('[mqtt] SUBSCRIBE $t FALHOU: $e');
        _assinado = false;
      }
    }
  }

  void _fase(FaseConexao nova, {String detalhe = ''}) {
    fase = nova;
    detalheFase = detalhe;
    // log sem credenciais: so etapa, host e motivo (adb logcat / flutter)
    debugPrint(
        '[mqtt] fase=${nova.name}${detalhe.isEmpty ? '' : ' ($detalhe)'}');
    notifyListeners();
  }

  /// Falha em qualquer etapa: mostra a causa tecnica (sem token) e
  /// reagenda nova tentativa.
  void _falhou(String etapa, String motivo) {
    _fase(FaseConexao.erro, detalhe: '$etapa: $motivo');
    _avisar('Falha na etapa $etapa: $motivo');
    _agendarRetry();
  }

  /// SocketException vem com preenchimento; corta o que nao ajuda.
  String _detalheErro(Object e) =>
      e.toString().replaceFirst('SocketException: ', '');

  /// Dica para o erro classico do EMQX (usuario digita emqx.com e o
  /// dominio real termina em emqxsl.com).
  String _dicaDns(String servidor) {
    if (servidor.endsWith('.emqx.com')) {
      return '  [dica: o dominio do EMQX Cloud termina em .emqxsl.com]';
    }
    return '';
  }

  /// Falhou conectar (rede fraca, DNS devolvendo IP ruim, senha ainda sendo
  /// trocada no EMQX...): retenta sozinho com espera que cresce ate 30 s.
  /// Cada tentativa resolve o DNS de novo - se o broker devolver um endereco
  /// ruim, a proxima chance costuma vir boa (autoReconnect do cliente so
  /// cobre apos a primeira conexao bem-sucedida).
  void _agendarRetry() {
    if (!cfg.pronto) return;
    _retry?.cancel();
    final espera = _delayRetry;
    _delayRetry = _delayRetry < 30 ? _delayRetry + 5 : 30;
    final base =
        ultimaMensagem.isEmpty ? 'conexao interrompida' : ultimaMensagem;
    ultimaMensagem = '$base (nova tentativa em ${espera}s)';
    notifyListeners();
    _retry = Timer(Duration(seconds: espera), () {
      _retry = null;
      if (!cfg.pronto) return;
      _desconectarCliente();
      _conectar();
    });
  }

  void _cancelarRetry() {
    _retry?.cancel();
    _retry = null;
  }

  void _aoConectar() {
    final client = _client;
    if (client == null) return;
    conectadoBroker = true;
    _assinar(client); // SUBSCRIBE aqui mesmo - nao depende do future
    // assinatura confirmada: limpa avisos de conexao antigos
    ultimaMensagem = '';
    _fase(FaseConexao.conectado);
  }

  void _aoDesconectar() {
    conectadoBroker = false;
    equipamentoOnline = false;
    // se _client ja e' null, a desconexao foi nossa (intencional);
    // caso contrario o broker/rede derrubou e o retry entra na frente
    final foiIntencional = _client == null;
    _fase(FaseConexao.desconectado);
    if (!foiIntencional) {
      debugPrint('[mqtt] conexao perdida - retentando');
      _agendarRetry();
    }
  }

  void _aoReceber(List<MqttReceivedMessage<MqttMessage>> mensagens) {
    for (final recebida in mensagens) {
      final topico = recebida.topic;
      final msg = recebida.payload;
      if (msg is! MqttPublishMessage) continue;
      debugPrint('[mqtt] recebido: $topico'); // sem payload: so o caminho
      final texto = utf8.decode(msg.payload.message);
      try {
        if (topico == topicos.avail) {
          equipamentoOnline = texto.trim() == 'online';
          notifyListeners();
        } else if (topico == topicos.state) {
          final dados = jsonDecode(texto);
          if (dados is Map<String, dynamic>) {
            estado = EstadoEquipamento.fromJson(dados);
            notifyListeners();
          }
        } else if (topico == topicos.ack) {
          final dados = jsonDecode(texto);
          if (dados is Map<String, dynamic>) {
            final ack = Ack.fromJson(dados);
            _acks.add(ack);
            final pendente = _pendentes.remove(ack.reqId);
            if (pendente != null && !pendente.isCompleted) {
              pendente.complete(ack);
            }
          }
        } else if (topico == topicos.events) {
          final dados = jsonDecode(texto);
          if (dados is Map<String, dynamic>) {
            _aoEvento(EventoSistema.fromJson(dados));
          }
        } else if (topico == topicos.jobs) {
          if (texto.isEmpty) {
            _ultimoProgresso = null;
            notifyListeners();
            continue;
          }
          // S3: progresso do estudo por job (payload ja e o payload do
          // job_progress - o agente repassa o que o app emite via SSE).
          final dados = jsonDecode(texto);
          if (dados is Map<String, dynamic>) {
            final pj = ProgressoJob.fromJson(dados);
            _ultimoProgresso = pj;
            _progresso.add(pj);
            notifyListeners();
          }
        }
      } catch (_) {
        // payload fora do contrato: ignora em vez de derrubar o app
      }
    }
  }

  void _aoEvento(EventoSistema evento) {
    if (evento.kind == 'gravacao_pronta' && evento.path.isNotEmpty) {
      final nome = evento.path
          .replaceAll('\\', '/')
          .split('/')
          .last;
      if (nome.isNotEmpty) nomeArquivo = nome;
    }
    final agora = DateTime.now();
    final rotulo = '${agora.hour.toString().padLeft(2, '0')}:'
        '${agora.minute.toString().padLeft(2, '0')}  '
        '${evento.kind.isEmpty ? "evento" : evento.kind}  ${evento.message}';
    eventos.insert(0, rotulo.trimRight());
    while (eventos.length > 6) {
      eventos.removeLast();
    }
    notifyListeners();
  }

  // ------------------------------------------------------------------
  // comandos
  // ------------------------------------------------------------------

  /// Envia um comando e espera o ack correlacionado pelo req_id. Se a
  /// resposta nao chegar no prazo, devolve um ack de falha (o operador nunca
  /// fica sem retorno).
  Future<Ack> executar(String cmd, {Map<String, String> extras = const {}}) {
    final payload = montarComando(cmd, extras: extras);
    final reqId = payload['req_id'] as String;
    final client = _client;
    if (client == null || !conectadoBroker) {
      _avisar('sem conexao com o equipamento');
      return Future.value(
          const Ack(ok: false, error: 'sem conexao com o equipamento'));
    }
    final completer = Completer<Ack>();
    _pendentes[reqId] = completer;
    Timer(const Duration(seconds: ackTimeoutSegundos), () {
      final pendente = _pendentes.remove(reqId);
      if (pendente != null && !pendente.isCompleted) {
        pendente.complete(Ack(
            ok: false,
            cmd: cmd,
            reqId: reqId,
            error: 'sem resposta do equipamento'));
      }
    });
    try {
      final dados = Uint8Buffer();
      dados.addAll(utf8.encode(jsonEncode(payload)));
      // comandos NUNCA sao retidos (roteiro: comunicacao)
      client.publishMessage(topicos.cmd, MqttQos.atLeastOnce, dados,
          retain: false);
    } catch (e) {
      _pendentes.remove(reqId);
      if (!completer.isCompleted) {
        completer.complete(Ack(
            ok: false,
            cmd: cmd,
            reqId: reqId,
            error: 'falha ao enviar: $e'));
      }
    }
    return completer.future;
  }

  // ------------------------------------------------------------------
  // utilidades
  // ------------------------------------------------------------------
  void _avisar(String texto) {
    ultimaMensagem = texto;
    notifyListeners();
  }

  /// Traduz a recusa do broker em frase utilizavel: a causa quase sempre e o
  /// token, nao a rede (mesmo criterio do app Kotlin).
  String _traduzirStatus(MqttClientConnectionStatus? status) {
    final codigo = status?.returnCode;
    final texto = codigo?.toString().toLowerCase() ?? '';
    if (texto.contains('notauthorized') || texto.contains('baduser')) {
      return msgCredencial;
    }
    if (texto.isNotEmpty && !texto.contains('accepted')) {
      return 'Conexao recusada ($codigo). Confira o token em Configuracoes.';
    }
    return 'Sem conexao com o servidor. Verifique a Internet do celular.';
  }

  String _traduzirExcecao(Object e) {
    final texto = e.toString().toLowerCase();
    const palavrasCredencial = [
      'not authorized', 'authoriz', 'autoriz', 'bad user',
      'authentication', 'autentic', 'password', 'senha',
    ];
    if (palavrasCredencial.any(texto.contains)) return msgCredencial;
    const palavrasRede = [
      'timeout', 'timed out', 'unreachable', 'inacess',
      'unable to connect', 'network', 'rede',
    ];
    if (palavrasRede.any(texto.contains)) return msgRede;
    return 'Falha ao conectar: $e';
  }

  /// Troca as configuracoes (apos Configuracoes) e reconecta.
  void aplicarConfiguracao(Configuracao nova) {
    cfg = nova;
    notifyListeners();
    if (nova.pronto) {
      conectar();
    } else {
      _desconectarCliente();
    }
  }

  void desconectar() {
    _cancelarRetry();
    _desconectarCliente();
  }

  void _desconectarCliente() {
    final client = _client;
    _client = null;
    conectadoBroker = false;
    equipamentoOnline = false;
    fase = FaseConexao.desconectado;
    detalheFase = '';
    _assinado = false;
    if (client != null) {
      try {
        client.disconnect();
      } catch (_) {
        // conexao ja caiu
      }
    }
  }

  @override
  void dispose() {
    _vigia?.cancel();
    _cancelarRetry();
    _desconectarCliente();
    _acks.close();
    super.dispose();
  }
}

const msgCredencial =
    'Broker recusou o usuario/token. Confira em Configuracoes: '
    "usuario 'operador' + token do painel.";
const msgRede =
    'Sem conexao com o servidor. Verifique a Internet do celular.';
