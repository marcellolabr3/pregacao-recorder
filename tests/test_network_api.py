"""Testes da API de rede: protecao, operacoes e recuperacao do Access Point."""
from __future__ import annotations

import json

import pytest

flask = pytest.importorskip("flask")

from app.states import State  # noqa: E402,F401


@pytest.fixture()
def client(fresh_state):
    from app.main import build

    app, manager, uploader = build()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def rede(monkeypatch):
    """Simula a camada NetworkManager e a montagem do status."""
    from app.api import network_routes
    from app.network import nm

    chamadas = {"connect": [], "ap_enable": 0, "ap_disable": 0}
    estado = {"ap_active": False, "wifi_connected": False, "ssid": ""}

    def fake_connect(ssid, password=None, timeout=None):
        chamadas["connect"].append({"ssid": ssid, "password": password})

    def fake_scan(rescan=True):
        return [{"ssid": "Igreja", "signal": 81, "strength": "Forte",
                 "security": "WPA2", "secure": True, "in_use": False}]

    def fake_status(**_kw):
        return {"ethernet": {"connected": True}, "wifi": {"connected": False},
                "internet": {"connected": False},
                "accessPoint": {"active": estado["ap_active"],
                                "ip": "192.168.50.1"},
                "tailscale": {"connected": False}, "online": False,
                "local": True,
                "hostname": "pregacao-pi",
                "access": {"hostname": "pregacao-pi", "port": 8080,
                           "urls": [{"id": "mdns",
                                     "value": "http://pregacao-pi.local:8080"}]}}

    monkeypatch.setattr(network_routes, "build_status", fake_status)
    monkeypatch.setattr(nm, "nmcli_available", lambda: True)
    monkeypatch.setattr(nm, "scan", fake_scan)
    monkeypatch.setattr(nm, "connect", fake_connect)
    monkeypatch.setattr(nm, "disconnect", lambda: None)
    monkeypatch.setattr(nm, "forget", lambda ssid: None)
    monkeypatch.setattr(nm, "wifi_status",
                        lambda: {"connected": estado["wifi_connected"],
                                 "ssid": estado["ssid"], "available": True})
    monkeypatch.setattr(nm, "ap_status",
                        lambda: {"active": estado["ap_active"],
                                 "ip": "192.168.50.1",
                                 "ssid": "PREGACAO-PI-A31F"})

    def fake_ap_enable(timeout=40):
        chamadas["ap_enable"] += 1
        estado["ap_active"] = True

    def fake_ap_disable():
        chamadas["ap_disable"] += 1
        estado["ap_active"] = False

    monkeypatch.setattr(nm, "ap_enable", fake_ap_enable)
    monkeypatch.setattr(nm, "ap_disable", fake_ap_disable)
    chamadas["estado"] = estado
    return chamadas


def _login(client, pin="1234"):
    return client.post("/api/login", json={"pin": pin})


def _admin(client, pin="1234"):
    _login(client)
    return client.post("/api/admin/login", json={"pin": pin})


# --------------------------------------------------------------------------
# protecao
# --------------------------------------------------------------------------
def test_status_exige_login(client, rede):
    assert client.get("/api/network/status").status_code == 401
    assert client.post("/api/network/connectivity-test").status_code == 401
    assert client.get("/api/network/tailscale/status").status_code == 401


def test_scan_e_alteracoes_exigem_pin_de_administrador(client, rede):
    _login(client)
    assert client.get("/api/network/wifi/scan").status_code == 403
    assert client.post("/api/network/wifi/connect",
                       json={"ssid": "Igreja"}).status_code == 403
    assert client.post("/api/network/wifi/disconnect").status_code == 403
    assert client.post("/api/network/wifi/forget",
                       json={"ssid": "Igreja"}).status_code == 403
    assert client.post("/api/network/ap/enable").status_code == 403
    assert client.post("/api/network/ap/disable").status_code == 403
    assert client.post("/api/network/tailscale/login").status_code == 403
    # nada foi executado na camada de rede
    assert rede["connect"] == []
    assert rede["ap_enable"] == 0


def test_nada_e_executado_sem_login(client, rede):
    assert client.post("/api/network/wifi/connect",
                       json={"ssid": "Igreja"}).status_code == 401
    assert client.post("/api/network/ap/enable").status_code == 401
    assert rede["connect"] == []
    assert rede["ap_enable"] == 0


# --------------------------------------------------------------------------
# leitura
# --------------------------------------------------------------------------
def test_status_devolve_todos_os_blocos(client, rede):
    _login(client)
    data = client.get("/api/network/status").get_json()
    for chave in ("ethernet", "wifi", "internet", "accessPoint", "tailscale",
                  "access", "online", "local"):
        assert chave in data
    assert "senha" not in json.dumps(data).lower()


def test_scan_devolve_rede_ordenada(client, rede):
    _admin(client)
    data = client.get("/api/network/wifi/scan").get_json()
    assert data["count"] == 1
    assert data["networks"][0]["ssid"] == "Igreja"
    assert data["networks"][0]["strength"] == "Forte"
    assert "password" not in json.dumps(data).lower()


def test_teste_de_conexao_para_usuario_comum(client, rede, monkeypatch):
    from app.network import connectivity

    monkeypatch.setattr(connectivity, "check",
                        lambda timeout=4.0: {"connected": True, "host": "x",
                                             "port": 443, "latency_ms": 5})
    _login(client)
    data = client.post("/api/network/connectivity-test").get_json()
    assert data["connected"] is True
    assert "seconds" in data


# --------------------------------------------------------------------------
# conectar / desconectar / esquecer
# --------------------------------------------------------------------------
def test_conectar_wifi_como_admin(client, rede):
    _admin(client)
    resp = client.post("/api/network/wifi/connect",
                       json={"ssid": "Igreja", "password": "senha-segura-123"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["ssid"] == "Igreja"
    # a senha nunca volta para a interface
    assert "senha-segura-123" not in json.dumps(data)
    assert rede["connect"][0]["password"] == "senha-segura-123"


def test_conectar_sem_ssid_e_recusado(client, rede):
    _admin(client)
    resp = client.post("/api/network/wifi/connect", json={"ssid": ""})
    assert resp.status_code == 400
    assert rede["connect"] == []


def test_falha_de_conexao_devolve_erro_legivel(client, rede, monkeypatch):
    from app.network import nm

    def quebra(ssid, password=None, timeout=None):
        raise nm.NetworkError("senha incorreta para essa rede Wi-Fi")

    monkeypatch.setattr(nm, "connect", quebra)
    _admin(client)
    resp = client.post("/api/network/wifi/connect",
                       json={"ssid": "Igreja", "password": "errada12345"})
    assert resp.status_code == 409
    assert "senha incorreta" in resp.get_json()["message"]


def test_desconectar_e_esquecer(client, rede):
    _admin(client)
    assert client.post("/api/network/wifi/disconnect").status_code == 200
    resp = client.post("/api/network/wifi/forget", json={"ssid": "Igreja"})
    assert resp.status_code == 200
    assert resp.get_json()["ssid"] == "Igreja"


# --------------------------------------------------------------------------
# Access Point: o usuario nunca pode ficar sem acesso
# --------------------------------------------------------------------------
def test_ativar_modo_de_configuracao_persiste_a_intencao(client, rede, cfg):
    _admin(client)
    resp = client.post("/api/network/ap/enable")
    assert resp.status_code == 200
    assert rede["ap_enable"] == 1
    # persistido: se o Raspberry reiniciar, o watchdog mantem o AP
    assert cfg.get("network.ap_forced") is True
    assert rede["estado"]["ap_active"] is True


def test_desativar_modo_de_configuracao(client, rede, cfg):
    _admin(client)
    client.post("/api/network/ap/enable")
    resp = client.post("/api/network/ap/disable")
    assert resp.status_code == 200
    assert cfg.get("network.ap_forced") is False
    assert rede["estado"]["ap_active"] is False


def test_falha_ao_ativar_ap_nao_deixa_intencao_pendente(client, rede, cfg,
                                                        monkeypatch):
    from app.network import nm

    def falha(timeout=40):
        raise nm.NetworkError("interface ocupada")

    monkeypatch.setattr(nm, "ap_enable", falha)
    _admin(client)
    resp = client.post("/api/network/ap/enable")
    assert resp.status_code == 409
    assert cfg.get("network.ap_forced") is False


def test_conectar_partindo_do_ap_baixa_o_ap_e_conecta(client, rede, cfg):
    """Cenario do item 5: celular no AP configurando o Wi-Fi da igreja."""
    _admin(client)
    client.post("/api/network/ap/enable")
    rede["estado"]["ap_active"] = True

    resp = client.post("/api/network/wifi/connect",
                       json={"ssid": "Igreja", "password": "senha-segura-123"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ap_disabled"] is True
    assert rede["ap_disable"] >= 1          # radio libertado antes de conectar
    assert rede["estado"]["ap_active"] is False
    # apos conectar, o AP deixa de ser forcado (volta ao modo normal)
    assert cfg.get("network.ap_forced") is False
    assert "celular" in data["message"]     # avisa que o AP caiu


def test_senha_errada_no_ap_devolve_o_ap(client, rede, cfg, monkeypatch):
    """Item 5: senha incorreta NAO deixa o Raspberry inacessivel."""
    from app.network import nm

    def quebra(ssid, password=None, timeout=None):
        raise nm.NetworkError("senha incorreta para essa rede Wi-Fi")

    monkeypatch.setattr(nm, "connect", quebra)
    _admin(client)
    client.post("/api/network/ap/enable")
    rede["estado"]["ap_active"] = True
    ligado = rede["ap_enable"]

    resp = client.post("/api/network/wifi/connect",
                       json={"ssid": "Igreja", "password": "errada12345"})
    assert resp.status_code == 409
    # o AP foi restaurado: o usuario continua com um caminho de acesso
    assert rede["estado"]["ap_active"] is True
    assert rede["ap_enable"] == ligado + 1


def test_operacoes_rede_nao_se_empilham(client, rede, monkeypatch):
    """Duas alteracoes simultaneas: a segunda recebe 409, nao corrompe estado."""
    from app.api import network_routes
    from app.network import nm

    chamadas = []
    monkeypatch.setattr(nm, "connect",
                        lambda ssid, password=None, timeout=None:
                        chamadas.append(ssid))
    _admin(client)

    # simula uma operacao em andamento segurando o lock
    assert network_routes._lock.acquire(blocking=False)
    try:
        segunda = client.post("/api/network/wifi/connect", json={"ssid": "DEUS"})
    finally:
        network_routes._lock.release()

    assert segunda.status_code == 409
    assert segunda.get_json()["error"] == "ocupado"
    assert chamadas == []                 # nada foi executado em paralelo


# --------------------------------------------------------------------------
# Tailscale
# --------------------------------------------------------------------------
def test_tailscale_login_exige_admin(client, rede):
    _login(client)
    assert client.post("/api/network/tailscale/login").status_code == 403


def test_tailscale_status_para_usuario_comum(client, rede, monkeypatch):
    from app.network import tailscale

    monkeypatch.setattr(tailscale, "status",
                        lambda: {"installed": True, "connected": False,
                                 "ip": "", "message": "autenticacao pendente",
                                 "auth_url": ""})
    _login(client)
    data = client.get("/api/network/tailscale/status").get_json()
    assert data["installed"] is True
    assert data["connected"] is False


def test_tailscale_testar_acesso_remoto(client, rede, monkeypatch):
    from app.network import tailscale

    monkeypatch.setattr(tailscale, "status",
                        lambda: {"installed": True, "connected": True,
                                 "ip": "100.64.0.9", "hostname": "pregacao-pi",
                                 "message": "", "auth_url": ""})
    _admin(client)
    data = client.post("/api/network/tailscale/test").get_json()
    assert data["ok"] is True
    assert "100.64.0.9" in data["message"]
