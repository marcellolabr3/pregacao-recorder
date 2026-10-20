// Protocolo MQTT do controle remoto - o mesmo contrato do agente do
// PC (docs/AGENTE.md). Tudo sob `pregacao/<device_id>/`:
//
//   cmd     app -> agente   {"cmd":"START","req_id":"...","ts":179...}
//   ack     agente -> app   resposta correlacionada pelo req_id
//   state   agente -> app   estado completo (RETIDO)
//   events  agente -> app   eventos (gravacao_*, upload_*)
//   avail   agente -> app   "online"/"offline" (retido + LWT)
//
// Este arquivo nao depende de Flutter: e a base dos testes de protocolo.
library;

import 'dart:math';

/// Raiz de todos os topics (igual ao TOPIC_ROOT do agente Python).
const String raizTopic = 'pregacao';

/// Prazo de validade do comando, em segundos (espelha COMANDO_TTL_SEGUNDOS
/// do agente): o "ts" enviado junto e conferido la do outro lado.
const int comandoTtlSegundos = 120;

/// Espera maxima do ack de um comando, em segundos (cinto de seguranca do
/// aplicativo: se a resposta nao chegar, o operador e avisado).
const int ackTimeoutSegundos = 20;

/// Os seis topics de um aparelho, derivados do device_id.
/// O sexto (jobs) e RETIDO: o celular que reconectar recebe o progresso
/// atual do estudo sem reiniciar nada (S3).
class Topicos {
  final String device;

  const Topicos(this.device);

  String get raiz => '$raizTopic/$device';
  String get avail => '$raiz/avail';
  String get state => '$raiz/state';
  String get events => '$raiz/events';
  String get ack => '$raiz/ack';
  String get cmd => '$raiz/cmd';
  String get jobs => '$raiz/jobs';
}

/// req_id proprio: unico por envio - e o que permite saber qual resposta
/// pertence a qual botao (e descartar ack atrasado de outro pedido).
final Random _aleatorio = Random();

String novoReqId() {
  final agora = DateTime.now().microsecondsSinceEpoch;
  return 'fl-$agora-${_aleatorio.nextInt(0xFFFFFF).toRadixString(16)}';
}

/// Monta o payload de um comando. O "ts" (epoch em segundos) e o campo do
/// prazo de validade conferido pelo agente; sem ele o broker/aparelho nao
/// teria como recusar um comando atrasado.
Map<String, dynamic> montarComando(
  String cmd, {
  Map<String, String> extras = const {},
  String? reqId,
  DateTime? agora,
}) {
  final ts = (agora ?? DateTime.now()).millisecondsSinceEpoch / 1000.0;
  return {
    'cmd': cmd,
    'req_id': reqId ?? novoReqId(),
    'ts': ts,
    ...extras,
  };
}

/// Enumeracao dos tons da tela principal (a cor em si fica na UI).
enum TomEstado { gravando, pronto, atencao, enviando, enviado, fraco }

/// Estado do equipamento, conforme o payload "state" do agente.
class EstadoEquipamento {
  final String deviceId;
  final String deviceName;
  final String state;
  final String banner;
  final String detail;
  final double startedAt;
  final bool recordingActive;
  final int segments;
  final int bytes;
  final int uploadPending;
  final int uploadRunning;
  final int uploadDone;
  final int uploadFailed;
  final bool driveConnected;
  final bool networkOnline;
  final bool apiOk;
  final String recordingDir;
  final String storageAviso;
  final int freeMb;
  final int recoveryPending;

  const EstadoEquipamento({
    this.deviceId = '',
    this.deviceName = '',
    this.state = '',
    this.banner = '',
    this.detail = '',
    this.startedAt = 0,
    this.recordingActive = false,
    this.segments = 0,
    this.bytes = 0,
    this.uploadPending = 0,
    this.uploadRunning = 0,
    this.uploadDone = 0,
    this.uploadFailed = 0,
    this.driveConnected = false,
    this.networkOnline = true,
    this.apiOk = true,
    this.recordingDir = '',
    this.storageAviso = '',
    this.freeMb = 0,
    this.recoveryPending = 0,
  });

  /// Tolerante a campos ausentes: o payload pode vir de um agente antigo.
  factory EstadoEquipamento.fromJson(Map<String, dynamic> json) {
    final recording = (json['recording'] as Map<String, dynamic>?) ?? const {};
    final uploads = (json['uploads'] as Map<String, dynamic>?) ?? const {};
    double numero(dynamic v) => (v is num) ? v.toDouble() : 0;
    int inteiro(dynamic v) => (v is num) ? v.toInt() : 0;
    return EstadoEquipamento(
      deviceId: json['device_id'] as String? ?? '',
      deviceName: json['device_name'] as String? ?? '',
      state: json['state'] as String? ?? '',
      banner: json['banner'] as String? ?? '',
      detail: json['detail'] as String? ?? '',
      startedAt: numero(json['started_at']),
      recordingActive: recording['active'] == true,
      segments: inteiro(recording['segments']),
      bytes: inteiro(recording['bytes']),
      uploadPending: inteiro(uploads['pending']),
      uploadRunning: inteiro(uploads['running']),
      uploadDone: inteiro(uploads['done']),
      uploadFailed: inteiro(uploads['failed']),
      driveConnected: json['drive_connected'] == true,
      networkOnline: json['network_online'] != false,
      apiOk: json['api_ok'] != false,
      recordingDir: json['recording_dir'] as String? ?? '',
      storageAviso: json['storage_aviso'] as String? ?? '',
      freeMb: inteiro(json['free_mb']),
      recoveryPending: inteiro(json['recovery_pending']),
    );
  }
}

/// Rotulo exibido ao operador (mesmos textos do app Android).
String rotuloDe(String state, String banner) {
  switch (state) {
    case 'IDLE':
      return 'PRONTO';
    case 'RECORDING':
      return 'GRAVANDO';
    case 'FINALIZING':
      return 'ENCERRANDO';
    case 'UPLOADING':
      return 'ENVIANDO AO DRIVE';
    case 'COMPLETED':
      return 'ENVIADO';
    case 'RECOVERY_REQUIRED':
      return 'ATENCAO - GRAVACAO INTERROMPIDA';
    case 'ERROR':
      return banner.isNotEmpty ? banner : 'ATENCAO';
    default:
      return banner.isNotEmpty ? banner : (state.isNotEmpty ? state : 'AGUARDANDO');
  }
}

/// Tom do rotulo (a tela traduz para Color).
TomEstado tomDe(String state, String banner) {
  switch (state) {
    case 'RECORDING':
      return TomEstado.gravando;
    case 'IDLE':
      return TomEstado.pronto;
    case 'ERROR':
    case 'RECOVERY_REQUIRED':
      return TomEstado.atencao;
    case 'UPLOADING':
      return TomEstado.enviando;
    case 'COMPLETED':
      return TomEstado.enviado;
    default:
      return banner.isNotEmpty ? TomEstado.atencao : TomEstado.fraco;
  }
}

/// Cronometro HH:MM:SS calculado a partir de started_at (epoch).
String formatarTempo(Duration decorrido) {
  final total = decorrido.isNegative ? Duration.zero : decorrido;
  String dois(int v) => v.toString().padLeft(2, '0');
  return '${dois(total.inHours)}:${dois(total.inMinutes % 60)}:'
      '${dois(total.inSeconds % 60)}';
}

/// Um ack do agente, normalizado.
class Ack {
  final bool ok;
  final String cmd;
  final String reqId;
  final String error;
  final String code;
  final String detail;
  final String state;
  final bool idempotent;
  final String ssid;
  final String url;
  final String redirectUri;
  final String account;
  final bool connected;
  final String folderId;
  final List<Map<String, dynamic>> networks;
  final Map<String, dynamic> drive;
  final Map<String, dynamic> storage;
  final String current;
  final List<Pregacao> pregacoes;
  final int totalPregacoes;

  const Ack({
    this.ok = false,
    this.cmd = '',
    this.reqId = '',
    this.error = '',
    this.code = '',
    this.detail = '',
    this.state = '',
    this.idempotent = false,
    this.ssid = '',
    this.url = '',
    this.redirectUri = '',
    this.account = '',
    this.connected = false,
    this.folderId = '',
    this.networks = const [],
    this.drive = const {},
    this.storage = const {},
    this.current = '',
    this.pregacoes = const [],
    this.totalPregacoes = 0,
  });

  factory Ack.fromJson(Map<String, dynamic> json) {
    final redes = <Map<String, dynamic>>[];
    final raw = json['networks'];
    if (raw is List) {
      for (final item in raw) {
        if (item is Map<String, dynamic>) redes.add(item);
      }
    }
    final programacao = <Pregacao>[];
    final itens = json['pregacoes'];
    if (itens is List) {
      for (final item in itens) {
        if (item is Map<String, dynamic>) {
          programacao.add(Pregacao.fromJson(item));
        }
      }
    }
    return Ack(
      ok: json['ok'] == true,
      cmd: json['cmd'] as String? ?? '',
      reqId: json['req_id'] as String? ?? '',
      error: json['error'] as String? ?? '',
      code: json['code'] as String? ?? '',
      detail: json['detail'] as String? ?? '',
      state: json['state'] as String? ?? '',
      idempotent: json['idempotent'] == true,
      ssid: json['ssid'] as String? ?? '',
      url: json['url'] as String? ?? '',
      redirectUri: json['redirect_uri'] as String? ?? '',
      account: json['account'] as String? ?? '',
      connected: json['connected'] == true,
      folderId: json['folder_id'] as String? ?? '',
      networks: redes,
      drive: (json['drive'] as Map<String, dynamic>?) ?? const {},
      storage: (json['storage'] as Map<String, dynamic>?) ?? const {},
      current: json['current'] as String? ?? '',
      pregacoes: programacao,
      totalPregacoes: json['total'] is int ? json['total'] as int : programacao.length,
    );
  }
}

/// Um evento do topic "events" ({kind, seq, ts, data}).
class EventoSistema {
  final String kind;
  final String message;
  final String path;

  const EventoSistema({this.kind = '', this.message = '', this.path = ''});

  factory EventoSistema.fromJson(Map<String, dynamic> json) {
    final data = (json['data'] as Map<String, dynamic>?) ?? const {};
    return EventoSistema(
      kind: json['kind'] as String? ?? '',
      message: data['message'] as String? ?? '',
      path: data['path'] as String? ?? '',
    );
  }
}

/// Progresso do estudo por job (topic "jobs", retido).
/// O painel/APK so avanca a barra com marco REAL concluido (S3):
/// GRAVACAO -> MP3 -> DRIVE -> NOTEBOOKLM -> ESTUDO -> PDF -> WHATSAPP.
/// Durante o trabalho, percentual acompanha marcos concluidos. Ao terminar,
/// 100% representa a tarefa concluida; envio opcional pulado fica identificado.
class ProgressoJob {
  final String jobId;
  final String recordingId;
  final String estado;
  final String etapa;
  final int percentual;
  final String descricao;
  final String motivo;
  final int seq;

  const ProgressoJob({
    this.jobId = '',
    this.recordingId = '',
    this.estado = '',
    this.etapa = '',
    this.percentual = 0,
    this.descricao = '',
    this.motivo = '',
    this.seq = 0,
  });

  /// Tolerante a campos ausentes: agente antigo ou payload parcial.
  factory ProgressoJob.fromJson(Map<String, dynamic> json) {
    int inteiro(dynamic v) {
      if (v is int) return v;
      if (v is double) return v.toInt();
      if (v is String) return int.tryParse(v) ?? 0;
      return 0;
    }

    return ProgressoJob(
      jobId: json['job_id'] as String? ?? '',
      recordingId: json['recording_id'] as String? ?? '',
      estado: json['estado'] as String? ?? '',
      etapa: json['etapa'] as String? ?? '',
      percentual: inteiro(json['percentual']).clamp(0, 100),
      descricao: json['descricao'] as String? ?? '',
      motivo: json['motivo'] as String? ?? '',
      seq: inteiro(json['seq']),
    );
  }

  /// Se o envio por WhatsApp foi confirmado (etapa FINAL = 100%).
  bool get envioConfirmado => etapa == 'FINAL';

  /// A tarefa terminou; o envio opcional pode ter sido pulado.
  bool get concluido => estado == 'CONCLUIDO';

  /// Se o estudo esta em espera (sessao/rede) - passo ativo amarelo.
  bool get emEspera => estado == 'AGUARDANDO_INTERVENCAO';

  /// Se o estudo falhou (etapa vermelha).
  bool get falhou => estado == 'ERRO';

  /// Rotulo curto da etapa para a UI.
  String get rotuloEtapa {
    switch (etapa) {
      case 'PRE-FLIGHT':
        return 'VERIFICANDO SESSAO';
      case 'NOTEBOOKLM':
        return 'NOTEBOOKLM PREPARANDO';
      case 'ESTUDO':
        return 'GERANDO ESTUDO';
      case 'PDF':
        return 'CONVERTENDO PDF';
      case 'WHATSAPP':
        return 'ENVIANDO WHATSAPP';
      case 'FINAL':
        return 'ENVIADO';
      case 'FINAL_SEM_ENVIO':
        return 'PRONTO (SEM ENVIO)';
      default:
        return etapa;
    }
  }

  /// Tom da etapa (concluido/ativo/aguardando/erro/pendente) - a UI usa
  /// para escolher a cor do ponto/pill.
  String get tomEtapa {
    if (estado == 'ERRO') return 'erro';
    if (estado == 'AGUARDANDO_INTERVENCAO') return 'aguardando';
    if (estado == 'CONCLUIDO') return 'concluido';
    if (estado == 'EXECUTANDO') return 'ativo';
    return 'pendente';
  }
}

/// Comando para gerenciar programacao de pregacoes (S4).
/// O agente recebe, valida (admin) e executa no SQLite local.
/// Payloads usam o mesmo contrato de versao otimista do servidor.
enum ComandoPregacao {
  listar('PREGACAO_LISTAR'),
  obter('PREGACAO_OBTER'),
  criar('PREGACAO_CRIAR'),
  atualizar('PREGACAO_ATUALIZAR'),
  deletar('PREGACAO_DELETAR');

  final String valor;
  const ComandoPregacao(this.valor);
}

/// Pregacao (metadados da programacao) - espelha a tabela SQLite.
/// Versao otimista: atualizar/deletar so sucedem se versao bater.
class Pregacao {
  final int id;
  final String data;
  final String horario;
  final String pregador;
  final String igreja;
  final String textoBase;
  final String tema;
  final int versao;
  final double criadoEm;
  final double atualizadoEm;

  const Pregacao({
    this.id = 0,
    this.data = '',
    this.horario = '',
    this.pregador = '',
    this.igreja = '',
    this.textoBase = '',
    this.tema = '',
    this.versao = 1,
    this.criadoEm = 0,
    this.atualizadoEm = 0,
  });

  factory Pregacao.fromJson(Map<String, dynamic> json) {
    int inteiro(dynamic v, {int padrao = 0}) {
      if (v is int) return v;
      if (v is double) return v.toInt();
      if (v is String) return int.tryParse(v) ?? padrao;
      return padrao;
    }
    double real(dynamic v) {
      if (v is double) return v;
      if (v is int) return v.toDouble();
      if (v is String) return double.tryParse(v) ?? 0;
      return 0;
    }

    return Pregacao(
      id: inteiro(json['id']),
      data: json['data'] as String? ?? '',
      horario: json['horario'] as String? ?? '',
      pregador: json['pregador'] as String? ?? '',
      igreja: json['igreja'] as String? ?? '',
      textoBase: json['texto_base'] as String? ?? '',
      tema: json['tema'] as String? ?? '',
      versao: inteiro(json['versao'], padrao: 1),
      criadoEm: real(json['criado_em']),
      atualizadoEm: real(json['atualizado_em']),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'data': data,
    'horario': horario,
    'pregador': pregador,
    'igreja': igreja,
    'texto_base': textoBase,
    'tema': tema,
    'versao': versao,
  };

  String get rotulo => '$data $horario  $pregador / $igreja';
}
