// Configuracoes do operador: os dados PUBLICOS do servico remoto ja vem de
// fabrica (host, porta, ID) - na pratica quem digita algo novo e so o TOKEN,
// que e credencial e fica gravado no armazenamento protegido do aparelho.
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
  String? _erro;

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
                  'equipamento). Nunca fica no codigo do aplicativo.',
            ),
          ),
          if (_erro != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(_erro!,
                  style: const TextStyle(color: Colors.red, fontSize: 13)),
            ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _salvar,
            child: const Text('SALVAR E CONECTAR'),
          ),
        ],
      ),
    );
  }

  void _salvar() {
    final servidor = _servidor.text.trim();
    final aparelho = _aparelho.text.trim();
    // trim tambem no token: um espaco invisivel (teclado/colar) ja derruba a
    // autenticacao no broker, e o operador jura que digitou a senha certa
    final token = _token.text.trim();
    final porta = int.tryParse(_porta.text.trim()) ?? 0;

    if (servidor.isEmpty || aparelho.isEmpty || token.isEmpty) {
      setState(() => _erro =
          'Servidor, ID do equipamento e token sao obrigatorios.');
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
    );
    // grava no armazenamento protegido e devolve para a tela principal,
    // que ja reconecta com os novos dados
    ArmazenamentoSeguro().salvar(nova);
    Navigator.pop(context, nova);
  }
}
