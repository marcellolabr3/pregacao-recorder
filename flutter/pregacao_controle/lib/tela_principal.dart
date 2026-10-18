// Tela unica de controle (paridade com o app Android original).
//
// Ela apenas EXIBE o estado que chega por MQTT e envia dois comandos
// (START/STOP). Nada de audio e gravado aqui: o celular observa o
// equipamento, nao substitui ele.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'configuracao.dart';
import 'main.dart';
import 'mqtt_controlador.dart';
import 'protocolo.dart';
import 'tela_configuracoes.dart';

class TelaPrincipal extends StatefulWidget {
  const TelaPrincipal({super.key});

  @override
  State<TelaPrincipal> createState() => _TelaPrincipalState();
}

class _TelaPrincipalState extends State<TelaPrincipal>
    with WidgetsBindingObserver {
  late MqttControlador mqtt;
  bool _inicializado = false;
  Timer? _ticker;
  String _versao = '';
  bool _aguardandoAck = false;
  bool _enviandoComando = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) => setState(() {}));
    PackageInfo.fromPlatform()
        .then((info) {
          if (mounted) setState(() => _versao = info.version);
        })
        .catchError((_) {
          // canal nativo indisponivel (teste/ambiente estranho): segue sem
          // a versao na barra, sem quebrar a tela
        });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // o contexto so pode ser lido aqui (e nao no initState); roda uma vez
    if (!_inicializado) {
      _inicializado = true;
      mqtt = AppScope.of(context);
      if (mqtt.cfg.pronto && !mqtt.conectadoBroker) mqtt.conectar();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // a conexao nao precisa ficar viva em segundo plano (economia de
    // bateria); ao voltar, o proprio app reconecta sozinho
    if (state == AppLifecycleState.resumed) {
      if (mqtt.cfg.pronto && !mqtt.conectadoBroker) mqtt.conectar();
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      mqtt.desconectar();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _ticker?.cancel();
    super.dispose();
  }

  // ------------------------------------------------------------------
  // render
  // ------------------------------------------------------------------
  @override
  Widget build(BuildContext context) {
    final cfg = mqtt.cfg;
    final estado = mqtt.estado;
    final ligado = mqtt.conectadoBroker && mqtt.equipamentoOnline;

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(cfg.aparelho, style: const TextStyle(fontSize: 18)),
            if (_versao.isNotEmpty)
              Text('v$_versao', style: const TextStyle(fontSize: 12)),
          ],
        ),
        actions: [_menu()],
      ),
      body: !cfg.pronto ? _semConfiguracao(context) : _conteudo(context, estado, ligado),
    );
  }

  Widget _menu() {
    return PopupMenuButton<String>(
      onSelected: (valor) {
        switch (valor) {
          case 'config':
            _abrirConfiguracoes();
        }
      },
      itemBuilder: (context) => const [
        PopupMenuItem(value: 'config', child: Text('Configuracoes')),
      ],
    );
  }

  /// Sem token ainda: orientacao na propria tela (mesmo criterio do app
  /// Kotlin) - em vez de tentar conectar com credencial vazia.
  Widget _semConfiguracao(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.settings_remote, size: 56),
            const SizedBox(height: 16),
            const Text(
              'Configure o acesso ao equipamento para comecar.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 8),
            const Text(
              'Os dados do servico remoto ja vem preenchidos: voce digita '
              'so o token (esta no painel do equipamento, cartao '
              'CONTROLE REMOTO).',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 13, color: Colors.grey),
            ),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: _abrirConfiguracoes,
              child: const Text('ABRIR CONFIGURACOES'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _conteudo(
      BuildContext context, EstadoEquipamento? estado, bool ligado) {
    final st = estado;
    final state = st?.state ?? '';
    final banner = st?.banner ?? '';

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // conexao + estado
        // DOIS indicadores distintos (criterio de diagnostico):
        //  - BROKER: o celular fala com o EMQX?
        //  - PC: o equipamento da igreja esta disponivel (avail retido)?
        // Assim "PC OFF" com "BROKER OK" = problema e' do PC, nao do celular.
        Row(
          children: [
            _badge(mqtt.conectadoBroker ? 'BROKER OK' : 'BROKER OFF',
                mqtt.conectadoBroker ? Colors.green : Colors.red),
            const SizedBox(width: 8),
            _badge(
                mqtt.equipamentoOnline ? 'PC ONLINE' : 'PC OFF',
                mqtt.equipamentoOnline
                    ? Colors.green
                    : (mqtt.conectadoBroker ? Colors.orange : Colors.red)),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                rotuloDe(state, banner),
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.right,
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: _cor(tomDe(state, banner)),
                ),
              ),
            ),
          ],
        ),
        // etapa da conexao em curso (diagnostico ao vivo); em falha a
        // causa tecnica aparece na mensagem vermelha abaixo
        if (!ligado &&
            mqtt.fase != FaseConexao.parado &&
            mqtt.fase != FaseConexao.erro)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              mqtt.rotuloFase,
              style: const TextStyle(fontSize: 12, color: Colors.orange),
            ),
          ),
        if (st != null && st.detail.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(st.detail,
                style: const TextStyle(fontSize: 13, color: Colors.grey)),
          ),
        const SizedBox(height: 12),

        // tempo de gravacao (calculado do started_at, como no app original)
        Text(
          formatarTempo(_decorrido(st)),
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 44,
            fontWeight: FontWeight.w300,
            color: state == 'RECORDING' ? Colors.red : Colors.grey,
          ),
        ),
        const SizedBox(height: 8),

        // botao de acao
        FilledButton(
          style: FilledButton.styleFrom(
            padding: const EdgeInsets.symmetric(vertical: 14),
            backgroundColor:
                state == 'RECORDING' ? Colors.red : Colors.indigo,
          ),
          onPressed: _acaoHabilitada(state, ligado) && !_aguardandoAck
              ? _aoApertarAcao
              : null,
          child: Text(_rotuloBotao(state, ligado),
              style: const TextStyle(fontSize: 16)),
        ),
        const SizedBox(height: 12),

        // upload
        Row(
          children: [
            Text(_uploadTexto(st),
                style: TextStyle(fontSize: 14, color: _corUpload(st))),
            if (st != null && st.uploadRunning > 0) ...[
              const SizedBox(width: 12),
              const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ],
          ],
        ),

        // arquivo
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(
            mqtt.nomeArquivo.isEmpty ? 'Nenhuma gravacao ainda' : mqtt.nomeArquivo,
            style: const TextStyle(fontSize: 13, color: Colors.grey),
          ),
        ),

        // mensagem (erros, detalhes de ack)
        if (mqtt.ultimaMensagem.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Text(mqtt.ultimaMensagem,
                style: const TextStyle(fontSize: 13, color: Colors.red)),
          ),

        const SizedBox(height: 16),
        const Text('Eventos',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 4),
        if (mqtt.eventos.isEmpty)
          const Text('-', style: TextStyle(color: Colors.grey))
        else
          ...mqtt.eventos.map((linha) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 1),
                child: Text(linha,
                    style: const TextStyle(fontSize: 12, color: Colors.grey)),
              )),
      ],
    );
  }

  // ------------------------------------------------------------------
  // acoes
  // ------------------------------------------------------------------
  void _aoApertarAcao() {
    final state = mqtt.estado?.state ?? '';
    if (state == 'IDLE' || state == 'COMPLETED' || state == 'ERROR') {
      _enviar('START');
    } else if (state == 'RECORDING') {
      showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Encerrar gravacao?'),
          content: const Text(
              'A gravacao sera finalizada e o arquivo comecara a ser salvo.'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('CANCELAR'),
            ),
            FilledButton(
              onPressed: () {
                Navigator.pop(context);
                _enviar('STOP');
              },
              child: const Text('ENCERRAR'),
            ),
          ],
        ),
      );
    }
  }

  Future<void> _enviar(String cmd) async {
    setState(() {
      _aguardandoAck = true;
      _enviandoComando = true;
    });
    final ack = await mqtt.executar(cmd);
    if (!mounted) return;
    setState(() {
      _aguardandoAck = false;
      _enviandoComando = false;
      if (!ack.ok) {
        mqtt.ultimaMensagem =
            ack.error.isEmpty ? 'resposta sem detalhe' : ack.error;
      } else if (ack.detail.isNotEmpty) {
        mqtt.ultimaMensagem = ack.detail;
      } else {
        mqtt.ultimaMensagem = '';
      }
    });
    // o estado novo chega pelo proprio MQTT em seguida e atualiza a tela
  }

  Future<void> _abrirConfiguracoes() async {
    final nova = await Navigator.push<Configuracao>(
      context,
      MaterialPageRoute(builder: (_) => TelaConfiguracoes(atual: mqtt.cfg)),
    );
    if (nova != null && mounted) {
      mqtt.aplicarConfiguracao(nova);
      setState(() {});
    }
  }

  // ------------------------------------------------------------------
  // helpers de apresentacao
  // ------------------------------------------------------------------
  Duration _decorrido(EstadoEquipamento? st) {
    if (st == null || st.state != 'RECORDING' || st.startedAt <= 0) {
      return Duration.zero;
    }
    final agora = DateTime.now().millisecondsSinceEpoch / 1000.0;
    return Duration(seconds: (agora - st.startedAt).clamp(0, 1 << 40).toInt());
  }

  bool _acaoHabilitada(String state, bool ligado) {
    if (!ligado || state.isEmpty || _enviandoComando) return false;
    return state == 'IDLE' || state == 'COMPLETED' || state == 'ERROR' ||
        state == 'RECORDING';
  }

  String _rotuloBotao(String state, bool ligado) {
    if (!ligado) return 'INICIAR GRAVACAO';
    if (state == 'RECORDING') return 'ENCERRAR GRAVACAO';
    if (state == 'FINALIZING' ||
        state == 'UPLOADING' ||
        state == 'UPLOAD_PENDING' ||
        state == 'RECOVERY_REQUIRED') {
      return 'AGUARDE...';
    }
    return 'INICIAR GRAVACAO';
  }

  String _uploadTexto(EstadoEquipamento? st) {
    if (st == null) return 'Envio ao Drive: -';
    if (st.uploadRunning > 0) return 'ENVIANDO';
    if (st.uploadPending > 0) return 'PENDENTE (${st.uploadPending})';
    if (st.uploadFailed > 0) return 'FALHOU (${st.uploadFailed})';
    if (st.uploadDone > 0) return 'ENVIADO';
    return 'Envio ao Drive: -';
  }

  Color _corUpload(EstadoEquipamento? st) {
    if (st == null) return Colors.grey;
    if (st.uploadRunning > 0) return Colors.blue;
    if (st.uploadPending > 0) return Colors.orange;
    if (st.uploadFailed > 0) return Colors.red;
    if (st.uploadDone > 0) return Colors.green;
    return Colors.grey;
  }

  Widget _badge(String texto, Color cor) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: cor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(texto,
          style: const TextStyle(color: Colors.white, fontSize: 12)),
    );
  }

  Color _cor(TomEstado tom) {
    switch (tom) {
      case TomEstado.gravando:
        return Colors.red;
      case TomEstado.pronto:
        return Colors.green;
      case TomEstado.atencao:
        return Colors.orange;
      case TomEstado.enviando:
        return Colors.blue;
      case TomEstado.enviado:
        return Colors.teal;
      case TomEstado.fraco:
        return Colors.grey;
    }
  }
}
