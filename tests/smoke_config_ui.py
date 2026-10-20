"""Fluxos CONFIG no Chromium, com APIs sinteticas e nenhuma conexao externa.

Executar com Python/Playwright do pacote e PLAYWRIGHT_BROWSERS_PATH do pacote.
Nao importa app.*, nao abre contas, microfone, arquivos pessoais ou broker.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parent.parent


def main():
    config = json.loads((ROOT / "config/default.json").read_text(encoding="utf-8"))
    config["storage"]["recordings_dir"] = "C:\\Teste\\gravacoes"
    devices = [{"hw": "dshow:mesa-a", "name": "Mesa A"},
               {"hw": "dshow:mesa-b", "name": "Mesa B"}]
    remote = {"enabled": True, "host": "broker.invalid", "port": 8883, "tls": True,
              "username": "pc-teste", "password_configured": True,
              "device_id": "pregacao-ui", "operator_token": "token-sintetico",
              "operator_token_configured": True, "restart_required": False}
    posts = []
    errors = []
    setup_needed = True

    def dispatch(route):
        nonlocal setup_needed
        request = route.request
        path = urlsplit(request.url).path
        if urlsplit(request.url).hostname != "pregacao-config.test":
            errors.append("tentativa de rede externa")
            route.abort()
            return
        if path in ("/", "/config", "/historico"):
            html = (ROOT / "web/templates/index.html").read_text(encoding="utf-8")
            route.fulfill(content_type="text/html", body=html.replace("{{ device_name }}", "Teste"))
            return
        if path.startswith("/static/"):
            asset = ROOT / "web" / path.lstrip("/")
            kind = "application/javascript" if path.endswith(".js") else "text/css"
            route.fulfill(content_type=kind, body=asset.read_text(encoding="utf-8") if asset.is_file() else "")
            return
        body = request.post_data_json if request.method == "POST" and request.post_data else {}
        if request.method == "POST":
            posts.append((path, copy.deepcopy(body)))
        response = {}
        if path == "/api/me":
            response = {"auth": True, "admin": True, "pin_required": False,
                        "setup_needed": setup_needed, "device_name": "Teste"}
        elif path == "/api/status":
            response = {"state": "IDLE", "device_name": "Teste", "network": {"online": False}}
        elif path == "/api/setup":
            response = {"admin": True, "recordings_dir": config["storage"]["recordings_dir"]}
        elif path == "/api/setup/complete":
            setup_needed = False
            response = {"ok": True}
        elif path == "/api/audio/devices":
            response = {"items": devices, "selected": devices[0]}
        elif path == "/api/audio/test":
            device = next((d for d in devices if d["hw"] == body.get("device")), devices[0])
            response = {"ok": True, "silent": False, "peak_db": -10, "device": device}
        elif path == "/api/config" and request.method == "POST":
            for key, value in body.items():
                target = config
                parts = key.split(".")
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = value
            response = {"ok": True}
        elif path == "/api/config":
            cfg = copy.deepcopy(config)
            cfg["drive"]["client_secret_set"] = True
            response = {"admin": True, "config": cfg, "remote": remote,
                        "audio_devices": devices, "detected": devices[0], "drive": {},
                        "formats": ["S16_LE"], "rates": [44100, 48000],
                        "encoders": ["mp3"], "bitrates": [128], "has_ffmpeg": True}
        elif path == "/api/storage":
            current = config["storage"]["recordings_dir"]
            response = {"current": current, "situacao": {"disponivel": True},
                        "items": [{"caminho": current, "rotulo": "Pasta de teste", "montado": True}]}
        elif path == "/api/remote/config":
            assert isinstance(body["port"], int) and not isinstance(body["port"], bool)
            remote.update({k: v for k, v in body.items() if k != "password"})
            remote["restart_required"] = True
            response = {"ok": True, "remote": remote,
                        "message": "Reinicie o Windows e abra o atalho; confirme STATUS/ACK no celular."}
        elif path in ("/api/estudos/status", "/api/integracoes", "/api/pregacoes", "/api/events/history"):
            response = {}
        else:
            errors.append(f"rota inesperada: {request.method} {path}")
        route.fulfill(content_type="application/json", body=json.dumps(response))

    with sync_playwright() as playwright:
        print("Chromium isolado: iniciando", flush=True)
        browser = playwright.chromium.launch(headless=True, timeout=60000, args=["--disable-gpu"])
        print("Chromium isolado: navegador iniciado", flush=True)
        context = browser.new_context(offline=True)
        print("Chromium isolado: contexto criado", flush=True)
        context.set_default_timeout(30000)
        context.set_default_navigation_timeout(30000)
        context.add_init_script("window.EventSource = undefined;")
        context.route("**/*", dispatch)
        page = context.new_page()
        print("Chromium isolado: pagina criada", flush=True)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://pregacao-config.test/", wait_until="domcontentloaded")
        print("Chromium isolado: painel carregado", flush=True)

        # O teste do assistente usa a selecao antes de AVANCAR/salvar.
        expect(page.locator("#setupOverlay")).to_be_visible()
        page.select_option("#wizDevice", "dshow:mesa-b")
        page.click("#wizAudioTest")
        expect(page.locator("#wizAudioResult")).to_contain_text("Mesa B")
        assert posts[-1] == ("/api/audio/test", {"device": "dshow:mesa-b"})
        assert config["audio"]["device"] == "auto"
        page.click("#wizNext")
        page.fill("#wizDir", "C:\\Teste\\Outro destino")
        page.click("#wizNext")
        page.click("#wizNext")
        page.click("#wizFinish")
        expect(page.locator("#setupOverlay")).not_to_be_visible()
        print("PASS: selecao/teste de audio e destino no assistente existente", flush=True)

        page.click("#navConfig")
        page.click("#btnAdvanced")
        expect(page.locator("#cfgDevice")).to_have_value("dshow:mesa-b")
        expect(page.locator("#cfgDestino")).to_have_value("C:\\Teste\\Outro destino")
        page.select_option("#cfgDevice", "dshow:mesa-a")
        page.select_option("#cfgRate", "48000")
        page.select_option('select[name="audio.channels"]', "1")
        page.click("#btnConfigAudioTest")
        expect(page.locator("#cfgAudioTestResult")).to_contain_text("Mesa A")
        assert posts[-1] == ("/api/audio/test", {"device": "dshow:mesa-a", "sample_rate": "48000", "channels": "1"})
        assert config["audio"]["device"] == "dshow:mesa-b"
        page.locator('#advancedForm button[type="submit"]').click()
        expect(page.locator("#advancedMsg")).to_have_text("Configuracoes avancadas salvas")
        saved = next(body for path, body in reversed(posts) if path == "/api/config")
        assert saved["audio.device"] == "dshow:mesa-a"
        assert "drive.client_secret" not in saved
        print("PASS: teste tecnico da selecao e salvamento de configuracoes", flush=True)

        # Conexao salva no bloco existente; senha omitida ao editar outra opcao.
        page.fill("#cfgRemoteHostInput", "novo.invalid")
        page.fill("#cfgRemoteUsername", "pc-novo")
        page.fill("#cfgRemoteDeviceInput", "pregacao-novo")
        page.fill("#cfgRemotePassword", "senha-sintetica")
        page.fill("#cfgRemoteNewToken", "token-novo")
        page.click("#btnRemoteSave")
        expect(page.locator("#cfgRemoteMessage")).to_contain_text("Reinicie o Windows")
        expect(page.locator("#cfgRemotePassword")).to_have_value("")
        expect(page.locator("#cfgRemoteNewToken")).to_have_value("")
        expect(page.locator("#cfgRemoteToken")).to_have_attribute("type", "password")

        expect(page.locator("#cfgRemoteDevice")).to_have_text("pregacao-novo")
        page.click("#btnRemoteToken")
        expect(page.locator("#cfgRemoteToken")).to_have_attribute("type", "text")
        page.click("#btnRemoteSave")
        expect(page.locator("#btnRemoteSave")).to_be_enabled()
        assert posts[-1][0] == "/api/remote/config"
        assert "password" not in posts[-1][1] and "operator_token" not in posts[-1][1]
        page.click("#btnAdvancedBack")
        expect(page.locator("#cfgRemoteToken")).to_have_value("")
        expect(page.locator("#cfgRemotePassword")).to_have_value("")
        page.click("#btnAdvanced")
        expect(page.locator("#cfgRemoteHostInput")).to_have_value("novo.invalid")
        expect(page.locator("#cfgRemoteToken")).to_have_attribute("type", "password")
        print("PASS: configuracao MQTT, preservacao de segredos e reabertura", flush=True)

        # Desconectar a interface salva preserva a preferencia na reabertura.
        devices[:] = [devices[1]]
        page.reload(wait_until="domcontentloaded")
        page.click("#navConfig")
        page.click("#btnAdvanced")
        expect(page.locator("#cfgDevice")).to_have_value("dshow:mesa-a")
        expect(page.locator("#cfgDevice option:checked")).to_contain_text("indisponivel")
        assert not errors, errors
        context.close()
        browser.close()
    print("PASS: Chromium CONFIG/audio/destino/MQTT com APIs isoladas; nenhuma conexao real.")


if __name__ == "__main__":
    main()
