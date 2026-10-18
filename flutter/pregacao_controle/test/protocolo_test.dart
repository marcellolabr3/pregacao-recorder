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
      expect(t.jobs, 'pregacao/pregacao-igreja-01/jobs');
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

  group('ProgressoJob (S3)', () {
    test('payload completo do agente via SSE', () {
      final pj = ProgressoJob.fromJson(const {
        'job_id': 'abc123',
        'recording_id': '20261018-100000-xyz',
        'estado': 'EXECUTANDO',
        'etapa': 'ESTUDO',
        'percentual': 57,
        'descricao': 'Gerando o estudo devocional',
        'motivo': '',
        'seq': 1790000000123,
      });
      expect(pj.jobId, 'abc123');
      expect(pj.recordingId, '20261018-100000-xyz');
      expect(pj.estado, 'EXECUTANDO');
      expect(pj.etapa, 'ESTUDO');
      expect(pj.percentual, 57);
      expect(pj.descricao, 'Gerando o estudo devocional');
      expect(pj.seq, 1790000000123);
      expect(pj.envioConfirmado, isFalse);
      expect(pj.emEspera, isFalse);
      expect(pj.falhou, isFalse);
      expect(pj.rotuloEtapa, 'GERANDO ESTUDO');
      expect(pj.tomEtapa, 'ativo');
    });

    test('etapa FINAL = envio confirmado (100%)', () {
      final pj = ProgressoJob.fromJson(const {
        'job_id': 'done',
        'etapa': 'FINAL',
        'percentual': 100,
        'estado': 'CONCLUIDO',
      });
      expect(pj.envioConfirmado, isTrue);
      expect(pj.rotuloEtapa, 'ENVIADO');
      expect(pj.tomEtapa, 'concluido');
    });

    test('etapa FINAL_SEM_ENVIO = 86% honesto (WhatsApp nao configurado)', () {
      final pj = ProgressoJob.fromJson(const {
        'job_id': 'sem_envio',
        'etapa': 'FINAL_SEM_ENVIO',
        'percentual': 86,
        'estado': 'CONCLUIDO',
      });
      expect(pj.envioConfirmado, isFalse);
      expect(pj.rotuloEtapa, 'PRONTO (SEM ENVIO)');
      expect(pj.tomEtapa, 'concluido');
    });

    test('AGUARDANDO_INTERVENCAO = aguardando (amarelo)', () {
      final pj = ProgressoJob.fromJson(const {
        'job_id': 'wait',
        'estado': 'AGUARDANDO_INTERVENCAO',
        'etapa': 'PRE-FLIGHT',
        'motivo': 'autenticacao expirada',
      });
      expect(pj.emEspera, isTrue);
      expect(pj.tomEtapa, 'aguardando');
    });

    test('ERRO = falhou (vermelho)', () {
      final pj = ProgressoJob.fromJson(const {
        'job_id': 'fail',
        'estado': 'ERRO',
        'etapa': 'PDF',
        'erro': 'codigo 1',
      });
      expect(pj.falhou, isTrue);
      expect(pj.tomEtapa, 'erro');
    });

    test('payload malformado (campos ausentes) nao quebra', () {
      final pj = ProgressoJob.fromJson(const {});
      expect(pj.jobId, '');
      expect(pj.percentual, 0);
      expect(pj.envioConfirmado, isFalse);
      expect(pj.emEspera, isFalse);
      expect(pj.falhou, isFalse);
    });

    test('percentual clamp 0..100 (agente bugado)', () {
      final pj1 = ProgressoJob.fromJson(const {'percentual': -10});
      expect(pj1.percentual, 0);
      final pj2 = ProgressoJob.fromJson(const {'percentual': 200});
      expect(pj2.percentual, 100);
    });

    test('seq aceita int, double ou String numerica', () {
      final a = ProgressoJob.fromJson(const {'seq': 1});
      final b = ProgressoJob.fromJson(const {'seq': 1.5});
      final c = ProgressoJob.fromJson(const {'seq': '123'});
      expect(a.seq, 1);
      expect(b.seq, 1);
      expect(c.seq, 123);
    });

    test('todas as etapas mapeadas para rotulo legivel', () {
      const etapas = {
        'PRE-FLIGHT': 'VERIFICANDO SESSAO',
        'NOTEBOOKLM': 'NOTEBOOKLM PREPARANDO',
        'ESTUDO': 'GERANDO ESTUDO',
        'PDF': 'CONVERTENDO PDF',
        'WHATSAPP': 'ENVIANDO WHATSAPP',
        'FINAL': 'ENVIADO',
        'FINAL_SEM_ENVIO': 'PRONTO (SEM ENVIO)',
      };
      etapas.forEach((k, v) {
        final pj = ProgressoJob.fromJson({'etapa': k});
        expect(pj.rotuloEtapa, v, reason: 'etapa $k');
      });
    });
  });
}

  group('Pregacao (S4)', () {
    test('ComandoPregacao valores corretos', () {
      expect(ComandoPregacao.listar.valor, 'PREGACAO_LISTAR');
      expect(ComandoPregacao.obter.valor, 'PREGACAO_OBTER');
      expect(ComandoPregacao.criar.valor, 'PREGACAO_CRIAR');
      expect(ComandoPregacao.atualizar.valor, 'PREGACAO_ATUALIZAR');
      expect(ComandoPregacao.deletar.valor, 'PREGACAO_DELETAR');
    });

    test('payload completo do servidor', () {
      final p = Pregacao.fromJson(const {
        'id': 42,
        'data': '2026-10-25',
        'horario': '19:00',
        'pregador': 'Pr. Joao',
        'igreja': 'Igreja Central',
        'texto_base': 'Joao 3:16',
        'tema': 'O Amor de Deus',
        'versao': 3,
        'criado_em': 1790000000.0,
        'atualizado_em': 1790000001.0,
      });
      expect(p.id, 42);
      expect(p.data, '2026-10-25');
      expect(p.horario, '19:00');
      expect(p.pregador, 'Pr. Joao');
      expect(p.igreja, 'Igreja Central');
      expect(p.textoBase, 'Joao 3:16');
      expect(p.tema, 'O Amor de Deus');
      expect(p.versao, 3);
      expect(p.criadoEm, closeTo(1790000000.0, 0.001));
      expect(p.atualizadoEm, closeTo(1790000001.0, 0.001));
      expect(p.rotulo, '2026-10-25 19:00  Pr. Joao / Igreja Central');
    });

    test('toJson so inclui campos necessarios para criar/atualizar', () {
      final p = Pregacao(
        id: 1,
        data: '2026-10-25',
        horario: '19:00',
        pregador: 'Pr. A',
        igreja: 'Igreja B',
        textoBase: 'Texto',
        tema: 'Tema',
        versao: 2,
      );
      final json = p.toJson();
      expect(json['id'], 1);
      expect(json['data'], '2026-10-25');
      expect(json['horario'], '19:00');
      expect(json['pregador'], 'Pr. A');
      expect(json['igreja'], 'Igreja B');
      expect(json['texto_base'], 'Texto');
      expect(json['tema'], 'Tema');
      expect(json['versao'], 2);
      // criado_em e atualizado_em nao vao no toJson (so leitura)
      expect(json.containsKey('criado_em'), isFalse);
    });

    test('payload malformado (campos ausentes) nao quebra', () {
      final p = Pregacao.fromJson(const {});
      expect(p.id, 0);
      expect(p.data, '');
      expect(p.versao, 1);
      expect(p.rotulo, '  / ');
    });

    test('aceita int, double ou String nos numericos', () {
      final a = Pregacao.fromJson({'id': 1, 'versao': 2});
      final b = Pregacao.fromJson({'id': 1.0, 'versao': 2.0});
      final c = Pregacao.fromJson({'id': '5', 'versao': '3'});
      expect(a.id, 1);
      expect(a.versao, 2);
      expect(b.id, 1);
      expect(b.versao, 2);
      expect(c.id, 5);
      expect(c.versao, 3);
    });
  });
}
