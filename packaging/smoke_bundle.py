"""Smoke local do pacote: sem contas, login, captura ou envios."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main(argv=None):
    arguments = argv if argv is not None else sys.argv[1:]
    root = Path(arguments[0]).resolve()
    python = root / "runtime/python/python.exe"
    node = root / "runtime/node/node.exe"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PREGACAO_", "NOTEBOOKLM_", "PLAYWRIGHT_", "GOOGLE_")) and k not in {"NODE_PATH", "NODE_OPTIONS", "PYTHONPATH", "PYTHONHOME"}}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="pregacao-bundle-smoke-") as temporary:
        env["NOTEBOOKLM_HOME"] = str(Path(temporary) / "notebooklm")
        env["PREGACAO_PIPELINE_HOME"] = temporary
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(root / "runtime/browsers")
        # Package runtime only; avoid using developer tools from PATH.
        windows = os.environ.get("SystemRoot", r"C:\Windows")
        env["PATH"] = os.pathsep.join((str(python.parent), str(node.parent), str(root / "runtime/ffmpeg/bin"), str(Path(windows) / "System32"), windows))
        code = r"""
import importlib, json, pathlib, sys
from io import BytesIO
expected = pathlib.Path(sys.executable).parent.resolve()
for name in ('flask','werkzeug','waitress','googleapiclient.discovery','google_auth_oauthlib','google_auth_httplib2','paho.mqtt.client','openpyxl','notebooklm','markdown','xhtml2pdf','playwright','rookie_cookies'):
    module = importlib.import_module(name)
    if getattr(module, '__file__', None):
        assert pathlib.Path(module.__file__).resolve().is_relative_to(expected), name
from xhtml2pdf import pisa
out = BytesIO()
assert not pisa.CreatePDF('<html><body><h1>Teste local</h1><p>Pregacao Recorder</p></body></html>', dest=out).err
assert out.getvalue().startswith(b'%PDF')
import openpyxl
book = openpyxl.Workbook()
book.active['A1'] = 'teste'
data = BytesIO()
book.save(data)
data.seek(0)
assert openpyxl.load_workbook(data).active['A1'].value == 'teste'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel='chromium')
    context = browser.new_context(offline=True)
    page = context.new_page()
    page.set_content('<h1>Runtime OK</h1>')
    assert page.locator('h1').inner_text() == 'Runtime OK'
    browser.close()
print('Imports, PDF, XLSX and bundled Chromium: PASS')
"""
        subprocess.run([str(python), '-B', '-c', code], cwd=root / 'gravador', env=env, check=True, timeout=300)
        subprocess.run([str(python), '-B', '-m', 'notebooklm', '--version'], cwd=temporary, env=env, check=True, timeout=300)
        subprocess.run([str(node), '--check', str(root / 'pipeline/whatsapp/send.js')], cwd=root / 'pipeline', env=env, check=True, timeout=300)
        subprocess.run([str(node), '-e', "const fs=require('fs'),path=require('path'); const base=fs.realpathSync('node_modules')+path.sep; for(const name of ['baileys','pino','qrcode','qrcode-terminal']) {if(!fs.realpathSync(require.resolve(name)).startsWith(base)) throw Error('Dependency outside package: '+name); require(name);} console.log('WhatsApp dependencies: PASS (no connection)')"], cwd=root / 'pipeline', env=env, check=True, timeout=300)
        ffmpeg = root / 'runtime/ffmpeg/bin/ffmpeg.exe'
        ffprobe = root / 'runtime/ffmpeg/bin/ffprobe.exe'
        devices = subprocess.run([str(ffmpeg), '-hide_banner', '-devices'], env=env, capture_output=True, text=True, check=True, timeout=30)
        assert 'dshow' in devices.stdout + devices.stderr, 'FFmpeg lacks DirectShow'
        audio = Path(temporary) / 'synthetic.mp3'
        subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', '0.1', '-codec:a', 'libmp3lame', '-y', str(audio)], env=env, check=True, timeout=30)
        probe = subprocess.run([str(ffprobe), '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(audio)], env=env, capture_output=True, text=True, check=True, timeout=30)
        assert float(json.loads(probe.stdout)['format']['duration']) > 0
        print('Private FFmpeg/DirectShow and synthetic MP3/ffprobe: PASS (no capture)', flush=True)
        before = {p.relative_to(root) for p in (root / 'gravador/config').rglob('*')}
        subprocess.run([str(python), '-B', '-m', 'app.launcher', '--verificar'], cwd=root / 'gravador', env=env, check=True, timeout=300)
        after = {p.relative_to(root) for p in (root / 'gravador/config').rglob('*')}
        assert before == after, 'diagnostic wrote configuration'
        assert not (root / 'gravador/config/config.json').exists()
        assert not (root / 'gravador/data').exists()
        assert not (root / 'gravador/logs').exists()
    print('Package smoke: PASS; no service, account, capture or send started')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
