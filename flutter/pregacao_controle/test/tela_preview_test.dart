// Previa das telas no PC (sem emulador): renderiza a tela principal nos
// estados reais e grava as imagens em test/goldens/.
//
//   flutter test --update-goldens test/tela_preview_test.dart
//
// Nao e' teste de comportamento (os de protocolo estao em
// protocolo_test.dart): e' a captura visual para revisao.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pregacao_controle/configuracao.dart';
import 'package:pregacao_controle/main.dart';
import 'package:pregacao_controle/mqtt_controlador.dart';
import 'package:pregacao_controle/protocolo.dart';
import 'package:pregacao_controle/tela_principal.dart';

Future<void> _capturar(
  WidgetTester tester,
  MqttControlador controlador,
  String arquivo,
) async {
  // celular 4.7" - mesma faixa dos aparelhos dos operadores
  tester.view.physicalSize = const Size(393 * 3, 852 * 3);
  tester.view.devicePixelRatio = 3.0;
  addTearDown(tester.view.resetPhysicalSize);
  await tester.pumpWidget(
    MaterialApp(
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFFD6AD53),
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF080807),
        useMaterial3: true,
      ),
      home: AppScope(controlador: controlador, child: const TelaPrincipal()),
    ),
  );
  await tester.pump(const Duration(milliseconds: 100));
  await expectLater(
    find.byType(Scaffold),
    matchesGoldenFile('goldens/$arquivo'),
  );
}

void main() {
  testWidgets('NotebookLM oferece diagnostico e renovacao do login no APK',
      (tester) async {
    final controlador = MqttControlador(Configuracao(token: 'x'));
    controlador.conectadoBroker = true;
    controlador.equipamentoOnline = true;
    controlador.estado = const EstadoEquipamento(
      state: 'IDLE',
      estudosAtivo: true,
      notebooklmEstado: 'auth',
    );
    await tester.pumpWidget(MaterialApp(
      home: AppScope(controlador: controlador, child: const TelaPrincipal()),
    ));
    expect(find.text('DIAGNOSTICAR SESSAO'), findsOneWidget);
    expect(find.text('RENOVAR LOGIN NO PC'), findsOneWidget);
    controlador.dispose();
  });

  testWidgets('previa: sem token (primeira abertura)', (tester) async {
    final controlador = MqttControlador(Configuracao());
    await _capturar(tester, controlador, 'principal_sem_token.png');
    controlador.dispose();
  });

  testWidgets('previa: PRONTO e ONLINE', (tester) async {
    final controlador = MqttControlador(Configuracao(token: 'x'));
    // sem conexao real: os campos de estado sao injetados direto
    controlador.conectadoBroker = true;
    controlador.equipamentoOnline = true;
    controlador.estado = const EstadoEquipamento(
      deviceId: 'pregacao-igreja-01',
      deviceName: 'Pulpito',
      state: 'IDLE',
      banner: 'PRONTO',
      uploadDone: 1,
    );
    await _capturar(tester, controlador, 'principal_pronto.png');
    controlador.dispose();
  });

  testWidgets('previa: GRAVANDO com cronometro e eventos', (tester) async {
    final controlador = MqttControlador(Configuracao(token: 'x'));
    controlador.conectadoBroker = true;
    controlador.equipamentoOnline = true;
    controlador.nomeArquivo = '2026-10-18_100000_pregacao.wav';
    controlador.estado = EstadoEquipamento(
      deviceId: 'pregacao-igreja-01',
      deviceName: 'Pulpito',
      state: 'RECORDING',
      banner: 'GRAVANDO',
      startedAt: DateTime.now().millisecondsSinceEpoch / 1000.0 - 3725,
      recordingActive: true,
      segments: 7,
      bytes: 64 * 1024 * 1024,
      uploadPending: 1,
    );
    controlador.eventos
      ..add('10:00  gravacao_iniciada  pregacao de manha')
      ..add('09:58  upload_concluido  2026-10-11_100000.wav');
    unawaited(Future<void>.delayed(Duration.zero));
    await _capturar(tester, controlador, 'principal_gravando.png');
    controlador.dispose();
  });
}
