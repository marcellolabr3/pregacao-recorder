"""Regressoes da retirada de administracao de rede e do painel Windows."""
import json
from html.parser import HTMLParser
from pathlib import Path

from app import paths
from app.config import Config


def test_home_padrao_e_o_projeto(monkeypatch):
    monkeypatch.delenv("PREGACAO_HOME", raising=False)
    assert paths.home() == Path(paths.__file__).resolve().parent.parent


def test_home_explicito_e_preservado(tmp_path, monkeypatch):
    monkeypatch.setenv("PREGACAO_HOME", str(tmp_path))
    assert paths.home() == tmp_path


def test_config_antiga_ignora_rede_sem_reescrever_arquivo(tmp_path):
    folder = tmp_path / "config"
    folder.mkdir()
    file = folder / "config.json"
    original = json.dumps({"network": {"ap_forced": True, "ap_ssid": "antigo", "check_port": 443},
                           "storage": {"recordings_dir": "D:/Gravacoes"}})
    file.write_text(original)
    cfg = Config(tmp_path)
    assert cfg.as_dict()["network"] == {"check_port": 443}
    assert cfg.recordings_root == Path("D:/Gravacoes")
    assert file.read_text() == original


def test_formularios_do_painel_sao_independentes():
    class Forms(HTMLParser):
        def __init__(self):
            super().__init__()
            self.form = None
            self.owners = {}

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "form":
                assert self.form is None, "formularios aninhados quebram o boot do painel"
                self.form = attrs.get("id")
            if tag in ("input", "select"):
                self.owners[attrs.get("name")] = self.form

        def handle_endtag(self, tag):
            if tag == "form":
                assert self.form is not None
                self.form = None

    html = Path(__file__).resolve().parent.parent / "web/templates/index.html"
    parser = Forms()
    parser.feed(html.read_text(encoding="utf-8"))
    assert parser.form is None
    assert parser.owners["pregador"] == "pregacaoForm"
    assert parser.owners["network.check_host"] == "advancedForm"
    assert parser.owners["storage.recordings_dir"] == "advancedForm"
