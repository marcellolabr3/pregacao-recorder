"""Testes S4: importacao CSV/XLSX + CRUD de pregacoes + snapshot."""
import tempfile
from pathlib import Path

import pytest

from app.db import Database
from app.importacao import (
    PregacaoImportada,
    gerar_modelo_csv,
    gravar_pregacoes,
    importar_csv,
    importar_xlsx,
)


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_modelo_csv_gera_cabecalho_e_exemplos():
    csv_texto = gerar_modelo_csv()
    assert csv_texto.startswith("data,horario,pregador,igreja,texto_base,tema\n")
    assert "Joao 3:16" in csv_texto
    assert "Romanos 8:28" in csv_texto


def test_importar_csv_valido(db):
    csv_texto = """data,horario,pregador,igreja,texto_base,tema
2026-10-25,19:00,Pr. Joao Silva,Igreja Central,"Joao 3:16","O Amor de Deus"
2026-11-01,09:30,Pr. Maria Santos,Igreja Norte,"Romanos 8:28","Todas as Coisas Cooperam"
"""
    res = importar_csv(csv_texto, db.get_pregacao_por_data_horario)
    assert len(res.validos) == 2
    assert res.erros == []
    assert res.duplicatas == []
    assert res.validos[0].data == "2026-10-25"
    assert res.validos[0].horario == "19:00"
    assert res.validos[0].pregador == "Pr. Joao Silva"


def test_importar_csv_com_erros(db):
    csv_texto = """data,horario,pregador,igreja,texto_base,tema
2026-10-25,19:00,Pr. Joao Silva,Igreja Central,"Joao 3:16","O Amor de Deus"
invalida,19:00,Sem Pregador,Igreja X,, 
2026-11-01,,Pr. Maria Santos,Igreja Norte,"Romanos 8:28","Tema"
"""
    res = importar_csv(csv_texto, db.get_pregacao_por_data_horario)
    assert len(res.validos) == 1  # so a primeira linha valida
    assert len(res.erros) >= 2  # data invalida + horario vazio
    # erros contem campo e mensagem
    for e in res.erros:
        assert "linha" in e
        assert "campo" in e
        assert "mensagem" in e


def test_importar_csv_duplicata_contra_banco(db):
    # pre-popula o banco
    db.create_pregacao("2026-10-25", "19:00", "Pr. Joao", "Igreja A", "", "")
    csv_texto = """data,horario,pregador,igreja,texto_base,tema
2026-10-25,19:00,Pr. Outro,Igreja B,, 
2026-11-01,09:30,Pr. Maria,Igreja C,, 
"""
    res = importar_csv(csv_texto, db.get_pregacao_por_data_horario)
    assert len(res.validos) == 1  # so a segunda (nao duplicata)
    assert len(res.duplicatas) == 1
    dup = res.duplicatas[0]
    assert dup["data"] == "2026-10-25"
    assert dup["horario"] == "19:00"
    assert dup["existente_id"] > 0


def test_importar_xlsx_valido(db):
    import openpyxl
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["data", "horario", "pregador", "igreja", "texto_base", "tema"])
        ws.append(["2026-10-25", "19:00", "Pr. Joao", "Igreja A", "Joao 3:16", "Tema A"])
        wb.save(tmp.name)
        tmp_path = Path(tmp.name)
    try:
        res = importar_xlsx(tmp_path, db.get_pregacao_por_data_horario)
        assert len(res.validos) == 1
        assert res.validos[0].pregador == "Pr. Joao"
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except PermissionError:
            pass  # Windows: arquivo ainda aberto pelo openpyxl read_only


def test_gravar_pregacoes_retorna_ids(db):
    pregacoes = [
        PregacaoImportada(
            data="2026-10-25", horario="19:00", pregador="Pr. A",
            igreja="Igreja 1", texto_base="T1", tema="Tema 1", linha_origem=1
        ),
        PregacaoImportada(
            data="2026-11-01", horario="09:30", pregador="Pr. B",
            igreja="Igreja 2", texto_base="T2", tema="Tema 2", linha_origem=2
        ),
    ]
    ids = gravar_pregacoes(db, pregacoes)
    assert len(ids) == 2
    for pid in ids:
        p = db.get_pregacao(pid)
        assert p is not None


def test_gravar_pregacoes_duplicata_levanta_integrity(db):
    db.create_pregacao("2026-10-25", "19:00", "Pr. A", "Igreja 1", "", "")
    pregacoes = [
        PregacaoImportada(
            data="2026-10-25", horario="19:00", pregador="Pr. B",
            igreja="Igreja 2", texto_base="", tema="", linha_origem=1
        ),
    ]
    with pytest.raises(Exception):  # sqlite3.IntegrityError
        gravar_pregacoes(db, pregacoes)


# ---------------------------------------------------------------------
# CRUD direto no banco (db.py)
# ---------------------------------------------------------------------
def test_create_pregacao_duplicata_levanta(db):
    db.create_pregacao("2026-10-25", "19:00", "Pr. A", "Igreja 1", "T1", "Tema 1")
    with pytest.raises(Exception):  # sqlite3.IntegrityError
        db.create_pregacao("2026-10-25", "19:00", "Pr. B", "Igreja 2", "", "")


def test_get_pregacao_por_data_horario(db):
    db.create_pregacao("2026-10-25", "19:00", "Pr. A", "Igreja 1", "Joao 3:16", "Amor")
    p = db.get_pregacao_por_data_horario("2026-10-25", "19:00")
    assert p is not None
    assert p["pregador"] == "Pr. A"
    assert p["texto_base"] == "Joao 3:16"
    # nao existente
    assert db.get_pregacao_por_data_horario("2026-10-25", "20:00") is None


def test_list_pregacoes_com_filtro_data(db):
    db.create_pregacao("2026-10-20", "19:00", "Pr. A", "Igreja 1", "", "")
    db.create_pregacao("2026-10-25", "19:00", "Pr. B", "Igreja 2", "", "")
    db.create_pregacao("2026-11-01", "09:30", "Pr. C", "Igreja 3", "", "")
    todas = db.list_pregacoes()
    assert len(todas) == 3
    out = db.list_pregacoes(data_de="2026-10-25", data_ate="2026-10-31")
    assert len(out) == 1
    assert out[0]["data"] == "2026-10-25"


def test_update_pregacao_incrementa_versao(db):
    pid = db.create_pregacao("2026-10-25", "19:00", "Pr. A", "Igreja 1", "", "")
    p1 = db.get_pregacao(pid)
    assert p1["versao"] == 1
    ok = db.update_pregacao(pid, pregador="Pr. B")
    assert ok is True
    p2 = db.get_pregacao(pid)
    assert p2["pregador"] == "Pr. B"
    assert p2["versao"] == 2


def test_update_pregacao_incrementa_versao(db):
    pid = db.create_pregacao("2026-10-25", "19:00", "Pr. A", "Igreja 1", "", "")
    p1 = db.get_pregacao(pid)
    assert p1["versao"] == 1
    ok = db.update_pregacao(pid, tema="Tentativa 1")
    assert ok is True
    p2 = db.get_pregacao(pid)
    assert p2["versao"] == 2
    assert p2["tema"] == "Tentativa 1"
    # segundo update
    ok = db.update_pregacao(pid, tema="Tentativa 2")
    assert ok is True
    p3 = db.get_pregacao(pid)
    assert p3["versao"] == 3
    assert p3["tema"] == "Tentativa 2"


def test_snapshot_pregacao_para_job_retorna_dict(db):
    db.create_pregacao("2026-10-25", "19:00", "Pr. Joao", "Igreja Central", "Joao 3:16", "Amor")
    snap = db.snapshot_pregacao_para_job("2026-10-25", "19:00")
    assert snap is not None
    assert snap["pregacao_id"] > 0
    assert snap["data"] == "2026-10-25"
    assert snap["horario"] == "19:00"
    assert snap["pregador"] == "Pr. Joao"
    assert snap["versao"] == 1
    # nao encontrado
    assert db.snapshot_pregacao_para_job("2026-10-25", "20:00") is None


def test_delete_pregacao(db):
    pid = db.create_pregacao("2026-10-25", "19:00", "Pr. A", "Igreja 1", "", "")
    assert db.delete_pregacao(pid) is True
    assert db.get_pregacao(pid) is None
    # deletar de novo = False
    assert db.delete_pregacao(pid) is False