// Configuracao do operador, gravada uma unica vez no celular.
//
// Host, porta e ID do aparelho NAO sao segredos (estao no painel do
// equipamento) e vem de fabrica: na pratica o operador digita so o TOKEN.
// O token e credencial - por isso o armazenamento e protegido (Keystore no
// Android, Keychain no iOS) e ele NUNCA esta no codigo do APK.
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

  Configuracao({
    this.servidor = padraoServidor,
    this.porta = 8883,
    this.tls = true,
    this.aparelho = padraoAparelho,
    this.usuario = 'operador',
    this.token = '',
    this.logoPath = '',
    this.backgroundPath = '',
  });

  // valores de fabrica: identificadores PUBLICOS do servico remoto
  static const padraoServidor = 'd1901dc1.ala.us-east-1.emqxsl.com';
  static const padraoAparelho = 'pregacao-igreja-01';

  /// Existe configuracao suficiente para tentar conectar? Sem token a tela
  /// principal mostra a orientacao, em vez de cair num erro de autenticacao
  /// que nao explica nada.
  bool get pronto =>
      servidor.trim().isNotEmpty &&
      aparelho.trim().isNotEmpty &&
      token.trim().isNotEmpty;

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
    try {
      final bruto = await _storage.read(key: _chave);
      if (bruto == null || bruto.isEmpty) return Configuracao();
      final dados = jsonDecode(bruto);
      if (dados is Map<String, dynamic>) return Configuracao.fromJson(dados);
      return Configuracao();
    } catch (_) {
      // armazenamento inacessivel (ex.: keystore corrompido): volta ao
      // padrao de fabrica em vez de travar o app
      return Configuracao();
    }
  }

  Future<void> salvar(Configuracao cfg) async {
    await _storage.write(key: _chave, value: jsonEncode(cfg.toJson()));
  }
}
