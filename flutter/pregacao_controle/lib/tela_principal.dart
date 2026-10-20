// Tela unica de controle (paridade com o app Android original).
//
// Exibe o estado que chega por MQTT, controla a gravacao e permite manter
// a programacao do PC. O audio continua sendo gravado no equipamento.
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
  bool _mostrarTodasPregacoes = false;

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

        // ===== PROGRESSO DO ESTUDO (S3) =====
        // Lido do topic "jobs" retido: o APK que reconectar ve o progresso
        // atual sem reiniciar nada. Cada etapa so avanca com marco REAL
        // (o agente republica so o que o app emite via SSE job_progress).
        _progressoWidget(mqtt),

        _programacaoWidget(mqtt),

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

  // ------------------------------------------------------------------
  // progresso do estudo (S3)
  // ------------------------------------------------------------------
  Widget _progressoWidget(MqttControlador mqtt) {
    final pj = mqtt.ultimoProgresso;
    if (pj == null) return const SizedBox.shrink();

    // Percentual vem do agente (ja honesto: so marco concluido).
    // A UI so espelha - nada de estimar por tempo.
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'PROGRESSO DO ESTUDO',
            style: TextStyle(
                fontWeight: FontWeight.bold, fontSize: 12, color: Colors.grey),
          ),
          const SizedBox(height: 6),
          LinearProgressIndicator(
            value: pj.percentual / 100,
            minHeight: 8,
            backgroundColor: Colors.grey[800],
            valueColor: AlwaysStoppedAnimation<Color>(_corProgresso(pj)),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Text('${pj.percentual}%  ',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
              Expanded(
                child: Text(
                  pj.descricao.isNotEmpty ? pj.descricao : pj.rotuloEtapa,
                  style: const TextStyle(fontSize: 13, color: Colors.grey),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (pj.motivo.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: Text(
                    pj.motivo,
                    style: const TextStyle(fontSize: 11, color: Colors.orange),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _programacaoWidget(MqttControlador mqtt) {
    final itens = mqtt.pregacoes;
    final visiveis = _mostrarTodasPregacoes ? itens : itens.take(3).toList();
    return Card(
      margin: const EdgeInsets.only(top: 16),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text('PROGRAMACAO DE PREGACOES',
                      style: TextStyle(fontWeight: FontWeight.bold)),
                ),
                IconButton(
                  tooltip: 'Nova pregacao',
                  onPressed: mqtt.equipamentoOnline
                      ? () => _editarPregacao(null)
                      : null,
                  icon: const Icon(Icons.add_circle_outline),
                ),
                IconButton(
                  tooltip: 'Atualizar programacao',
                  onPressed: mqtt.equipamentoOnline && !mqtt.carregandoPregacoes
                      ? mqtt.carregarPregacoes
                      : null,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            if (mqtt.carregandoPregacoes) const LinearProgressIndicator(),
            if (mqtt.erroPregacoes.isNotEmpty)
              Text(mqtt.erroPregacoes,
                  style: const TextStyle(color: Colors.red)),
            if (itens.isEmpty && !mqtt.carregandoPregacoes && mqtt.erroPregacoes.isEmpty)
              Text(mqtt.equipamentoOnline
                  ? 'Nenhuma pregacao cadastrada'
                  : 'Conecte ao PC para consultar a programacao'),
            for (final p in visiveis)
              ListTile(
                contentPadding: EdgeInsets.zero,
                dense: true,
                title: Text('${p.data} ${p.horario}  ${p.pregador}'),
                subtitle: Text([
                  p.igreja,
                  if (p.tema.isNotEmpty) p.tema,
                  if (p.textoBase.isNotEmpty) p.textoBase,
                ].join(' - ')),
                trailing: mqtt.equipamentoOnline
                    ? PopupMenuButton<String>(
                        tooltip: 'Opcoes da pregacao',
                        onSelected: (acao) {
                          if (acao == 'editar') _editarPregacao(p);
                          if (acao == 'excluir') _excluirPregacao(p);
                        },
                        itemBuilder: (context) => const [
                          PopupMenuItem(value: 'editar', child: Text('EDITAR')),
                          PopupMenuItem(value: 'excluir', child: Text('EXCLUIR')),
                        ],
                      )
                    : null,
              ),
            if (itens.length > 3)
              TextButton(
                onPressed: () => setState(
                    () => _mostrarTodasPregacoes = !_mostrarTodasPregacoes),
                child: Text(_mostrarTodasPregacoes
                    ? 'MOSTRAR MENOS'
                    : (mqtt.totalPregacoes > itens.length
                        ? 'VER ${itens.length} DE ${mqtt.totalPregacoes}'
                        : 'VER TODAS (${itens.length})')),
              ),
            if (!mqtt.equipamentoOnline)
              const Text('PC offline: exibindo a ultima programacao recebida',
                  style: TextStyle(color: Colors.grey, fontSize: 12)),
          ],
        ),
      ),
    );
  }

  Future<void> _editarPregacao(Pregacao? atual) async {
    final resultado = await showDialog<String>(
      context: context,
      builder: (context) => _DialogoPregacao(mqtt: mqtt, atual: atual),
    );
    if (!mounted || resultado == null) return;
    await mqtt.carregarPregacoes();
    if (!mounted) return;
    final mensagem = resultado == 'ok'
        ? 'Programacao salva'
        : 'Outro aparelho alterou esta programacao. Confira a lista atualizada.';
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(mensagem)));
  }

  Future<void> _excluirPregacao(Pregacao p) async {
    final confirmado = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Excluir pregacao?'),
        content: Text('${p.data} ${p.horario}  ${p.pregador}'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('CANCELAR'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('EXCLUIR'),
          ),
        ],
      ),
    );
    if (confirmado != true || !mounted) return;
    final resposta = await mqtt.executar(ComandoPregacao.deletar.valor,
        extras: {'id': '${p.id}', 'versao': '${p.versao}'});
    if (!mounted) return;
    await mqtt.carregarPregacoes();
    if (!mounted) return;
    final mensagem = resposta.ok
        ? 'Pregacao excluida'
        : (resposta.error.isEmpty ? 'Nao foi possivel excluir' : resposta.error);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(mensagem)));
  }

  Color _corProgresso(ProgressoJob pj) {
    if (pj.falhou) return Colors.red;
    if (pj.emEspera) return Colors.orange;
    if (pj.concluido) return Colors.green;
    return Colors.blue;
  }
}

class _DialogoPregacao extends StatefulWidget {
  final MqttControlador mqtt;
  final Pregacao? atual;

  const _DialogoPregacao({required this.mqtt, this.atual});

  @override
  State<_DialogoPregacao> createState() => _DialogoPregacaoState();
}

class _DialogoPregacaoState extends State<_DialogoPregacao> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _data;
  late final TextEditingController _horario;
  late final TextEditingController _pregador;
  late final TextEditingController _igreja;
  late final TextEditingController _textoBase;
  late final TextEditingController _tema;
  bool _salvando = false;
  String _erro = '';

  @override
  void initState() {
    super.initState();
    final atual = widget.atual;
    final hoje = DateTime.now();
    _data = TextEditingController(text: atual?.data ?? _formatarData(hoje));
    _horario = TextEditingController(text: atual?.horario ?? '19:00');
    _pregador = TextEditingController(text: atual?.pregador ?? '');
    _igreja = TextEditingController(text: atual?.igreja ?? '');
    _textoBase = TextEditingController(text: atual?.textoBase ?? '');
    _tema = TextEditingController(text: atual?.tema ?? '');
  }

  @override
  void dispose() {
    for (final c in [_data, _horario, _pregador, _igreja, _textoBase, _tema]) {
      c.dispose();
    }
    super.dispose();
  }

  static String _formatarData(DateTime data) =>
      '${data.year.toString().padLeft(4, '0')}-'
      '${data.month.toString().padLeft(2, '0')}-'
      '${data.day.toString().padLeft(2, '0')}';

  Future<void> _escolherData() async {
    final informada = DateTime.tryParse(_data.text);
    final inicial = informada != null &&
            !informada.isBefore(DateTime(1900)) &&
            !informada.isAfter(DateTime(2200))
        ? informada
        : DateTime.now();
    final escolha = await showDatePicker(
      context: context,
      initialDate: inicial,
      firstDate: DateTime(1900),
      lastDate: DateTime(2200),
    );
    if (escolha != null && mounted) _data.text = _formatarData(escolha);
  }

  Future<void> _escolherHorario() async {
    final partes = _horario.text.split(':');
    final hora = partes.length == 2 ? int.tryParse(partes[0]) : null;
    final minuto = partes.length == 2 ? int.tryParse(partes[1]) : null;
    final escolha = await showTimePicker(
      context: context,
      initialTime: hora != null && minuto != null &&
              hora >= 0 && hora < 24 && minuto >= 0 && minuto < 60
          ? TimeOfDay(hour: hora, minute: minuto)
          : const TimeOfDay(hour: 19, minute: 0),
    );
    if (escolha != null && mounted) {
      _horario.text = '${escolha.hour.toString().padLeft(2, '0')}:'
          '${escolha.minute.toString().padLeft(2, '0')}';
    }
  }

  Future<void> _salvar() async {
    if (!_form.currentState!.validate() || _salvando) return;
    setState(() { _salvando = true; _erro = ''; });
    final atual = widget.atual;
    final extras = <String, String>{
      'data': _data.text,
      'horario': _horario.text,
      'pregador': _pregador.text.trim(),
      'igreja': _igreja.text.trim(),
      'texto_base': _textoBase.text.trim(),
      'tema': _tema.text.trim(),
      if (atual != null) 'id': '${atual.id}',
      if (atual != null) 'versao': '${atual.versao}',
    };
    try {
      final resposta = await widget.mqtt.executar(
          atual == null
              ? ComandoPregacao.criar.valor
              : ComandoPregacao.atualizar.valor,
          extras: extras);
      if (!mounted) return;
      if (resposta.ok) {
        Navigator.pop(context, 'ok');
      } else if (resposta.code == 'versao_desatualizada') {
        Navigator.pop(context, 'conflito');
      } else {
        setState(() {
          _erro = resposta.error.isEmpty
              ? 'Nao foi possivel salvar a programacao'
              : resposta.error;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _erro = 'Falha ao salvar a programacao');
    } finally {
      if (mounted) setState(() => _salvando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.atual == null ? 'NOVA PREGACAO' : 'EDITAR PREGACAO'),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          child: Form(
            key: _form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  controller: _data,
                  readOnly: true,
                  onTap: _escolherData,
                  decoration: const InputDecoration(labelText: 'Data',
                      suffixIcon: Icon(Icons.calendar_today)),
                  validator: (v) => v == null || v.isEmpty ? 'Informe a data' : null,
                ),
                TextFormField(
                  controller: _horario,
                  readOnly: true,
                  onTap: _escolherHorario,
                  decoration: const InputDecoration(labelText: 'Horario',
                      suffixIcon: Icon(Icons.access_time)),
                  validator: (v) => v == null || v.isEmpty ? 'Informe o horario' : null,
                ),
                TextFormField(
                  controller: _pregador,
                  maxLength: 120,
                  decoration: const InputDecoration(labelText: 'Pregador'),
                  validator: (v) => v == null || v.trim().isEmpty
                      ? 'Informe o pregador' : null,
                ),
                TextFormField(
                  controller: _igreja,
                  maxLength: 120,
                  decoration: const InputDecoration(labelText: 'Igreja'),
                  validator: (v) => v == null || v.trim().isEmpty
                      ? 'Informe a igreja' : null,
                ),
                TextFormField(
                  controller: _textoBase,
                  maxLength: 160,
                  decoration: const InputDecoration(labelText: 'Texto base'),
                ),
                TextFormField(
                  controller: _tema,
                  maxLength: 200,
                  decoration: const InputDecoration(labelText: 'Tema'),
                ),
                if (_erro.isNotEmpty)
                  Text(_erro, style: const TextStyle(color: Colors.red)),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _salvando ? null : () => Navigator.pop(context),
          child: const Text('CANCELAR'),
        ),
        FilledButton(
          onPressed: _salvando ? null : _salvar,
          child: Text(_salvando ? 'SALVANDO...' : 'SALVAR'),
        ),
      ],
    );
  }
}
