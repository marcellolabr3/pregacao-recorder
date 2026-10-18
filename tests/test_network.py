"""Testes da camada de rede.

Nada aqui toca na rede real: o ``nmcli`` e simulado, o que permite rodar os
testes em qualquer maquina (inclusive no Windows, onde nao existe nmcli).
"""
from __future__ import annotations

import json
import logging
import time

import pytest

from app.network import connectivity, nm, tailscale
from app.network.watchdog import (
    AP_AFTER_NO_NETWORK,
    AP_AFTER_WIFI_FAIL,
    Watchdog,
    evaluate,
)


# ==========================================================================
# decisao do watchdog (funcao pura)
# ==========================================================================
def _ev(**kw):
    base = dict(
        eth_connected=False,
        wifi_connected=False,
        ap_active=False,
        ap_forced=False,
        seconds_degraded=0.0,
        has_saved_wifi=False,
    )
    base.update(kw)
    return evaluate(**base)


def test_sem_rede_ainda_nao_sobe_ap():
    """Antes do tempo de tolerancia o AP nao sobe (evita flapping)."""
    assert _ev(seconds_degraded=1) == "keep"
    assert _ev(seconds_degraded=AP_AFTER_NO_NETWORK - 1) == "keep"


def test_sem_rede_apos_tolerancia_sobe_ap():
    assert _ev(seconds_degraded=AP_AFTER_NO_NETWORK) == "ap_on"


def test_wifi_salvo_falhando_tem_tolerancia_maior():
    """Rede conhecida em retry recebe mais tempo antes do AP de emergencia."""
    assert _ev(has_saved_wifi=True,
               seconds_degraded=AP_AFTER_NO_NETWORK) == "keep"
    assert _ev(has_saved_wifi=True,
               seconds_degraded=AP_AFTER_WIFI_FAIL) == "ap_on"


def test_ethernet_funcional_mantem_ap_desligado():
    assert _ev(eth_connected=True, ap_active=True) == "ap_off"
    assert _ev(eth_connected=True) == "keep"


def test_wifi_funcional_mantem_ap_desligado():
    assert _ev(wifi_connected=True, ap_active=True) == "ap_off"
    assert _ev(wifi_connected=True) == "keep"


def test_ap_de_recuperacao_ja_ativo_nao_pisca():
    """AP ativo sem rede: nada a fazer (nao liga/desliga em loop)."""
    assert _ev(ap_active=True, seconds_degraded=999) == "keep"


def test_ap_forcado_pelo_painel_sobe_mesmo_com_rede():
    assert _ev(ap_forced=True, eth_connected=True) == "ap_on"
    assert _ev(ap_forced=True, ap_active=True) == "keep"


def test_watchdog_derruba_ap_quando_a_rede_volta():
    """Fora do modo forcado, rede voltando derruba o AP (volta ao normal)."""
    assert _ev(ap_forced=False, eth_connected=True, ap_active=True) == "ap_off"


# ==========================================================================
# nmcli (simulado)
# ==========================================================================
@pytest.fixture()
def nmcli(monkeypatch):
    """Substitui nm.run por um gravador com respostas em fila.

    Cada resposta e uma tupla ``(codigo, stdout[, stderr])``.
    """
    state = {"responses": [], "calls": []}

    def respond(*respostas):
        for item in respostas:
            tupla = tuple(item) if not isinstance(item, str) else (0, item, "")
            if len(tupla) == 2:
                tupla = (tupla[0], tupla[1], "")
            state["responses"].append(tupla)

    def fake_run(args, timeout=nm.NM_TIMEOUT, stdin=None):
        state["calls"].append({"args": list(args), "stdin": stdin,
                               "timeout": timeout})
        if state["responses"]:
            return state["responses"].pop(0)
        return 0, "", ""

    monkeypatch.setattr(nm, "run", fake_run)
    monkeypatch.setattr(nm, "nmcli_available", lambda: True)
    state["respond"] = respond
    return state


@pytest.fixture()
def logs(caplog, monkeypatch):
    """Capta logs mesmo com propagate=False do logging_setup."""
    monkeypatch.setattr(logging.getLogger("pregacao"), "propagate", True)
    return caplog


# ==========================================================================
# parsing do nmcli
# ==========================================================================
def test_rows_respeita_escape_de_dois_pontos():
    rows = nm._rows("rede:com:dois-pontos:77\nnormal:80:WPA2::Infra\n")
    assert rows[0] == ["rede", "com", "dois-pontos", "77"]
    assert rows[1] == ["normal", "80", "WPA2", "", "Infra"]


def test_scan_ignora_ssid_oculto_e_ordena_por_sinal(nmcli):
    nmcli["respond"]((0,
        "Visitantes:20:WPA2::Infra\n"
        ":0:::Infra\n"                      # SSID oculto: descartado
        "Os Labres:77:WPA1 WPA2:*:Infra\n"
        "Os Labres:45:WPA1 WPA2::Infra\n"   # duplicata: fica a melhor
        "DEUS:34:WPA2::Infra\n"))
    nets = nm.scan()
    assert [n["ssid"] for n in nets] == ["Os Labres", "DEUS", "Visitantes"]
    assert nets[0]["signal"] == 77
    assert nets[0]["in_use"] is True
    assert nets[0]["secure"] is True
    assert nets[0]["strength"] == "Forte"
    assert nets[2]["strength"] == "Fraco"
    # senha ou chave jamais aparecem no scan
    texto = json.dumps(nets).lower()
    assert "psk" not in texto and "password" not in texto


def test_scan_sem_permissao_devolve_lista_vazia(nmcli, logs):
    nmcli["respond"]((1, "", "Error: not authorized."))
    with logs.at_level("WARNING"):
        assert nm.scan() == []
    assert any("scan" in r.message.lower() for r in logs.records)


def test_scan_deve_pedir_rescan_quando_solicitado(nmcli):
    nmcli["respond"]((0, ""))
    nm.scan(rescan=True)
    args = nmcli["calls"][0]["args"]
    assert args[args.index("--rescan") + 1] == "yes"


def test_ethernet_status_com_ip_e_gateway(nmcli):
    nmcli["respond"](
        (0, "eth0:ethernet:connected:Wired connection 1\n"
            "wlan0:wifi:disconnected:\n"
            "lo:loopback:connected:lo\n"),
        (0, "192.168.100.6/24\n"),
        (0, "192.168.100.1\n"),
    )
    eth = nm.ethernet_status()
    assert eth["connected"] is True
    assert eth["ip"] == "192.168.100.6"
    assert eth["gateway"] == "192.168.100.1"
    # loopback nunca aparece como interface real
    assert all(d["type"] != "loopback" for d in nm.devices())


def test_wifi_status_mostra_rede_sinal_e_seguranca(nmcli):
    nmcli["respond"](
        (0, "eth0:ethernet:connected:Wired connection 1\n"
            "wlan0:wifi:connected:Igreja\n"),
        (0, "192.168.1.73/24\n"),
        (0, "192.168.1.1\n"),
        (0, "Igreja:81:WPA2:*:Infra\n"),
    )
    wifi = nm.wifi_status()
    assert wifi["connected"] is True
    assert wifi["ssid"] == "Igreja"
    assert wifi["ip"] == "192.168.1.73"
    assert wifi["gateway"] == "192.168.1.1"
    assert wifi["signal"] == 81
    assert wifi["security"] == "WPA2"


def test_wifi_status_nao_conta_o_proprio_ap_como_conectado(nmcli):
    """O NM marca o AP como 'conectado'; isso nao vira Wi-Fi de cliente.

    Sem essa separacao o watchdog desligaria o AP de recuperacao achando que
    ha rede boa, e o painel mostraria Wi-Fi conectado em "pregacao-ap".
    """
    nmcli["respond"](
        (0, "eth0:ethernet:connected:Wired connection 1\n"
            f"wlan0:wifi:connected:{nm.AP_PROFILE}\n"),
        (0, "enabled\n"),
    )
    wifi = nm.wifi_status()
    assert wifi["connected"] is False
    assert wifi["ssid"] == ""
    assert wifi["ip"] == ""
    assert wifi["state"] == "emitindo AP"


# ==========================================================================
# Wi-Fi: conectar / desconectar / esquecer
# ==========================================================================
def test_conectar_envia_senha_por_stdin_e_nao_por_argumento(nmcli):
    nmcli["respond"]((0, "Device 'wlan0' successfully activated.\n"))
    nm.connect("Igreja", "senha-segura-123")
    chamada = nmcli["calls"][0]
    assert chamada["stdin"] == "senha-segura-123\n"
    assert "--ask" in chamada["args"]
    assert "senha-segura-123" not in " ".join(chamada["args"])


def test_conectar_rejeita_senha_curta_sem_chamar_nmcli(nmcli):
    with pytest.raises(nm.NetworkError):
        nm.connect("Igreja", "curta")
    assert nmcli["calls"] == []


def test_conectar_rejeita_ssid_invalido(nmcli):
    with pytest.raises(nm.NetworkError):
        nm.connect("", "senha-segura-123")
    with pytest.raises(nm.NetworkError):
        nm.connect("-rf", "senha-segura-123")
    with pytest.raises(nm.NetworkError):
        nm.connect("x" * 33, "senha-segura-123")
    assert nmcli["calls"] == []


def test_falha_de_conexao_registra_wifi_connection_failed(nmcli, logs):
    nmcli["respond"]((1, "", "Error: Connection activation failed"))
    with logs.at_level("WARNING"):
        with pytest.raises(nm.NetworkError):
            nm.connect("Os Labres", "senha-segura-123")
    assert any("Wi-Fi connection failed" in r.message for r in logs.records)


def test_forget_nao_aceita_perfil_que_nao_seja_wifi(nmcli):
    nmcli["respond"]((0, "Wired connection 1:802-3-ethernet\n"
                         "Os Labres:802-11-wireless\n"
                         "pregacao-ap:802-11-wireless\n"),
                     (0, ""))
    with pytest.raises(nm.NetworkError):
        nm.forget("Wired connection 1")     # ethernet: bloqueado
    with pytest.raises(nm.NetworkError):
        nm.forget(nm.AP_PROFILE)            # AP de recuperacao: bloqueado
    # rede sem perfil nenhum nao e erro (nao ha o que apagar)
    nm.forget("Inexistente")


def test_forget_apaga_apenas_o_perfil_wifi(nmcli):
    nmcli["respond"]((0, "Os Labres:802-11-wireless\n"), (0, ""))
    nm.forget("Os Labres")
    assert nmcli["calls"][-1]["args"] == ["con", "delete", "id", "Os Labres"]


def test_saved_wifi_ignora_o_perfil_do_ap(nmcli):
    nmcli["respond"]((0, "Wired connection 1:802-3-ethernet\n"
                         "Igreja:802-11-wireless\n"
                         "pregacao-ap:802-11-wireless\n"))
    assert nm.saved_wifi() == ["Igreja"]


# ==========================================================================
# Access Point de configuracao
# ==========================================================================
def test_ap_status_inativo(nmcli):
    nmcli["respond"]((0, "Wired connection 1:802-3-ethernet:eth0\n"),
                     (0, "eth0:ethernet:connected:Wired connection 1\n"
                         "wlan0:wifi:disconnected:\n"))
    status = nm.ap_status()
    assert status["active"] is False
    assert status["ip"] == "192.168.50.1"
    assert status["state"] == "inativo"


def test_ap_status_ativo(nmcli):
    nmcli["respond"]((0, f"{nm.AP_PROFILE}:802-11-wireless:wlan0\n"),
                     (0, "wlan0:wifi:connected:pregacao-ap\n"))
    status = nm.ap_status()
    assert status["active"] is True
    assert status["state"] == "ativo"


def test_ap_enable_cria_perfil_e_sobe(nmcli):
    # 1) AP ativo?  2) perfil existe?  3) interface wifi  4) cria  5) sobe
    nmcli["respond"]((0, ""), (0, ""), (0, ""), (0, ""), (0, ""))
    nm.ap_enable()
    args = [c["args"] for c in nmcli["calls"]]
    criar = next(a for a in args if a[:2] == ["con", "add"])
    assert criar[:4] == ["con", "add", "type", "wifi"]
    assert "802-11-wireless.mode" in criar and "ap" in criar
    assert "ipv4.method" in criar and "shared" in criar
    assert "192.168.50.1/24" in criar
    # WPA2 com 802.11w (PMF) DESLIGADO: o driver Broadcom do Raspberry Pi
    # recusa a chave IGTK e o hotspot nunca subia (raspberrypi/linux#7247).
    assert criar[criar.index("802-11-wireless-security.pmf") + 1] == "1"
    assert criar[criar.index("802-11-wireless-security.key-mgmt") + 1] == "wpa-psk"
    # a senha vai por stdin, nunca como argumento
    senha = nm.ap_passphrase()
    assert all(senha not in " ".join(a) for a in args)
    subir = next(c for c in nmcli["calls"] if c["args"][:2] == ["--ask", "con"])
    assert subir["args"] == ["--ask", "con", "up", nm.AP_PROFILE]
    assert subir["stdin"] == f"{senha}\n" * 3
    assert args[-1] == ["--ask", "con", "up", nm.AP_PROFILE]


def test_ap_enable_recria_perfil_existente(nmcli):
    """Perfil antigo some e renasce com o .env vigente (sem ler a senha)."""
    nmcli["respond"]((0, ""), (0, f"{nm.AP_PROFILE}:802-11-wireless\n"),
                     (0, "wlan0:wifi:disconnected\n"), (0, ""), (0, ""), (0, ""))
    nm.ap_enable()
    args = [c["args"] for c in nmcli["calls"]]
    assert args[2][:3] == ["con", "delete", "id"]
    assert any(a[:2] == ["con", "add"] for a in args)
    assert not any(a[:2] == ["con", "modify"] for a in args)
    assert args[-1] == ["--ask", "con", "up", nm.AP_PROFILE]


def test_ap_enable_ja_ativo_nao_mexe_no_perfil(nmcli):
    """Chamar de novo com o AP ligado nao derruba a conexao do usuario."""
    nmcli["respond"]((0, f"{nm.AP_PROFILE}:802-11-wireless\n"))
    nm.ap_enable()
    args = [c["args"] for c in nmcli["calls"]]
    assert len(args) == 1
    assert not any(a[:2] == ["con", "add"] for a in args)


def test_ap_enable_tenta_de_novo_se_a_ativacao_falhar(nmcli):
    """Senha ja gravada: uma falha transitorio nao desiste do AP."""
    nmcli["respond"]((0, ""), (0, ""), (0, ""), (0, ""),
                     (1, "", "interface ocupada"), (0, ""))
    nm.ap_enable()
    args = [c["args"] for c in nmcli["calls"]]
    assert args[-2][:2] == ["--ask", "con"]
    assert args[-1] == ["con", "up", nm.AP_PROFILE]


def test_ap_enable_nunca_devolve_a_senha_em_erro(nmcli):
    senha = nm.ap_passphrase()
    nmcli["respond"]((0, ""), (0, ""), (0, ""), (0, ""),
                     (1, "", f"falhou com {senha}"),
                     (1, "", f"falhou de novo {senha}"))
    with pytest.raises(nm.NetworkError) as erro:
        nm.ap_enable()
    assert senha not in str(erro.value)
    assert "***" in str(erro.value)


def test_ap_enable_sem_nmcli_levanta_erro_claro(monkeypatch):
    monkeypatch.setattr(nm, "nmcli_available", lambda: False)
    with pytest.raises(nm.NetworkError) as erro:
        nm.ap_enable()
    assert "nmcli" in str(erro.value)


def test_ap_ssid_tem_formato_unico():
    ssid = nm.ap_ssid()
    assert ssid.startswith("PREGACAO-PI-")
    assert len(ssid) == len("PREGACAO-PI-") + 4


def test_senha_padrao_do_ap_e_valida_para_wpa2():
    senha = nm.ap_passphrase()
    assert 8 <= len(senha) <= 63


def test_mensagens_de_log_no_formato_do_projeto():
    """Item 19 da arquitetura: tags [NETWORK]/[TAILSCALE] exatamente assim."""
    from app.network.watchdog import (
        MSG_ETHERNET_ON,
        MSG_INET_OFF,
        MSG_INET_ON,
        MSG_TS_OFF,
        MSG_TS_ON,
        MSG_WIFI_OFF,
    )

    assert MSG_ETHERNET_ON == "[NETWORK] Ethernet connected"
    assert MSG_INET_ON == "[NETWORK] Internet available"
    assert MSG_INET_OFF == "[NETWORK] Internet unavailable"
    assert MSG_TS_ON == "[TAILSCALE] Connected"
    assert MSG_TS_OFF == "[TAILSCALE] Disconnected"
    assert MSG_WIFI_OFF == "[NETWORK] Wi-Fi disconnected"
    assert nm.MSG_AP_STARTING == "[NETWORK] Starting configuration AP"
    assert nm.MSG_AP_ACTIVE == "[NETWORK] Configuration AP active"
    assert nm.MSG_AP_STOPPING == "[NETWORK] Stopping configuration AP"
    assert nm.MSG_WIFI_FAILED == "[NETWORK] Wi-Fi connection failed"


# ==========================================================================
# status geral
# ==========================================================================
def _stub_status(monkeypatch, *, eth, wifi, ap, internet):
    from app.network.status import build

    monkeypatch.setattr(nm, "ethernet_status", lambda: eth)
    monkeypatch.setattr(nm, "wifi_status", lambda: wifi)
    monkeypatch.setattr(nm, "ap_status", lambda: ap)
    monkeypatch.setattr(nm, "has_default_route", lambda: True)
    monkeypatch.setattr(connectivity, "check", lambda timeout=4.0: internet)
    monkeypatch.setattr(tailscale, "status", lambda: {
        "installed": True, "connected": True, "ip": "100.64.0.2",
        "hostname": "pregacao-pi", "message": "",
    })
    return build


def test_status_build_nao_devolve_segredos(monkeypatch):
    build = _stub_status(
        monkeypatch,
        eth={"connected": True, "ip": "10.0.0.2", "gateway": "10.0.0.1",
             "available": True, "state": "conectado", "device": "eth0"},
        wifi={"connected": True, "ssid": "Igreja", "ip": "10.0.0.3",
              "signal": 77, "gateway": "10.0.0.1", "available": True,
              "state": "conectado", "device": "wlan0", "security": "WPA2"},
        ap={"active": False, "ssid": "PREGACAO-PI-A31F",
            "ip": "192.168.50.1", "state": "inativo"},
        internet={"connected": True, "host": "x", "port": 443,
                  "latency_ms": 12},
    )

    payload = build()
    for chave in ("ethernet", "wifi", "internet", "accessPoint", "tailscale",
                  "access", "online", "local", "hostname", "has_route"):
        assert chave in payload, f"chave ausente: {chave}"

    texto = json.dumps(payload).lower()
    for proibido in ("psk", "password", "senha", "client_secret"):
        assert proibido not in texto, f"segredo vazou no status: {proibido}"

    # todos os caminhos de acesso aparecem no painel
    urls = {u["id"]: u["value"] for u in payload["access"]["urls"]}
    assert "ethernet" in urls and "wifi" in urls and "tailscale" in urls
    assert urls["tailscale"].startswith("http://100.64.0.2:")
    assert payload["has_route"] is True


def test_status_build_quando_so_existe_o_ap(monkeypatch):
    build = _stub_status(
        monkeypatch,
        eth={"connected": False, "ip": "", "gateway": "", "available": True,
             "state": "desconectado", "device": "eth0"},
        wifi={"connected": False, "ssid": "", "ip": "", "gateway": "",
              "signal": 0, "available": True, "state": "desconectado",
              "device": "wlan0"},
        ap={"active": True, "ssid": "PREGACAO-PI-A31F", "ip": "192.168.50.1",
            "state": "ativo"},
        internet={"connected": False, "host": "", "port": 0,
                  "latency_ms": 0},
    )

    payload = build(with_internet=True, timeout=0.1)
    assert payload["online"] is False
    assert payload["local"] is True          # o AP conta como caminho local
    urls = {u["id"] for u in payload["access"]["urls"]}
    assert "ap" in urls and "ethernet" not in urls


# ==========================================================================
# ciclo do watchdog (com nm simulado)
# ==========================================================================
def _wd(monkeypatch, offline=False):
    monkeypatch.setattr(nm, "ethernet_status",
                        lambda: {"connected": not offline})
    monkeypatch.setattr(nm, "wifi_status",
                        lambda: {"connected": False, "ssid": ""})
    monkeypatch.setattr(nm, "ap_status", lambda: {"active": False})
    monkeypatch.setattr(nm, "saved_wifi", lambda: [])
    monkeypatch.setattr(connectivity, "check",
                        lambda timeout=4.0: {"connected": not offline})
    monkeypatch.setattr(tailscale, "status",
                        lambda: {"connected": False, "message": ""})
    return Watchdog(interval=5, test_mode="offline" if offline else "normal")


def test_watchdog_com_ethernet_nao_mexe_no_ap(monkeypatch):
    chamadas = []
    monkeypatch.setattr(nm, "ap_enable", lambda **kw: chamadas.append("on"))
    monkeypatch.setattr(nm, "ap_disable", lambda: chamadas.append("off"))
    wd = _wd(monkeypatch)
    resultado = wd.cycle()
    assert resultado["action"] == "keep"
    assert chamadas == []
    assert resultado["ethernet"] is True


def test_watchdog_le_a_flag_depois_dos_testes_de_rede(monkeypatch):
    """A flag do modo de configuracao e lida por ultimo, ja na hora da acao.

    O administrador pode ligar (ou desligar) o modo pelo celular enquanto o
    ciclo roda; com a leitura no inicio, o AP recem-ligado seria derrubado
    (ou o recem-desligado religado) na mesma volta, fazendo o celular
    desconectar no meio da configuracao.
    """
    from app.config import config

    ordem = []
    original = config.get

    def get(chave, padrao=None):
        if chave == "network.ap_forced":
            ordem.append("flag")
        return original(chave, padrao)

    monkeypatch.setattr(config, "get", get)
    wd = _wd(monkeypatch)
    monkeypatch.setattr(
        connectivity, "check",
        lambda timeout=4.0: (ordem.append("internet"), {"connected": True})[-1])
    wd.cycle()
    assert ordem == ["internet", "flag"], (
        "a flag foi lida antes dos testes de rede: ha corrida com o painel")


def test_watchdog_sem_rede_apos_tolerancia_sobe_ap(monkeypatch):
    ligado = []
    monkeypatch.setattr(nm, "ap_enable", lambda **kw: ligado.append(True))
    wd = _wd(monkeypatch, offline=True)
    wd._degraded_since = time.monotonic() - (AP_AFTER_NO_NETWORK + 5)
    resultado = wd.cycle()
    assert resultado["action"] == "ap_on"
    assert ligado == [True]


def test_watchdog_antes_da_tolerancia_nao_sobe_ap(monkeypatch):
    ligado = []
    monkeypatch.setattr(nm, "ap_enable", lambda **kw: ligado.append(True))
    wd = _wd(monkeypatch, offline=True)
    wd._degraded_since = time.monotonic() - 1
    assert wd.cycle()["action"] == "keep"
    assert ligado == []


def test_watchdog_rede_volta_derruba_o_ap(monkeypatch):
    desligado = []
    wd = _wd(monkeypatch, offline=False)
    monkeypatch.setattr(nm, "ap_status", lambda: {"active": True})
    monkeypatch.setattr(nm, "ap_disable", lambda: desligado.append(True))
    resultado = wd.cycle()
    assert resultado["action"] == "ap_off"
    assert desligado == [True]


def test_watchdog_loga_wifi_conectado_sem_quebrar_o_formato(logs, monkeypatch):
    """A mensagem de Wi-Fi usa {}: passar argumento ao logging perdia a linha.

    O format do logging e printf (%%), entao `log.info(msg, ssid)` levantava
    TypeError dentro do RotatingFileHandler e a linha nunca chegava ao journal.
    """
    monkeypatch.setattr(nm, "ethernet_status", lambda: {"connected": False})
    monkeypatch.setattr(nm, "wifi_status",
                        lambda: {"connected": True, "ssid": "rede 100%"})
    monkeypatch.setattr(nm, "ap_status", lambda: {"active": False})
    monkeypatch.setattr(nm, "saved_wifi", lambda: ["rede 100%"])
    monkeypatch.setattr(connectivity, "check",
                        lambda timeout=4.0: {"connected": True})
    monkeypatch.setattr(tailscale, "status",
                        lambda: {"connected": False, "message": ""})
    with logs.at_level(logging.INFO, logger="pregacao.network"):
        Watchdog(interval=5).cycle()
    linhas = [registro.getMessage() for registro in logs.records]
    assert "[NETWORK] Wi-Fi connected: rede 100%" in linhas
    assert all("TypeError" not in linha for linha in linhas)


def test_watchdog_registra_transicoes_uma_vez(monkeypatch, logs):
    monkeypatch.setattr(nm, "ap_enable", lambda **kw: None)
    wd = _wd(monkeypatch, offline=True)
    wd._degraded_since = time.monotonic() - (AP_AFTER_NO_NETWORK + 5)
    with logs.at_level(logging.INFO):
        wd.cycle()
        wd.cycle()   # segundo ciclo: nao repete as transicoes
    mensagens = [r.message for r in logs.records]
    assert mensagens.count("[NETWORK] Ethernet disconnected") == 1
    assert "[NETWORK] Internet unavailable" in mensagens
    assert "[TAILSCALE] Disconnected" in mensagens
    # sem rede salva nao ha falha de Wi-Fi a reportar
    assert not any("Wi-Fi connection failed" in m for m in mensagens)


def test_watchdog_reporta_falha_de_wifi_salvo_antes_do_ap(monkeypatch, logs):
    monkeypatch.setattr(nm, "ap_enable", lambda **kw: None)
    wd = _wd(monkeypatch, offline=True)
    monkeypatch.setattr(nm, "saved_wifi", lambda: ["Igreja"])
    wd._degraded_since = time.monotonic() - (AP_AFTER_WIFI_FAIL + 5)
    with logs.at_level(logging.INFO):
        wd.cycle()
    assert any("Wi-Fi connection failed" in r.message for r in logs.records)


# ==========================================================================
# Tailscale
# ==========================================================================
def test_tailscale_status_sem_instalacao(monkeypatch):
    monkeypatch.setattr(tailscale, "installed", lambda: False)
    info = tailscale.status()
    assert info["installed"] is False
    assert info["connected"] is False
    assert info["ip"] == ""


def test_tailscale_status_ignora_json_invalido(monkeypatch):
    monkeypatch.setattr(tailscale, "installed", lambda: True)
    monkeypatch.setattr(tailscale, "_sudo",
                        lambda args, timeout=30: (0, "lixo", ""))
    info = tailscale.status()
    assert info["connected"] is False
    assert info["message"]


def test_tailscale_status_legivel(monkeypatch):
    monkeypatch.setattr(tailscale, "installed", lambda: True)
    payload = json.dumps({
        "BackendState": "Running",
        "AuthURL": "",
        "Self": {"HostName": "pregacao-pi",
                 "DNSName": "pregacao-pi.tail.ts.net.",
                 "TailscaleIPs": ["100.64.0.2"], "Online": True},
    })
    monkeypatch.setattr(tailscale, "_sudo",
                        lambda args, timeout=30: (0, payload, ""))
    info = tailscale.status()
    assert info["connected"] is True
    assert info["ip"] == "100.64.0.2"
    assert info["hostname"] == "pregacao-pi"
    assert "authkey" not in json.dumps(info).lower()


def test_tailscale_login_devolve_quando_ja_conectado(monkeypatch):
    monkeypatch.setattr(tailscale, "status",
                        lambda: {"installed": True, "connected": True,
                                 "auth_url": "", "message": ""})
    res = tailscale.start_login(wait=0)
    assert res["started"] is False
    assert "ja conectado" in res["message"]
