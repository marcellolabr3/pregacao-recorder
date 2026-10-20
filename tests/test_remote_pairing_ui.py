"""Pareamento no painel com credenciais sinteticas, sem servicos ou rede."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parent.parent


def test_dados_do_pareamento_exigem_admin_e_nao_incluem_senha_do_pc(monkeypatch):
    from flask import Flask
    from app.api import routes

    monkeypatch.setenv("PREGACAO_PIN", "1234")
    monkeypatch.setenv("PREGACAO_ADMIN_PIN", "5678")
    for key, value in {
        "PREGACAO_REMOTE_HOST": "broker.invalid", "PREGACAO_REMOTE_PORT": "8883",
        "PREGACAO_REMOTE_TLS": "1", "PREGACAO_REMOTE_USERNAME": "pc-sintetico",
        "PREGACAO_REMOTE_PASSWORD": "senha-pc-sintetica",
        "PREGACAO_DEVICE_ID": "pregacao-pc-novo",
        "PREGACAO_OPERATOR_TOKEN": "token-operador-sintetico",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(routes.estudos, "iniciar", lambda: None)
    monkeypatch.setattr(routes.drive, "status", lambda: {})
    monkeypatch.setattr(routes.audio_device, "list_devices", lambda: [])
    monkeypatch.setattr(routes.audio_device, "detect", lambda *_: None)
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="segredo-sintetico")
    routes.register_routes(app, SimpleNamespace(), SimpleNamespace())
    with app.test_client() as client:
        assert client.get("/api/config").status_code == 401
        with client.session_transaction() as session:
            session["auth"] = True
        normal = client.get("/api/config").get_json()
        assert normal["admin"] is False
        assert "remote" not in normal
        assert "token-operador-sintetico" not in str(normal)
        with client.session_transaction() as session:
            session["admin"] = True
        admin = client.get("/api/config").get_json()
        assert admin["remote"]["device_id"] == "pregacao-pc-novo"
        assert admin["remote"]["host"] == "broker.invalid"
        assert admin["remote"]["operator_token"] == "token-operador-sintetico"
        assert "senha-pc-sintetica" not in str(admin)


@pytest.mark.skipif(not shutil.which("node"), reason="Node nao disponivel para UI isolada")
def test_ui_mascara_token_exige_revelacao_e_limpa_ao_sair_do_admin():
    script = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
let source = fs.readFileSync(process.argv[1], 'utf8');
source = source.replace('document.addEventListener("DOMContentLoaded", boot);',
  'window.testUI = {renderRemotePairing, toggleRemoteToken, setView, loadAdvanced, setAdmin: value => {isAdmin = value;}};');
const elements = {};
const element = id => elements[id] || (elements[id] = {
  textContent: '', value: '', type: 'password', disabled: false, attributes: {},
  classList: {toggle: function(name, hidden) {this[name] = hidden;}},
  setAttribute: function(name, value) {this.attributes[name] = value;},
  set innerHTML(value) {throw new Error('HTML nao permitido para dados do pareamento');},
});
const context = {
  document: {getElementById: element, body: {dataset: {view: 'advanced'}}},
  window: {}, history: {replaceState: () => {}}, setInterval: () => {},
};
vm.runInNewContext(source, context);
const ui = context.window.testUI;
const token = element('cfgRemoteToken');
const button = element('btnRemoteToken');
ui.renderRemotePairing({admin: true, remote: {
  device_id: 'pregacao-novo', host: '<img src=x onerror=alert(1)>', port: 8883,
  tls: true, operator_token: 'token-sintetico', enabled: true,
  username: 'pc-sintetico', password_configured: true,
}});
assert.strictEqual(token.type, 'password');
assert.strictEqual(token.value, 'token-sintetico');
assert.strictEqual(element('cfgRemoteHost').textContent, '<img src=x onerror=alert(1)>');
assert.strictEqual(element('cfgRemoteDevice').textContent, 'pregacao-novo');
assert.strictEqual(element('cfgRemoteHostInput').value, '<img src=x onerror=alert(1)>');
assert.strictEqual(element('cfgRemoteUsername').value, 'pc-sintetico');
assert.strictEqual(element('cfgRemotePassword').value, '');
assert.strictEqual(element('cfgRemoteNewToken').value, '');
assert.strictEqual(element('cfgRemoteCard').classList.hidden, false);
ui.toggleRemoteToken();
assert.strictEqual(token.type, 'password');
ui.setAdmin(true);
ui.toggleRemoteToken();
assert.strictEqual(token.type, 'text');
assert.strictEqual(button.attributes['aria-pressed'], 'true');
ui.toggleRemoteToken();
assert.strictEqual(token.type, 'password');
ui.toggleRemoteToken();
element('cfgRemotePassword').value = 'senha-ainda-nao-salva';
element('cfgRemoteNewToken').value = 'token-ainda-nao-salvo';
ui.setView('home');
assert.strictEqual(token.type, 'password');
assert.strictEqual(token.value, '');
assert.strictEqual(button.disabled, true);
assert.strictEqual(element('cfgRemoteCard').classList.hidden, true);
assert.strictEqual(element('cfgRemoteUsername').value, '');
assert.strictEqual(element('cfgRemotePassword').value, '');
assert.strictEqual(element('cfgRemoteNewToken').value, '');
ui.loadAdvanced({admin: false, remote: {operator_token: 'nao-usar'}});
assert.strictEqual(token.value, '');
assert.strictEqual(element('cfgRemoteDevice').textContent, '--');
"""
    result = subprocess.run([shutil.which("node"), "-e", script, str(ROOT / "web/static/app.js")],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not shutil.which("node"), reason="Node nao disponivel para UI isolada")
def test_ui_salva_conexao_com_porta_numerica_e_preserva_segredos_em_branco():
    script = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
let source = fs.readFileSync(process.argv[1], 'utf8');
source = source.replace('document.addEventListener("DOMContentLoaded", boot);',
  'window.testUI = {saveRemoteConfig, renderRemotePairing, setAdmin: value => {isAdmin = value;}};');
const elements = {};
const element = id => elements[id] || (elements[id] = {
  value: '', checked: false, textContent: '', type: 'password', disabled: false,
  classList: {toggle: () => {}}, setAttribute: () => {}, appendChild: () => {},
});
let sent;
const remote = {enabled: true, host: 'broker.invalid', port: 8883, tls: true,
  username: 'pc-teste', device_id: 'pregacao-ui', operator_token: 'token-atual'};
const context = {
  document: {getElementById: element, createElement: () => ({}), body: {dataset: {view: 'advanced'}}},
  window: {}, setInterval: () => {}, setTimeout: () => {},
  fetch: (path, options) => {
    assert.strictEqual(path, '/api/remote/config');
    sent = JSON.parse(options.body);
    assert.strictEqual(typeof sent.port, 'number');
    assert.strictEqual(sent.port, 8883);
    return Promise.resolve({status: 200, ok: true,
      json: () => Promise.resolve({ok: true, remote, message: 'Reinicie o Windows'})});
  },
};
vm.runInNewContext(source, context);
const ui = context.window.testUI;
ui.setAdmin(true);
ui.renderRemotePairing({admin: true, remote});
(async () => {
  await ui.saveRemoteConfig();
  assert.strictEqual(Object.hasOwn(sent, 'password'), false);
  assert.strictEqual(Object.hasOwn(sent, 'operator_token'), false);
  element('cfgRemotePassword').value = ' nova senha ';
  element('cfgRemoteNewToken').value = ' novo-token ';
  await ui.saveRemoteConfig();
  assert.strictEqual(sent.password, ' nova senha ');
  assert.strictEqual(sent.operator_token, 'novo-token');
  assert.strictEqual(element('cfgRemotePassword').value, '');
  assert.strictEqual(element('cfgRemoteNewToken').value, '');
  assert.strictEqual(element('cfgRemoteToken').type, 'password');
  assert.strictEqual(element('cfgRemoteMessage').textContent, 'Reinicie o Windows');
})().catch(error => {process.stderr.write(error.stack); process.exitCode = 1;});
"""
    result = subprocess.run([shutil.which("node"), "-e", script, str(ROOT / "web/static/app.js")],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
