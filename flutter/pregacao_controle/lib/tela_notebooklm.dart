import 'package:flutter/material.dart';

import 'mqtt_controlador.dart';
import 'protocolo.dart';

/// Entrada permanente no menu, inclusive antes de chegar o estado MQTT.
class TelaNotebookLm extends StatelessWidget {
  final MqttControlador mqtt;

  const TelaNotebookLm({super.key, required this.mqtt});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Conta NotebookLM')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [NotebookLmPanel(mqtt: mqtt)],
      ),
    );
  }
}

class NotebookLmPanel extends StatefulWidget {
  final MqttControlador mqtt;

  const NotebookLmPanel({super.key, required this.mqtt});

  @override
  State<NotebookLmPanel> createState() => _NotebookLmPanelState();
}

class _NotebookLmPanelState extends State<NotebookLmPanel> {
  bool _enviando = false;

  Future<void> _executar(String comando) async {
    setState(() => _enviando = true);
    final ack = await widget.mqtt.executar(comando);
    if (!mounted) return;
    setState(() => _enviando = false);
    final detalhe = ack.ok
        ? (ack.detail.isEmpty ? 'Acao do NotebookLM solicitada.' : ack.detail)
        : (ack.error.isEmpty ? 'Nao foi possivel concluir a acao.' : ack.error);
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(detalhe)));
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.mqtt,
      builder: (context, _) {
        final st = widget.mqtt.estado;
        final status = st ?? const EstadoEquipamento();
        final ligado =
            widget.mqtt.conectadoBroker && widget.mqtt.equipamentoOnline;
        final estudosAtivo = st != null && status.estudosAtivo;
        final loginEmAndamento = status.notebooklmLoginEmAndamento;
        final ocupado = status.notebooklmDiagnostico || loginEmAndamento;
        final estado = status.notebooklmEstado;
        final rotulo = st == null
            ? 'Aguardando estado do PC'
            : !estudosAtivo
            ? 'Estudo automatico desativado no PC'
            : loginEmAndamento
            ? 'Login em andamento no PC'
            : switch (estado) {
                'ok' => 'Conta conectada',
                'auth' => 'Sessao expirada',
                'rede' => 'Sem resposta da rede',
                _ => 'Aguardando verificacao',
              };
        final cor = switch (estado) {
          'ok' when estudosAtivo => Colors.green,
          'auth' when estudosAtivo => Colors.orange,
          'rede' when estudosAtivo => Colors.orange,
          _ => Colors.grey,
        };
        final podeAgir = ligado && estudosAtivo && !ocupado && !_enviando;
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'NOTEBOOKLM',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 6),
                Text(rotulo, style: TextStyle(color: cor)),
                if (loginEmAndamento &&
                    status.notebooklmLoginDetalhe.isNotEmpty)
                  Text(status.notebooklmLoginDetalhe),
                if (estudosAtivo &&
                    estado != 'ok' &&
                    status.notebooklmDetalhe.isNotEmpty)
                  Text(status.notebooklmDetalhe),
                if (estudosAtivo)
                  Text(
                    status.notebooklmMasterToken
                        ? 'Renovacao automatica configurada'
                        : 'Renovacao automatica ainda nao configurada',
                  ),
                if (estudosAtivo && status.estudosAguardando > 0)
                  Text(
                    '${status.estudosAguardando} estudo(s) aguardando a conta',
                  ),
                if (!ligado)
                  const Text('Conecte o celular ao PC para usar os comandos.'),
                const SizedBox(height: 8),
                const Text(
                  'A conta Google e validada pelo PC. Se precisar entrar '
                  'novamente, o navegador abre no computador.',
                ),
                if (ocupado) const LinearProgressIndicator(),
                const SizedBox(height: 6),
                OutlinedButton.icon(
                  onPressed: podeAgir ? () => _executar('NLM_REFRESH') : null,
                  icon: const Icon(Icons.refresh),
                  label: const Text('DIAGNOSTICAR SESSAO'),
                ),
                OutlinedButton.icon(
                  onPressed: podeAgir ? () => _executar('NLM_RECONNECT') : null,
                  icon: const Icon(Icons.login),
                  label: const Text('RENOVAR LOGIN NO PC'),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
