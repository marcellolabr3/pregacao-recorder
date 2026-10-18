// Pregacao Controle - app de controle remoto do gravador (Flutter).
//
// Uma tela principal + Configuracoes + Wi-Fi + Armazenamento + Drive, todos
// falhando com o MESMO equipamento por MQTT/TLS (docs/AGENTE.md).
import 'package:flutter/material.dart';

import 'configuracao.dart';
import 'mqtt_controlador.dart';
import 'tela_principal.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final cfg = await ArmazenamentoSeguro().carregar();
  runApp(PregacaoApp(cfg: cfg));
}

class PregacaoApp extends StatefulWidget {
  final Configuracao cfg;

  const PregacaoApp({super.key, required this.cfg});

  @override
  State<PregacaoApp> createState() => _PregacaoAppState();
}

class _PregacaoAppState extends State<PregacaoApp> {
  late final MqttControlador controlador;

  @override
  void initState() {
    super.initState();
    controlador = MqttControlador(widget.cfg);
  }

  @override
  void dispose() {
    controlador.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppScope(
      controlador: controlador,
      child: MaterialApp(
        title: 'Pregacao Controle',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorSchemeSeed: Colors.indigo,
          useMaterial3: true,
        ),
        home: const TelaPrincipal(),
      ),
    );
  }
}

/// O unico controlador MQTT do app, acessivel de qualquer tela.
class AppScope extends InheritedNotifier<MqttControlador> {
  const AppScope({
    super.key,
    required MqttControlador controlador,
    required super.child,
  }) : super(notifier: controlador);

  static MqttControlador of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope ausente na arvore');
    return scope!.notifier!;
  }
}
