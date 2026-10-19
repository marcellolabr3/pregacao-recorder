"""Destinos Windows: consultas sem escrita e nenhum fallback de disco."""
from pathlib import Path
from app.storage import destinos as dest


def test_listar_nao_cria_pastas(tmp_path, monkeypatch):
    default, configured = tmp_path / "padrao", tmp_path / "escolhido"
    monkeypatch.setattr(dest, "unidades", lambda: [{"raiz": str(tmp_path), "rotulo": "Disco teste"}])
    items = dest.destinos(configured, default)
    assert items[0]["caminho"] == str(configured)
    assert items[0]["atual"] is True
    assert not default.exists() and not configured.exists()
    assert not (tmp_path / "pregacoes").exists()


def test_destino_igual_ao_padrao_nao_duplica(tmp_path, monkeypatch):
    monkeypatch.setattr(dest, "unidades", lambda: [])
    assert len(dest.destinos(tmp_path, tmp_path)) == 1


def test_disco_ausente_continua_visivel_sem_criar_pasta(tmp_path, monkeypatch):
    absent = tmp_path / "desconectado" / "pregacoes"
    original = dest._raiz
    monkeypatch.setattr(dest, "_raiz", lambda p: tmp_path / "volume-ausente" if p == absent else original(p))
    items = dest.destinos(absent, tmp_path)
    assert items[0]["atual"] is True and items[0]["disponivel"] is False
    assert "nao sera desviada" in dest.aviso(absent, tmp_path)
    assert not absent.exists()


def test_escolher_prepara_pasta_no_destino_solicitado(tmp_path):
    target = tmp_path / "audio" / "gravacoes"
    assert dest.escolher(str(target), tmp_path) == (True, "")
    assert target.is_dir()


def test_escolher_recusa_vazio_e_relativo(tmp_path):
    assert dest.escolher("", tmp_path)[0] is False
    assert dest.escolher("pasta/relativa", tmp_path)[0] is False


def test_escolher_recusa_arquivo(tmp_path):
    target = tmp_path / "arquivo"
    target.write_text("preservar")
    assert dest.escolher(str(target), tmp_path)[0] is False
    assert target.read_text() == "preservar"


def test_status_de_destino_existente(tmp_path):
    status = dest.atual(tmp_path, tmp_path)
    assert status["disponivel"] is True and status["disco"]["ok"] is True
    assert dest.aviso(tmp_path, tmp_path) is None


def test_pasta_sem_permissao_e_recusada(tmp_path, monkeypatch):
    monkeypatch.setattr(dest.os, "access", lambda *a: False)
    assert dest.escolher(str(tmp_path / "sem-permissao"), tmp_path)[0] is False


def test_falha_ao_preparar_pasta_tem_erro_claro(tmp_path, monkeypatch):
    def deny(*a, **k):
        raise PermissionError("acesso negado")
    monkeypatch.setattr(Path, "mkdir", deny)
    ok, message = dest.escolher(str(tmp_path / "novo"), tmp_path)
    assert ok is False and "preparar" in message
