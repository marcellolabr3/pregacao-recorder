// Configuracoes do operador: a edicao pessoal ja traz a conexao completa;
// alteracoes feitas no celular ficam no armazenamento protegido do aparelho.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'configuracao.dart';

class TelaConfiguracoes extends StatefulWidget {
  final Configuracao atual;

  const TelaConfiguracoes({super.key, required this.atual});

  @override
  State<TelaConfiguracoes> createState() => _TelaConfiguracoesState();
}

class _TelaConfiguracoesState extends State<TelaConfiguracoes> {
  late final TextEditingController _servidor;
  late final TextEditingController _porta;
  late final TextEditingController _aparelho;
  late final TextEditingController _usuario;
  late final TextEditingController _token;
  late bool _tls;
  late String _logoPath;
  late String _backgroundPath;
  String? _erro;
  static const _appearanceChannel = MethodChannel(
    'org.pregacao.pregacao_controle/appearance',
  );

  @override
  void initState() {
    super.initState();
    final cfg = widget.atual;
    _servidor = TextEditingController(text: cfg.servidor);
    _porta = TextEditingController(text: cfg.porta.toString());
    _aparelho = TextEditingController(text: cfg.aparelho);
    _usuario = TextEditingController(text: cfg.usuario);
    _token = TextEditingController(text: cfg.token);
    _tls = cfg.tls;
    _logoPath = cfg.logoPath;
    _backgroundPath = cfg.backgroundPath;
  }

  @override
  void dispose() {
    _servidor.dispose();
    _porta.dispose();
    _aparelho.dispose();
    _usuario.dispose();
    _token.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Configuracoes')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _servidor,
            keyboardType: TextInputType.url,
            decoration: const InputDecoration(
              labelText: 'Servidor (broker MQTT)',
              hintText: Configuracao.padraoServidor,
              helperText: 'Identificador publico do servico remoto.',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _porta,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            decoration: const InputDecoration(
              labelText: 'Porta',
              hintText: '8883',
            ),
          ),
          SwitchListTile(
            title: const Text('Conexao segura (TLS)'),
            value: _tls,
            onChanged: (v) => setState(() => _tls = v),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _aparelho,
            decoration: const InputDecoration(
              labelText: 'ID do equipamento',
              hintText: Configuracao.padraoAparelho,
              helperText: 'Mesmo ID que aparece no painel do equipamento.',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _usuario,
            decoration: const InputDecoration(
              labelText: 'Usuario',
              hintText: 'operador',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _token,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'Token',
              helperText:
                  'Credencial dos operadores (cartao CONTROLE REMOTO do '
                  'equipamento). Na edicao pessoal ja vem preenchida.',
            ),
          ),
          const SizedBox(height: 18),
          FilledButton(
            onPressed: _salvar,
            child: const Text('SALVAR ACESSO E CONECTAR'),
          ),
          const Divider(height: 38),
          const Text(
            'APARENCIA',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          const Text(
            'Escolha imagens do proprio celular. Elas ficam salvas neste aparelho.',
            style: TextStyle(fontSize: 13),
          ),
          const SizedBox(height: 14),
          const Text('Icone na tela do aplicativo'),
          const SizedBox(height: 8),
          if (_logoPath.isNotEmpty) _preview(_logoPath, height: 72, width: 72),
          Wrap(
            spacing: 8,
            children: [
              OutlinedButton.icon(
                onPressed: () => _escolherImagem('logo'),
                icon: const Icon(Icons.image_outlined),
                label: const Text('ESCOLHER ICONE'),
              ),
              if (_logoPath.isNotEmpty)
                TextButton(
                  onPressed: () => setState(() => _logoPath = ''),
                  child: const Text('REMOVER'),
                ),
            ],
          ),
          if (_logoPath.isNotEmpty) ...[
            OutlinedButton.icon(
              onPressed: _criarAtalho,
              icon: const Icon(Icons.add_to_home_screen),
              label: const Text('CRIAR ATALHO COM ESTE ICONE'),
            ),
            const Text(
              'O atalho usa a imagem escolhida na tela inicial. O icone original do APK na lista de aplicativos permanece igual.',
              style: TextStyle(fontSize: 12),
            ),
          ],
          const SizedBox(height: 16),
          const Text('Imagem de fundo'),
          const SizedBox(height: 8),
          if (_backgroundPath.isNotEmpty)
            _preview(_backgroundPath, height: 130, width: double.infinity),
          Wrap(
            spacing: 8,
            children: [
              OutlinedButton.icon(
                onPressed: () => _escolherImagem('background'),
                icon: const Icon(Icons.wallpaper_outlined),
                label: const Text('ESCOLHER FUNDO'),
              ),
              if (_backgroundPath.isNotEmpty)
                TextButton(
                  onPressed: () => setState(() => _backgroundPath = ''),
                  child: const Text('REMOVER'),
                ),
            ],
          ),
          if (_erro != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(
                _erro!,
                style: const TextStyle(color: Colors.red, fontSize: 13),
              ),
            ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _salvar,
            child: const Text('SALVAR APARENCIA'),
          ),
        ],
      ),
    );
  }

  Widget _preview(
    String path, {
    required double height,
    required double width,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(10),
        child: Image.file(
          File(path),
          width: width,
          height: height,
          fit: BoxFit.cover,
          errorBuilder: (_, _, _) => const Text('Imagem indisponivel'),
        ),
      ),
    );
  }

  Future<void> _escolherImagem(String kind) async {
    try {
      final path = await _appearanceChannel.invokeMethod<String>(
        'chooseImage',
        {'kind': kind},
      );
      if (path == null || !mounted) return;
      await FileImage(File(path)).evict();
      setState(() {
        if (kind == 'logo') {
          _logoPath = path;
        } else {
          _backgroundPath = path;
        }
        _erro = null;
      });
    } on PlatformException catch (error) {
      if (mounted) setState(() => _erro = error.message ?? 'Imagem invalida');
    } on MissingPluginException {
      if (mounted) {
        setState(() => _erro = 'Selecao de imagem indisponivel neste aparelho');
      }
    }
  }

  Future<void> _criarAtalho() async {
    try {
      final requested = await _appearanceChannel.invokeMethod<bool>(
        'createShortcut',
        {'path': _logoPath},
      );
      if (!mounted) return;
      if (requested == true) {
        setState(() => _erro = null);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Confirme a criacao do atalho na tela inicial do Android.',
            ),
          ),
        );
      } else {
        setState(
          () => _erro = 'O iniciador nao aceitou o atalho personalizado.',
        );
      }
    } on PlatformException catch (error) {
      if (mounted) {
        setState(() => _erro = error.message ?? 'Atalho indisponivel');
      }
    } on MissingPluginException {
      if (mounted) setState(() => _erro = 'Atalho indisponivel neste aparelho');
    }
  }

  Future<void> _salvar() async {
    final servidor = _servidor.text.trim();
    final aparelho = _aparelho.text.trim();
    // trim tambem no token: um espaco invisivel (teclado/colar) ja derruba a
    // autenticacao no broker, e o operador jura que digitou a senha certa
    final token = _token.text.trim();
    final porta = int.tryParse(_porta.text.trim()) ?? 0;

    if (servidor.isEmpty || aparelho.isEmpty || token.isEmpty) {
      setState(
        () => _erro = 'Servidor, ID do equipamento e token sao obrigatorios.',
      );
      return;
    }
    if (porta < 1 || porta > 65535) {
      setState(() => _erro = 'Porta invalida.');
      return;
    }
    final nova = Configuracao(
      servidor: servidor,
      porta: porta,
      tls: _tls,
      aparelho: aparelho,
      usuario: _usuario.text.trim().isEmpty ? 'operador' : _usuario.text.trim(),
      token: token,
      logoPath: _logoPath,
      backgroundPath: _backgroundPath,
    );
    // grava no armazenamento protegido e devolve para a tela principal,
    // que ja reconecta com os novos dados
    try {
      await ArmazenamentoSeguro().salvar(nova);
      if (mounted) Navigator.pop(context, nova);
    } catch (_) {
      if (mounted) {
        setState(() => _erro = 'Nao foi possivel salvar a configuracao');
      }
    }
  }
}
