// A edicao pessoal recebe a conexao MQTT no build. So a aparencia escolhida
// no celular pode sobrescrever esses dados.
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class Configuracao {
  String servidor;
  int porta;
  bool tls;
  String aparelho;
  String usuario;
  String token;
  String logoPath;
  String backgroundPath;
  final bool conexaoFixa;

  Configuracao({
    this.servidor = padraoServidor,
    this.porta = 8883,
    this.tls = true,
    this.aparelho = padraoAparelho,
    this.usuario = 'operador',
    this.token = '',
    this.logoPath = '',
    this.backgroundPath = '',
    this.conexaoFixa = false,
  });

  // O build publico exige um ID informado pelo operador. O ID antigo
  // pregacao-igreja-01 nao identifica o PC ativo e nao deve ser sugerido.
  static const padraoServidor = 'd1901dc1.ala.us-east-1.emqxsl.com';
  static const padraoAparelho = '';

  static const _hostIncorporado = String.fromEnvironment(
    'PREGACAO_MOBILE_HOST',
  );
  static const _portaIncorporada = String.fromEnvironment(
    'PREGACAO_MOBILE_PORT',
  );
  static const _tlsIncorporado = String.fromEnvironment('PREGACAO_MOBILE_TLS');
  static const _aparelhoIncorporado = String.fromEnvironment(
    'PREGACAO_MOBILE_DEVICE_ID',
  );
  static const _usuarioIncorporado = String.fromEnvironment(
    'PREGACAO_MOBILE_USERNAME',
  );
  static const _tokenIncorporado = String.fromEnvironment(
    'PREGACAO_MOBILE_PASSWORD',
  );

  static bool get temConexaoIncorporada =>
      _hostIncorporado.isNotEmpty &&
      _aparelhoIncorporado.isNotEmpty &&
      _tokenIncorporado.isNotEmpty;

  /// Valores incorporados somente ao APK pessoal por --dart-define-from-file.
  /// O build publico continua sem credenciais.
  static Configuracao inicial() {
    return Configuracao(
      servidor: _hostIncorporado.isEmpty ? padraoServidor : _hostIncorporado,
      porta: int.tryParse(_portaIncorporada) ?? 8883,
      tls: _tlsIncorporado.isEmpty ? true : _tlsIncorporado == 'true',
      aparelho: _aparelhoIncorporado.isEmpty
          ? padraoAparelho
          : _aparelhoIncorporado,
      usuario: _usuarioIncorporado.isEmpty ? 'operador' : _usuarioIncorporado,
      token: _tokenIncorporado,
      conexaoFixa: temConexaoIncorporada,
    );
  }

  /// Existe configuracao suficiente para tentar conectar?
  bool get pronto =>
      servidor.trim().isNotEmpty &&
      aparelho.trim().isNotEmpty &&
      token.trim().isNotEmpty;

  bool mesmaConexao(Configuracao outra) =>
      servidor == outra.servidor &&
      porta == outra.porta &&
      tls == outra.tls &&
      aparelho == outra.aparelho &&
      usuario == outra.usuario &&
      token == outra.token;

  /// Migra configuracoes antigas sem reutilizar host, ID ou token salvos.
  static Configuracao comAparenciaSalva(
    Configuracao incorporada,
    Map<String, dynamic> salva,
  ) => Configuracao(
    servidor: incorporada.servidor,
    porta: incorporada.porta,
    tls: incorporada.tls,
    aparelho: incorporada.aparelho,
    usuario: incorporada.usuario,
    token: incorporada.token,
    logoPath: salva['logo_path'] as String? ?? '',
    backgroundPath: salva['background_path'] as String? ?? '',
    conexaoFixa: true,
  );

  Map<String, dynamic> toJson() => {
    'servidor': servidor.trim(),
    'porta': porta,
    'tls': tls,
    'aparelho': aparelho.trim(),
    'usuario': usuario.trim(),
    'token': token,
    'logo_path': logoPath,
    'background_path': backgroundPath,
  };

  factory Configuracao.fromJson(Map<String, dynamic> json) => Configuracao(
    servidor: (json['servidor'] as String?) ?? padraoServidor,
    porta: (json['porta'] as num?)?.toInt() ?? 8883,
    tls: json['tls'] != false,
    aparelho: (json['aparelho'] as String?) ?? padraoAparelho,
    usuario: (json['usuario'] as String?) ?? 'operador',
    token: (json['token'] as String?) ?? '',
    logoPath: (json['logo_path'] as String?) ?? '',
    backgroundPath: (json['background_path'] as String?) ?? '',
  );
}

/// Persistencia protegida (uma entrada so, em JSON).
class ArmazenamentoSeguro {
  static const _chave = 'pregacao_config';
  static const _storage = FlutterSecureStorage();

  Future<Configuracao> carregar() async {
    final incorporada = Configuracao.inicial();
    try {
      final bruto = await _storage.read(key: _chave);
      if (bruto == null || bruto.isEmpty) return incorporada;
      final dados = jsonDecode(bruto);
      if (dados is Map<String, dynamic>) {
        return Configuracao.temConexaoIncorporada
            ? Configuracao.comAparenciaSalva(incorporada, dados)
            : Configuracao.fromJson(dados);
      }
      return incorporada;
    } catch (_) {
      // armazenamento inacessivel (ex.: keystore corrompido): volta ao
      // padrao de fabrica em vez de travar o app
      return incorporada;
    }
  }

  Future<void> salvar(Configuracao cfg) async {
    final dados = Configuracao.temConexaoIncorporada
        ? {'logo_path': cfg.logoPath, 'background_path': cfg.backgroundPath}
        : cfg.toJson();
    await _storage.write(key: _chave, value: jsonEncode(dados));
  }
}
