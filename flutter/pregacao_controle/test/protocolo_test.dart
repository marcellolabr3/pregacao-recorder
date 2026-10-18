// Testes de protocolo: o contrato que o app fala com o agente do Raspberry
// (docs/AGENTE.md). Sem rede e sem dispositivo - a camada Dart pura.
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:pregacao_controle/configuracao.dart';
import 'package:pregacao_controle/protocolo.dart';

void main() {
  group('Topicos', () {
    test('derivam do device_id igual ao agente', () {
      final t = Topicos('pregacao-igreja-01');
      expect(t.avail, 'pregacao/pregacao-igreja-01/avail');
      expect(t.state, 'pregacao/pregacao-igreja-01/state');
      expect(t.events, 'pregacao/pregacao-igreja-01/events');
      expect(t.ack, 'pregacao/pregacao-igreja-01/ack');
      expect(t.cmd, 'pregacao/pregacao-igreja-01/cmd');
    });
  });

  group('montarComando', () {
    test('sempre leva cmd, req_id unico e ts (prazo de validade)', () {
      final agora = DateTime.now();
      final a = montarComando('START', reqId: 'a1', agora: agora);
      final b = montarComando('START', reqId: 'a2', agora: agora);
      expect(a['cmd'], 'START');
      expect(a['req_id'], 'a1');
      expect(b['req_id'], 'a2');
      expect(a['req_id'], isNot(b['req_id']));
      // ts em epoch segundos, dentro da janela do TTL do agente
      final ts = a['ts'] as double;
      expect((agora.millisecondsSinceEpoch / 1000.0 - ts).abs(), lessThan(2));
    });

    test('req_id gerado e unico entre envios', () {
      final ids = {for (var i = 0; i < 500; i++) novoReqId()};
      expect(ids.length, 500);
    });

    test('extras (ssid, password, path...) viajam junto', () {
      final cmd = montarComando('WIFI_CONNECT',
          extras: {'ssid': 'Igreja', 'password': '12345678'},
          reqId: 'x');
      expect(cmd['ssid'], 'Igreja');
      expect(cmd['password'], '12345678');
      expect(cmd['cmd'], 'WIFI_CONNECT');
    });

    test('payload e JSON valido (o que o agente recebe)', () {
      final texto = jsonEncode(montarComando('STOP', reqId: 'r'));
      expect(jsonDecode(texto)['cmd'], 'STOP');
    });
  });

  group('EstadoEquipamento', () {
    test('payload completo do agente', () {
      final st = EstadoEquipamento.fromJson(const {
        'device_id': 'pregacao-igreja-01',
        'device_name': 'Pulpito',
        'state': 'RECORDING',
        'banner': 'GRAVANDO',
        'detail': '',
        'started_at': 1790000000.4,
        'recording': {'active': true, 'segments': 12, 'bytes': 1048576},
        'uploads': {'pending': 0, 'running': 1, 'done': 3, 'failed': 0},
        'drive_connected': true,
        'network_online': true,
        'api_ok': true,
        'recording_dir': '/mnt/ssd/pregacoes',
        'storage_aviso': '',
        'free_mb': 5000,
        'recovery_pending': 0,
      });
      expect(st.state, 'RECORDING');
      expect(st.recordingActive, isTrue);
      expect(st.segments, 12);
      expect(st.bytes, 1048576);
      expect(st.uploadRunning, 1);
      expect(st.uploadDone, 3);
      expect(st.driveConnected, isTrue);
      expect(st.freeMb, 5000);
      expect(st.startedAt, closeTo(1790000000.4, 0.001));
    });

    test('agente antigo, sem campos novos, nao quebra', () {
      final st = EstadoEquipamento.fromJson(const {'state': 'IDLE'});
      expect(st.state, 'IDLE');
      expect(st.recordingActive, isFalse);
      expect(st.networkOnline, isTrue); // assumido saudavel sem o campo
      expect(st.apiOk, isTrue);
      expect(st.storageAviso, '');
    });
  });

  group('rotulos da tela', () {
    test('rotuloDe segue os textos do app Android', () {
      expect(rotuloDe('IDLE', 'PRONTO'), 'PRONTO');
      expect(rotuloDe('RECORDING', 'GRAVANDO'), 'GRAVANDO');
      expect(rotuloDe('FINALIZING', 'ENCERRANDO'), 'ENCERRANDO');
      expect(rotuloDe('UPLOADING', 'ENVIANDO'), 'ENVIANDO AO DRIVE');
      expect(rotuloDe('COMPLETED', 'ENVIADO'), 'ENVIADO');
      expect(rotuloDe('ERROR', ''), 'ATENCAO');
      expect(rotuloDe('ERROR', 'BATERIA FRACA'), 'BATERIA FRACA');
      expect(rotuloDe('', ''), 'AGUARDANDO');
    });

    test('tomDe define a cor da situacao', () {
      expect(tomDe('IDLE', ''), TomEstado.pronto);
      expect(tomDe('RECORDING', ''), TomEstado.gravando);
      expect(tomDe('UPLOADING', ''), TomEstado.enviando);
      expect(tomDe('COMPLETED', ''), TomEstado.enviado);
      expect(tomDe('ERROR', 'X'), TomEstado.atencao);
      expect(tomDe('RECOVERY_REQUIRED', ''), TomEstado.atencao);
      expect(tomDe('QUALQUER', ''), TomEstado.fraco);
    });

    test('formatarTempo zera negativos e conta direito', () {
      expect(formatarTempo(const Duration(hours: 1, minutes: 2, seconds: 3)),
          '01:02:03');
      expect(formatarTempo(const Duration(seconds: 65)), '00:01:05');
      expect(formatarTempo(const Duration(seconds: -10)), '00:00:00');
      expect(formatarTempo(Duration.zero), '00:00:00');
    });
  });

  group('Ack', () {
    test('ack de sucesso com detalhe', () {
      final ack = Ack.fromJson(const {
        'ok': true,
        'cmd': 'WIFI_CONNECT',
        'req_id': 'r1',
        'state': 'IDLE',
        'detail': 'conectado',
        'ssid': 'Igreja',
      });
      expect(ack.ok, isTrue);
      expect(ack.reqId, 'r1');
      expect(ack.ssid, 'Igreja');
      expect(ack.detail, 'conectado');
    });

    test('ack de erro carrega cmd/req_id (comando expirado)', () {
      final ack = Ack.fromJson(const {
        'ok': false,
        'cmd': 'STOP',
        'req_id': 'r2',
        'error': 'comando expirado (prazo de validade de 120s)',
      });
      expect(ack.ok, isFalse);
      expect(ack.cmd, 'STOP');
      expect(ack.reqId, 'r2');
      expect(ack.error, contains('expirado'));
    });

    test('ack de WIFI_SCAN carrega as redes', () {
      final ack = Ack.fromJson(const {
        'ok': true,
        'req_id': 'r3',
        'networks': [
          {'ssid': 'Igreja', 'signal': 80, 'security': 'WPA2',
           'in_use': true},
          {'ssid': 'Convidados', 'signal': 40, 'security': '--',
           'in_use': false},
        ],
      });
      expect(ack.networks.length, 2);
      expect(ack.networks.first['ssid'], 'Igreja');
      expect(ack.networks.first['in_use'], isTrue);
    });

    test('ack de DRIVE_STATUS carrega o recorte do agente', () {
      final ack = Ack.fromJson(const {
        'ok': true,
        'req_id': 'r4',
        'drive': {
          'libraries': true,
          'credentials': true,
          'connected': true,
          'account': 'igreja@gmail.com',
          'folder': 'pregacoes',
          'auto_upload': true,
        },
      });
      expect(ack.drive['connected'], isTrue);
      expect(ack.drive['account'], 'igreja@gmail.com');
    });
  });

  group('EventoSistema', () {
    test('gravacao_pronta traz o caminho do arquivo', () {
      final ev = EventoSistema.fromJson(const {
        'kind': 'gravacao_pronta',
        'seq': 1,
        'ts': 1790000000.0,
        'data': {
          'path': '/mnt/ssd/pregacoes/2026-10-18_100000.wav',
          'message': 'gravacao pronta',
        },
      });
      expect(ev.kind, 'gravacao_pronta');
      expect(ev.path, '/mnt/ssd/pregacoes/2026-10-18_100000.wav');
      expect(ev.message, 'gravacao pronta');
    });

    test('evento malformado nao derruba', () {
      final ev = EventoSistema.fromJson(const {'kind': 'desconhecido'});
      expect(ev.kind, 'desconhecido');
      expect(ev.message, '');
      expect(ev.path, '');
    });
  });

  group('Configuracao', () {
    test('pronto() exige token (host/ID vem de fabrica)', () {
      expect(Configuracao().pronto, isFalse); // sem token
      final cfg = Configuracao()..token = 'segredo';
      expect(cfg.pronto, isTrue);
      final semServidor = Configuracao(servidor: ' ', token: 'x');
      expect(semServidor.pronto, isFalse);
    });

    test('defaults sao os identificadores publicos do servico', () {
      final cfg = Configuracao();
      expect(cfg.servidor, Configuracao.padraoServidor);
      expect(cfg.aparelho, Configuracao.padraoAparelho);
      expect(cfg.porta, 8883);
      expect(cfg.tls, isTrue);
      expect(cfg.usuario, 'operador');
    });

    test('roundtrip JSON preserva tudo (inclusive o token)', () {
      final cfg = Configuracao(
        servidor: 'broker.exemplo.com',
        porta: 8883,
        tls: false,
        aparelho: 'igreja-02',
        usuario: 'operador',
        token: 'token-com "aspas" e \\ barras',
      );
      final volta = Configuracao.fromJson(
          Map<String, dynamic>.from(jsonDecode(jsonEncode(cfg.toJson()))));
      expect(volta.servidor, cfg.servidor);
      expect(volta.porta, cfg.porta);
      expect(volta.tls, isFalse);
      expect(volta.aparelho, 'igreja-02');
      expect(volta.usuario, cfg.usuario);
      expect(volta.token, cfg.token);
    });
  });
}
