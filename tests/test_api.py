import pytest

flask = pytest.importorskip("flask")

from app.states import State  # noqa: E402


@pytest.fixture()
def client(fresh_state):
    from app.main import build

    app, manager, uploader = build()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client, pin="1234"):
    return client.post("/api/login", json={"pin": pin})


def _admin(client, pin="1234"):
    """Login normal + liberacao das CONFIGURACOES AVANCADAS."""
    _login(client)
    return client.post("/api/admin/login", json={"pin": pin})


# --------------------------------------------------------------------------
def test_index_is_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"INICIAR GRAVACAO" in resp.data
    assert b"FINALIZAR GRAVACAO" in resp.data
    # nao pode haver toggle de clique unico
    assert b"toggle" not in resp.data.lower()


def test_programacao_fica_na_primeira_pagina(client):
    pagina = client.get("/").data
    inicio = pagina.index(b'id="viewHome"')
    programacao = pagina.index(b'id="programacaoCard"')
    avancado = pagina.index(b'id="viewAdvanced"')
    assert inicio < programacao < avancado


def test_programacao_api_valida_campos_e_versao_de_dois_celulares(client):
    _admin(client)
    dados = {
        "data": "2026-11-01", "horario": "19:00", "pregador": "Ana",
        "igreja": "Central", "texto_base": "Joao 3:16", "tema": "Amor",
    }
    assert client.post("/api/pregacoes", json={**dados, "data": "2026-02-30"}).status_code == 422
    criado = client.post("/api/pregacoes", json=dados)
    assert criado.status_code == 200
    item = criado.get_json()["pregacao"]
    assert item["versao"] == 1
    pid = item["id"]

    alterado = client.put(f"/api/pregacoes/{pid}", json={"pregador": "Beatriz", "versao": 1})
    assert alterado.status_code == 200
    assert alterado.get_json()["pregacao"]["versao"] == 2
    conflito = client.put(f"/api/pregacoes/{pid}", json={"pregador": "Carla", "versao": 1})
    assert conflito.status_code == 409
    assert conflito.get_json()["error"] == "versao_desatualizada"
    assert client.get(f"/api/pregacoes/{pid}").get_json()["pregador"] == "Beatriz"
    assert client.delete(f"/api/pregacoes/{pid}", json={"versao": 1}).status_code == 409
    assert client.delete(f"/api/pregacoes/{pid}", json={"versao": 2}).status_code == 200

    eventos = client.get("/api/events/history").get_json()["items"]
    assert len([e for e in eventos if e["kind"] == "programacao_alterada"]) == 3


def test_me_reports_pin_required(client):
    data = client.get("/api/me").get_json()
    assert data["pin_required"] is True
    assert data["auth"] is False


def test_critical_operations_require_pin(client):
    assert client.post("/api/start").status_code == 401
    assert client.post("/api/stop").status_code == 401
    assert client.get("/api/config").status_code == 401
    assert client.get("/api/recovery").status_code == 401


def test_wrong_pin_rejected(client):
    resp = _login(client, "9999")
    assert resp.status_code == 401
    assert client.post("/api/start").status_code == 401


def test_correct_pin_grants_access(client):
    assert _login(client).status_code == 200
    assert client.get("/api/config").status_code == 200


def test_logout_revokes_access(client):
    _login(client)
    client.post("/api/logout")
    assert client.post("/api/start").status_code == 401


def test_status_endpoint_exposes_source_of_truth(client):
    data = client.get("/api/status").get_json()
    for key in ("state", "banner", "storage", "network", "drive", "uploads",
                "recovery", "last_recording", "audio_devices", "device",
                "platform"):
        assert key in data, key
    assert data["state"] in State.ALL


def test_start_without_audio_device_is_refused(client, monkeypatch):
    """Sem interface de audio, o sistema NAO deve fingir que gravou.

    A ausencia de placa e simulada por mock: o teste nao pode depender de o
    host ter arecord/ffmpeg/placa nenhuma.
    """
    from app.audio import device as audio_device

    monkeypatch.setattr(audio_device, "list_devices", lambda: [])
    _login(client)
    resp = client.post("/api/start")
    assert resp.status_code == 409
    assert "interface de audio" in resp.get_json()["message"].lower()


def test_stop_while_idle_is_refused(client):
    _login(client)
    resp = client.post("/api/stop")
    assert resp.status_code == 409


def test_config_validation_rejects_bad_values(client):
    _admin(client)
    resp = client.post("/api/config", json={"audio.sample_rate": 12345})
    assert resp.status_code == 422
    resp = client.post("/api/config", json={"audio.channels": 9})
    assert resp.status_code == 422
    resp = client.post("/api/config", json={"chave_inexistente": 1})
    assert resp.status_code == 422


def test_advanced_config_requires_admin_pin(client):
    """Usuario comum nao altera audio/armazenamento/credenciais."""
    _login(client)
    resp = client.post("/api/config", json={"audio.sample_rate": 44100})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "admin_obrigatorio"
    resp = client.post("/api/config", json={"drive.client_id": "x"})
    assert resp.status_code == 403
    # porem ele pode alterar o nome do equipamento
    resp = client.post("/api/config", json={"device_name": "Nome Livre"})
    assert resp.status_code == 200


def test_config_get_hides_credentials_from_regular_user(client, cfg):
    """O usuario comum nunca recebe credenciais/tecnico via API."""
    cfg.set("drive.client_id", "igreja.apps.googleusercontent.com")
    cfg.set("drive.client_secret", "GOCSPX-segredo-grande-123")
    _login(client)

    data = client.get("/api/config").get_json()
    assert data["admin"] is False
    assert data["config"]["device_name"]            # nome livre, sempre
    assert "audio" not in data["config"]            # nada de formatos
    assert "drive" not in data["config"]            # nada de client_id
    assert "audio_devices" not in data
    assert set(data["drive"]) <= {
        "connected", "credentials", "account", "folder"}

    st = client.get("/api/drive/status").get_json()
    assert "client_id" not in st
    assert "credentials_file" not in st
    assert "source" not in st

    # administrador recebe o payload completo (secret continua fora)
    _admin(client)
    data = client.get("/api/config").get_json()
    assert data["admin"] is True
    assert data["config"]["drive"]["client_id"] == \
        "igreja.apps.googleusercontent.com"
    assert data["config"]["drive"]["client_secret"] == ""
    assert data["config"]["drive"]["client_secret_set"] is True
    assert "audio" in data["config"]
    assert data["remote"]["device_id"]        # id unico do equipamento
    # padrao de fabrica: agente desligado (sem PREGACAO_REMOTE_HOST)
    assert data["remote"]["configured"] is False
    assert data["remote"]["enabled"] is False
    assert data["remote"]["operator_token"] == ""
    assert isinstance(data["remote"]["service"], str)  # nao depende do gerenciador de servicos


def test_remote_block_is_admin_only(client):
    """Controle remoto (id + token do operador) nunca sai para usuario comum."""
    _login(client)
    data = client.get("/api/config").get_json()
    assert data["admin"] is False
    assert "remote" not in data


def test_admin_login_and_logs(client):
    _login(client)
    # sem admin, a area avanccada e os logs sao negados
    assert client.get("/api/logs").status_code == 403
    assert client.post("/api/admin/login", json={"pin": "0000"}).status_code == 401
    assert client.post("/api/admin/login", json={"pin": "1234"}).status_code == 200
    resp = client.get("/api/logs?lines=50")
    assert resp.status_code == 200
    assert "file" in resp.get_json()
    assert client.post("/api/config", json={"audio.bitrate": 192}).status_code == 200


def test_setup_wizard_flow(client):
    _login(client)
    assert client.get("/api/setup").get_json()["needed"] is True
    assert client.get("/api/me").get_json()["setup_needed"] is True
    resp = client.post("/api/setup/complete")
    assert resp.status_code == 200
    assert client.get("/api/setup").get_json()["needed"] is False
    assert client.get("/api/me").get_json()["setup_needed"] is False
    # sem login, o assistente nao expoe nada
    client.post("/api/logout")
    assert client.get("/api/setup").status_code == 401


def test_config_accepts_valid_values(client):
    _admin(client)
    resp = client.post(
        "/api/config",
        json={
            "device_name": "Igreja Teste",
            "audio.sample_rate": 48000,
            "audio.bitrate": 192,
            "drive.auto_upload": False,
        },
    )
    assert resp.status_code == 200
    assert "audio.sample_rate" in resp.get_json()["applied"]

    data = client.get("/api/config").get_json()["config"]
    assert data["device_name"] == "Igreja Teste"
    assert data["audio"]["sample_rate"] == 48000
    assert data["drive"]["auto_upload"] is False


def test_config_rejects_unknown_audio_device(client):
    _admin(client)
    resp = client.post("/api/config", json={"audio.device": "hw:99,0"})
    assert resp.status_code == 422


def test_drive_connect_without_credentials(client):
    _login(client)
    resp = client.post("/api/drive/connect")
    assert resp.status_code in (412, 501, 500)


def test_oauth_callback_without_code_returns_to_interface(client):
    _login(client)
    resp = client.get("/oauth/callback")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "/config?drive=erro" in body


def test_oauth_callback_google_error_returns_to_interface(client):
    _login(client)
    resp = client.get("/oauth/callback?error=access_denied")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "/config?drive=erro" in body
    assert "access_denied" in body


def test_oauth_callback_with_code_but_without_flow(client):
    _login(client)
    resp = client.get("/oauth/callback?code=abc")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "/config?drive=erro" in body


def test_oauth_callback_requires_pin(client):
    resp = client.get("/oauth/callback?code=abc")
    assert resp.status_code == 401


def test_drive_credentials_are_manual_and_secret_never_leaks(client):
    _admin(client)
    resp = client.post(
        "/api/config",
        json={
            "drive.client_id": "minha-igreja.apps.googleusercontent.com",
            "drive.client_secret": "GOCSPX-segredo-longo-123",
        },
    )
    assert resp.status_code == 200

    drive_cfg = client.get("/api/config").get_json()["config"]["drive"]
    assert drive_cfg["client_id"] == "minha-igreja.apps.googleusercontent.com"
    assert drive_cfg["client_secret"] == ""            # secret nunca sai daqui
    assert drive_cfg["client_secret_set"] is True

    st = client.get("/api/drive/status").get_json()
    assert st["credentials"] is True
    assert st["source"] == "manual"


def test_drive_client_id_invalid_rejected(client):
    _admin(client)
    resp = client.post("/api/config", json={"drive.client_id": "nao-um-client-id"})
    assert resp.status_code == 422


def test_clearing_client_id_also_clears_secret(client):
    _admin(client)
    client.post(
        "/api/config",
        json={
            "drive.client_id": "x.apps.googleusercontent.com",
            "drive.client_secret": "segredo-grande-123",
        },
    )
    client.post("/api/config", json={"drive.client_id": ""})
    st = client.get("/api/drive/status").get_json()
    assert st["credentials"] is False
    assert st["source"] != "manual"


def test_start_authorization_prefers_manual_credentials(cfg):
    pytest.importorskip("google_auth_oauthlib.flow")
    from app.upload import drive

    cfg.set("drive.client_id", "manual-abc.apps.googleusercontent.com")
    cfg.set("drive.client_secret", "segredo-manual-123")
    url = drive.start_authorization("http://localhost:8099/oauth/callback")
    assert "manual-abc.apps.googleusercontent.com" in url
    # o seletor de contas habilita TROCAR de conta
    assert "select_account" in url


def test_notifications_are_persisted(client):
    _login(client)
    client.post("/api/config", json={"device_name": "X"})
    items = client.get("/api/events/history").get_json()["items"]
    assert any(i["kind"] == "configuracao" for i in items)


def test_recovery_endpoints_without_item(client):
    _login(client)
    assert client.get("/api/recovery").get_json()["items"] == []
    resp = client.post("/api/recovery/nao-existe/recover")
    assert resp.status_code == 409


def test_stream_nao_declara_header_proibido(client):
    """/api/stream nao pode definir "Connection" (header hop-by-hop).

    A PEP 3333 proibe o aplicativo de tocar nesse header: o waitress levanta
    AssertionError e devolve 500, o que quebra o fluxo ao vivo do painel
    (EventSource). O keep-alive e responsabilidade do servidor.
    """
    _login(client)
    resp = client.get("/api/stream")
    try:
        assert resp.status_code == 200
        assert "Connection" not in resp.headers
        assert resp.headers["Content-Type"].startswith("text/event-stream")
        # le o primeiro snapshot e encerra antes do loop infinito
        pedaco = next(iter(resp.response))
        assert b"event: status" in pedaco
    finally:
        resp.close()


# --------------------------------------------------------------------------
# armazenamento: onde gravar (SSD x pasta do PC)
# --------------------------------------------------------------------------
def _norm(caminho) -> str:
    """Caminhos chegam com barra nativa na API e em POSIX no modulo de
    destinos; sem normalizar as comparacoes quebrariam so no Windows."""
    return str(caminho).replace("\\", "/")


def test_storage_list_requires_pin(client):
    assert client.get("/api/storage").status_code == 401
    assert client.get("/api/storage").get_json()["error"] == "nao_autenticado"


def test_storage_list_shows_destinations_and_current(client):
    """A lista expoe o destino escolhido, a situacao real e os candidatos."""
    _login(client)
    data = client.get("/api/storage").get_json()

    assert _norm(data["current"])            # sempre ha um destino ativo
    assert _norm(data["default_dir"])         # e o colchao da pasta do PC
    assert _norm(data["situacao"]["caminho"]) == _norm(data["current"])
    assert isinstance(data["aviso"], (str, type(None)))

    candidatos = [_norm(i["caminho"]) for i in data["items"]]
    assert candidatos
    # a pasta do PC aparece SEMPRE: e o que segura quando o disco externo some
    assert _norm(data["default_dir"]) in candidatos
    # o destino escolhido tambem, mesmo que o disco tenha sumido
    assert _norm(data["current"]) in candidatos


def test_storage_set_requires_admin_pin(client):
    """Trocar o destino e operacao de administrador."""
    _login(client)
    resp = client.post("/api/storage", json={"path": "/qualquer/pasta"})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "admin_obrigatorio"


def test_storage_set_rejects_unmounted_destination(client, monkeypatch):
    """Recusa destino relativo/invalido; nao escolhe outro disco."""
    _admin(client)
    resp = client.post("/api/storage", json={"path": "caminho/relativo/invalido"})
    assert resp.status_code == 422
    assert resp.get_json()["error"] == "destino_invalido"


def test_storage_set_rejects_empty_path(client):
    _admin(client)
    resp = client.post("/api/storage", json={"path": "   "})
    assert resp.status_code == 422
    assert resp.get_json()["error"] == "destino_invalido"


def test_storage_set_accepts_default_folder(client, monkeypatch):
    """O pasta padrao do PC e um destino valido."""
    from app.paths import recordings_dir

    _admin(client)
    alvo = str(recordings_dir())
    resp = client.post("/api/storage", json={"path": alvo})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["current"] == alvo
    assert _norm(client.get("/api/storage").get_json()["current"]) == _norm(alvo)


def test_config_rejects_unmounted_destination(client, monkeypatch):
    """A troca via /api/config passa pela mesma validacao dos destinos."""
    _admin(client)
    resp = client.post(
        "/api/config", json={"storage.recordings_dir": "caminho/relativo/invalido"}
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"] == "config_invalida"


def test_config_keeps_current_destination_when_disk_is_gone(client, cfg, monkeypatch):
    """O form completo REENVIA o destino; se nao mudou, nao valida.

    Sem esta regra o administrador perdia qualquer outra alteracao so porque
    o SSD desconectou - o campo seria revalidado, recusado, e nada seria
    salvo. O valor igual ao atual pula a checagem.
    """
    cfg.set("storage.recordings_dir", "caminho/relativo/invalido")

    _admin(client)
    resp = client.post(
        "/api/config",
        json={
            "device_name": "Igreja Teste",
            "storage.recordings_dir": "caminho/relativo/invalido",  # igual ao atual
        },
    )
    assert resp.status_code == 200
    assert "device_name" in resp.get_json()["applied"]
    # o destino nao foi tocado nem revalidado
    assert _norm(cfg.recordings_root) == "caminho/relativo/invalido"


# --------------------------------------------------------------------------
# google drive: conector loopback do APK (o Pi nunca ouve o retorno)
# --------------------------------------------------------------------------
def test_drive_finish_requires_pin(client):
    resp = client.post("/api/drive/finish", json={"code": "abc"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "nao_autenticado"


def test_drive_finish_without_code_is_rejected(client):
    _login(client)
    resp = client.post("/api/drive/finish", json={"state": "qualquer"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "codigo_ausente"


def test_drive_finish_without_open_flow_is_rejected(client, monkeypatch):
    """Sem fluxo aberto no Pi, um codigo solto do celular nao e aceito."""
    from app.upload import drive

    monkeypatch.setattr(drive, "_flow", None)
    _login(client)
    resp = client.post(
        "/api/drive/finish", json={"code": "codigo-solto", "state": "state-solto"}
    )
    assert resp.status_code == 502
    assert resp.get_json()["error"] == "drive_oauth_falhou"


def test_finish_authorization_rejects_state_from_another_flow(monkeypatch):
    """Um codigo valido de OUTRO pedido nao pode ser aceito.

    O APK captura o retorno do navegador em localhost:8080 do PROPRIO
    celular e devolve por aqui. O ``state`` e o que prova que aquele codigo
    veio do fluxo que este Pi abriu.
    """
    from app.upload import drive

    trocados = []

    class _Fluxo:
        credentials = object()

        def fetch_token(self, code):
            trocados.append(code)

    monkeypatch.setattr(drive, "_import_google", lambda: True)
    monkeypatch.setattr(drive, "_flow", _Fluxo())
    monkeypatch.setattr(drive, "_pending_state", "state-desta-sessao")

    with pytest.raises(drive.DriveError) as exc:
        drive.finish_authorization("codigo-do-google", "state-de-outro-pedido")

    assert "nao confere" in str(exc.value)
    assert trocados == []          # o codigo NUNCA chegou a ser trocado


def test_finish_authorization_without_state_keeps_web_flow(monkeypatch):
    """O fluxo da interface web nao envia state: continua sendo aceito."""
    from app.upload import drive

    trocados = []

    class _Fluxo:
        credentials = object()

        def fetch_token(self, code):
            trocados.append(code)

    monkeypatch.setattr(drive, "_import_google", lambda: True)
    monkeypatch.setattr(drive, "_flow", _Fluxo())
    monkeypatch.setattr(drive, "_pending_state", "state-desta-sessao")
    monkeypatch.setattr(drive, "_save_token", lambda creds: None)

    drive.finish_authorization("codigo-do-google")
    assert trocados == ["codigo-do-google"]


@pytest.mark.parametrize("url", ["/api/network/status", "/api/network/wifi/scan", "/api/network/ap/enable", "/api/network/tailscale/status"])
def test_gestao_de_rede_retirada(client, url):
    _admin(client)
    assert client.get(url).status_code == 404
    assert client.post(url, json={}).status_code == 404


@pytest.mark.parametrize("url", ["/api/integracoes", "/api/pregacoes", "/api/importacao/modelo"])
def test_rotas_atuais_disponiveis_no_backend_atualizado(client, url):
    _admin(client)
    assert client.get(url).status_code == 200
