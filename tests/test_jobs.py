"""S2: jobs do estudo persistidos em SQLite.

Estado/etapa/prova gravada vivem no banco: a fila sobrevive a reinicio,
etapa concluida nunca re-executa (transicoes com guarda) e a recuperacao
no boot decide pelo log de handoff gravado, nunca por memoria.
"""
import time
from pathlib import Path

import pytest

from app import estudos
from app.db import Database


@pytest.fixture(autouse=True)
def _db_isolado(monkeypatch, tmp_path):
    """Cada teste com seu proprio banco (S2: a fila e persistente)."""
    monkeypatch.setattr(estudos, "db", Database(tmp_path / "jobs.db"))


@pytest.fixture
def estudos_banco(_db_isolado):
    """O banco que o modulo estudos esta usando neste teste."""
    return estudos.db


def _espera(cond, timeout=5.0):
    limite = time.time() + timeout
    while time.time() < limite:
        if cond():
            return True
        time.sleep(0.02)
    return False


class _Proc:
    def __init__(self, codigo=0, stdout=None):
        self._codigo = codigo
        if codigo == 0 and stdout is not None:
            # o pipeline real grava cada passo com flush; o fake grava os
            # MESMOS marcos para a drenagem do log provar o envio (S3)
            stdout.write("=== 8. Enviando PDF\n=== CONCLUIDO\n")
            stdout.flush()

    def wait(self):
        return self._codigo

    def poll(self):
        return self._codigo


def _configura(monkeypatch, tmp_path, **extra):
    (tmp_path / "pipeline.py").write_text("#", encoding="utf-8")
    valores = {
        "estudos.ativo": True,
        "estudos.python": "/venv/python.exe",
        "estudos.pasta": str(tmp_path),
        "estudos.whatsapp": "",
        **extra,
    }
    monkeypatch.setattr(
        estudos.config, "get", lambda chave, padrao=None: valores.get(chave, padrao)
    )
    avisos = []
    monkeypatch.setattr(
        estudos, "notify", lambda *a, **k: avisos.append(a[0] if a else "")
    )
    return avisos


# ----------------------------------------------------------- no proprio banco
def test_criacao_e_idempotente(tmp_path):
    banco = Database(tmp_path / "jobs.db")
    assert banco.create_job(audio_path="a.mp3") is True
    # a mesma gravacao de novo = UM job, nunca dois
    assert banco.create_job(audio_path="a.mp3") is False
    assert banco.job_contagens() == {"PENDENTE": 1}


def test_snapshot_de_recording_e_drive_no_momento_da_criacao(tmp_path):
    banco = Database(tmp_path / "jobs.db")
    banco.create_session(
        {"id": "sess-1", "started_at": time.time(), "state": "COMPLETED"}
    )
    banco.update_session(
        "sess-1", final_path="x.mp3", drive_file_id="gdrive123"
    )
    assert banco.create_job(audio_path="x.mp3")
    job = banco.list_jobs(1)[0]
    assert job["recording_id"] == "sess-1"
    assert job["drive_file_id"] == "gdrive123"
    # coluna de metadados pronta para a S4, vazia por enquanto
    assert job["metadados"] is None


def test_claim_ordena_e_conta_tentativas(tmp_path):
    banco = Database(tmp_path / "jobs.db")
    banco.create_job(audio_path="1.mp3")
    banco.create_job(audio_path="2.mp3")
    primeiro = banco.claim_job()
    segundo = banco.claim_job()
    assert {primeiro["audio_path"], segundo["audio_path"]} == {"1.mp3", "2.mp3"}
    assert primeiro["estado"] == "EXECUTANDO"
    assert primeiro["etapa"] == "PRE-FLIGHT"
    assert primeiro["tentativas"] == 1
    # so PENDENTE e reclamavel: nada de dupla captura
    assert banco.claim_job() is None


def test_etapa_concluida_nunca_reexecuta_nem_sobrescreve(tmp_path):
    banco = Database(tmp_path / "jobs.db")
    banco.create_job(audio_path="a.mp3")
    job_id = banco.claim_job()["job_id"]
    assert banco.job_concluir(job_id, resultado="log.txt") is True
    # re-execucao tardia (reinicio, corrida) nao vira True de novo...
    assert banco.job_concluir(job_id, resultado="log2.txt") is False
    # ...nem uma falha atrasada sobrescreve o CONCLUIDO
    assert banco.job_falhar(job_id, "timeout antigo") is False
    job = banco.get_job(job_id)
    assert job["estado"] == "CONCLUIDO"
    assert job["resultado"] == "log.txt"
    assert job["erro"] is None
    assert job["finished_at"]


def test_transicoes_so_desde_o_estado_certo(tmp_path):
    banco = Database(tmp_path / "jobs.db")
    banco.create_job(audio_path="a.mp3")
    job_id = banco.list_jobs(1)[0]["job_id"]
    # PENDENTE nao conclui nem aguarda: precisa passar por claim
    assert banco.job_concluir(job_id) is False
    assert banco.job_aguardar(job_id, "x") is False
    assert banco.claim_job()["job_id"] == job_id
    assert banco.job_aguardar(job_id, "sem rede") is True
    # AGUARDANDO nao conclui direto; volta primeiro para PENDENTE
    assert banco.job_concluir(job_id) is False
    assert banco.job_retomar() == 1
    assert banco.claim_job()["job_id"] == job_id
    assert banco.job_concluir(job_id, resultado="ok") is True


def test_recuperacao_reenfileira_somente_executando(tmp_path):
    banco = Database(tmp_path / "jobs.db")
    banco.create_job(audio_path="a.mp3")
    em_execucao = banco.claim_job()
    banco.create_job(audio_path="b.mp3")  # fica PENDENTE
    assert banco.job_reenfileirar(em_execucao["job_id"]) is True
    assert banco.job_contagens().get("PENDENTE") == 2
    # de novo, apos ja estar PENDENTE: nao ha o que reenfileirar
    assert banco.job_reenfileirar(em_execucao["job_id"]) is False


def test_aguardando_retorna_em_lote_e_cancelamento(tmp_path):
    banco = Database(tmp_path / "jobs.db")
    for nome in ("a.mp3", "b.mp3"):
        banco.create_job(audio_path=nome)
    j1 = banco.claim_job()
    j2 = banco.claim_job()
    banco.job_aguardar(j1["job_id"], "sem rede")
    banco.job_aguardar(j2["job_id"], "autenticacao expirada")
    assert banco.job_contagens()["AGUARDANDO_INTERVENCAO"] == 2
    assert banco.job_motivo() in ("sem rede", "autenticacao expirada")
    # um cancelado; o outro volta para a fila
    assert banco.job_cancelar(j2["job_id"]) is True
    assert banco.job_retomar() == 1
    cont = banco.job_contagens()
    assert cont.get("PENDENTE") == 1
    assert cont.get("CANCELADO") == 1
    # o pendente roda; o cancelado nunca mais e reclamado
    assert banco.claim_job() is not None
    assert banco.claim_job() is None


def test_estado_sobrevive_a_nova_instancia_do_banco(tmp_path):
    arquivo = tmp_path / "jobs.db"
    banco = Database(arquivo)
    banco.create_job(audio_path="a.mp3")
    job_id = banco.claim_job()["job_id"]
    banco.update_job(job_id, etapa="PIPELINE", resultado="handoff.log")
    # "reinicio": novo objeto apontando para o MESMO arquivo
    de_volta = Database(arquivo)
    job = de_volta.get_job(job_id)
    assert job["estado"] == "EXECUTANDO"
    assert job["etapa"] == "PIPELINE"
    assert job["resultado"] == "handoff.log"


# --------------------------------------------- recuperacao no boot (estudos)
def test_boot_conclui_pelo_log_quando_o_pipeline_terminou(
    monkeypatch, tmp_path, estudos_banco
):
    banco = estudos_banco
    banco.create_job(audio_path=str(tmp_path / "pregacao.mp3"))
    job = banco.claim_job()
    log_handoff = tmp_path / "handoff_20261018.log"
    log_handoff.write_text(
        "# handoff\n=== 8. Enviando PDF\n=== CONCLUIDO\n", encoding="utf-8"
    )
    banco.update_job(job["job_id"], etapa="PIPELINE", resultado=str(log_handoff))
    monkeypatch.setattr(estudos, "ligado", lambda: False)
    avisos = []
    monkeypatch.setattr(
        estudos, "notify", lambda *a, **k: avisos.append(a[0] if a else "")
    )

    total = estudos.retomar_apos_reinicio()

    # prova gravada no log: job ja tinha terminado - nada volta a fila
    assert total == 0
    job = banco.get_job(job["job_id"])
    assert job["estado"] == "CONCLUIDO"
    assert job["etapa"] == "FINAL_INCERTO"  # tentativa antiga nao prova aceite
    assert avisos == []


def test_boot_reefileira_o_interrompido_sem_prova(
    monkeypatch, tmp_path, estudos_banco
):
    banco = estudos_banco
    banco.create_job(audio_path=str(tmp_path / "pregacao.mp3"))
    job = banco.claim_job()  # morreu no meio: sem log de handoff
    monkeypatch.setattr(estudos, "ligado", lambda: False)
    avisos = []
    monkeypatch.setattr(
        estudos, "notify", lambda *a, **k: avisos.append(a[0] if a else "")
    )

    total = estudos.retomar_apos_reinicio()

    assert total == 1
    assert banco.get_job(job["job_id"])["estado"] == "PENDENTE"
    assert avisos == ["estudos_retomando"]


def test_boot_nao_mexe_nos_outros_estados(monkeypatch, tmp_path, estudos_banco):
    banco = estudos_banco
    # um CONCLUIDO, um AGUARDANDO e um ERRO de antes do reinicio
    banco.create_job(audio_path="c.mp3")
    banco.job_concluir(banco.claim_job()["job_id"], resultado="x")
    banco.create_job(audio_path="p.mp3")
    pendente = banco.claim_job()
    banco.job_aguardar(pendente["job_id"], "autenticacao expirada")
    banco.create_job(audio_path="e.mp3")
    falho = banco.claim_job()
    banco.job_falhar(falho["job_id"], "codigo 1")
    monkeypatch.setattr(estudos, "ligado", lambda: False)

    assert estudos.retomar_apos_reinicio() == 0

    cont = banco.job_contagens()
    assert cont.get("CONCLUIDO") == 1
    assert cont.get("AGUARDANDO_INTERVENCAO") == 1
    assert cont.get("ERRO") == 1
    assert "PENDENTE" not in cont


# ------------------------------------------ fluxo completo com o trabalhador
def test_enfileirar_nao_duplica_e_conclui_no_banco(monkeypatch, tmp_path):
    _configura(monkeypatch, tmp_path)
    chamadas = []
    monkeypatch.setattr(
        estudos.subprocess,
        "Popen",
        # o fake grava somente a tentativa; sem ID o aceite fica incerto
        lambda cmd, **kw: chamadas.append(cmd)
        or _Proc(0, stdout=kw.get("stdout")),
    )
    caminho = str(tmp_path / "pregacao.mp3")

    estudos.enfileirar(caminho)
    estudos.enfileirar(caminho)  # duplicata: cai no UNIQUE
    assert _espera(lambda: chamadas)
    assert _espera(
        lambda: estudos.db.job_contagens().get("CONCLUIDO", 0) == 1
    )

    time.sleep(0.2)
    assert len(chamadas) == 1  # disparou UMA vez
    cont = estudos.db.job_contagens()
    assert cont.get("CONCLUIDO") == 1
    assert cont.get("PENDENTE", 0) == 0
    assert cont.get("EXECUTANDO", 0) == 0
    job = estudos.db.list_jobs(1)[0]
    assert job["etapa"] == "FINAL_INCERTO"
    assert job["resultado"] and "handoff" in Path(job["resultado"]).name
    # o log de handoff prova o que foi disparado (e serve de marcador
    # de conclusao para a recuperacao no boot)
    texto = Path(job["resultado"]).read_text(encoding="utf-8")
    assert caminho in texto


def test_falha_do_pipeline_vira_estado_erro_com_motivo(monkeypatch, tmp_path):
    _configura(monkeypatch, tmp_path)
    chamadas = []
    monkeypatch.setattr(
        estudos.subprocess,
        "Popen",
        lambda cmd, **kw: chamadas.append(cmd) or _Proc(1),
    )
    estudos.enfileirar(str(tmp_path / "pregacao.mp3"))
    assert _espera(lambda: estudos.db.job_contagens().get("ERRO", 0) == 1)
    job = estudos.db.list_jobs(1)[0]
    assert job["estado"] == "ERRO"
    assert "codigo 1" in job["erro"]
    assert job["finished_at"]


def test_preflight_pausa_no_banco_e_diagnostico_retoma(
    monkeypatch, tmp_path
):
    _configura(monkeypatch, tmp_path)
    chamadas = []
    monkeypatch.setattr(
        estudos.subprocess,
        "Popen",
        lambda cmd, **kw: chamadas.append(cmd) or _Proc(0),
    )
    monkeypatch.setattr(estudos, "verificar_saude", lambda force=False: "auth")
    monkeypatch.setattr(estudos, "_renovar_sessao", lambda: False)
    caminho = str(tmp_path / "pregacao.mp3")

    estudos.enfileirar(caminho)
    assert _espera(
        lambda: estudos.db.job_contagens().get("AGUARDANDO_INTERVENCAO", 0) == 1
    )
    # nada disparado, job guardado com motivo e pre-flight marcado
    assert chamadas == []
    job = estudos.db.list_jobs(1)[0]
    assert job["estado"] == "AGUARDANDO_INTERVENCAO"
    assert job["motivo"] == "autenticacao expirada"
    assert job["etapa"] == "PRE-FLIGHT"
    assert job["tentativas"] == 1

    # sessao volta: o diagnosticador devolve o job a fila e ele CONCLUI
    monkeypatch.setattr(estudos, "verificar_saude", lambda force=False: "ok")
    resultado = estudos.diagnosticar()
    assert resultado["retomados"] == 1
    assert _espera(
        lambda: estudos.db.job_contagens().get("CONCLUIDO", 0) == 1
    )
    job = estudos.db.get_job(job["job_id"])
    assert job["estado"] == "CONCLUIDO"
    assert job["tentativas"] == 2  # segunda passada: claim de novo contou
    assert job["motivo"] is None


def test_diagnostico_acorda_pendente_esquecido(monkeypatch, tmp_path):
    _configura(monkeypatch, tmp_path)
    chamadas = []
    monkeypatch.setattr(
        estudos.subprocess,
        "Popen",
        lambda cmd, **kw: chamadas.append(cmd) or _Proc(0),
    )
    monkeypatch.setattr(estudos, "verificar_saude", lambda force=False: "ok")
    # job PENDENTE sem nenhum sinal a caminho: nao ha quem o acorde
    estudos.db.create_job(audio_path=str(tmp_path / "pregacao.mp3"))
    time.sleep(0.1)
    assert chamadas == []
    estudos.diagnosticar()
    assert _espera(
        lambda: estudos.db.job_contagens().get("CONCLUIDO", 0) == 1
    )
    assert len(chamadas) == 1


def test_status_conta_pelo_banco(monkeypatch, tmp_path):
    _configura(monkeypatch, tmp_path)
    banco = estudos.db
    banco.create_job(audio_path="a.mp3")
    job = banco.claim_job()
    estudos._aguardar(job["job_id"], "autenticacao expirada")

    st = estudos.status()
    assert st["aguardando"] == 1
    assert st["motivo"] == "autenticacao expirada"
    assert st["fila"] == 0

    banco.job_retomar()
    st = estudos.status()
    assert st["aguardando"] == 0
    assert st["motivo"] == ""
    assert st["fila"] == 1


# -------------------------------------------- progresso por job (S3)
def test_barra_esconde_quando_nao_ha_nada(monkeypatch, tmp_path):
    b = estudos.barra()
    assert b["mostrar"] is False
    assert b["percentual"] == 0
    assert b["etapas"] == []


def test_barra_somente_com_prova_no_banco(monkeypatch, tmp_path):
    banco = estudos.db
    # gravacao em curso: passo 1 ativo, nenhum marco concluido
    banco.create_session(
        {"id": "s1", "started_at": time.time(), "state": "RECORDING"}
    )
    b = estudos.barra()
    assert b["mostrar"] is True
    assert b["percentual"] == 0
    assert b["etapas"][0] == {"n": 1, "nome": "GRAVACAO", "tom": "ativo"}
    assert all(e["tom"] == "pendente" for e in b["etapas"][1:])
    assert b["descricao"] == "Gravando"

    # gravacao terminou e o MP3 existe: 2 de 7 (drive ainda pendente)
    banco.update_session(
        "s1", ended_at=time.time(), final_path="x.mp3", final_bytes=1000
    )
    b = estudos.barra()
    assert b["percentual"] == 29  # 2/7 = 28,6 arredondado
    assert b["etapas"][0]["tom"] == "concluido"
    assert b["etapas"][1]["tom"] == "concluido"
    assert b["etapas"][2]["tom"] == "ativo"  # enviando ao Drive

    # prova do Drive: 3 de 7
    banco.update_session("s1", drive_file_id="gdrive9")
    b = estudos.barra()
    assert b["percentual"] == 43
    assert b["etapas"][2]["tom"] == "concluido"


def test_barra_pinta_espera_e_erro_com_o_tom_do_job(monkeypatch, tmp_path):
    banco = estudos.db
    banco.create_job(audio_path="x.mp3")  # sem sessao ligada: base 0
    job = banco.claim_job()
    banco.job_aguardar(job["job_id"], "autenticacao expirada")

    b = estudos.barra()
    assert b["estado"] == "AGUARDANDO_INTERVENCAO"
    assert b["etapas"][3]["tom"] == "aguardando"  # NOTEBOOKLM parado
    assert "autenticacao expirada" in b["descricao"]
    assert b["percentual"] == 0  # zero prova de gravacao+mp3+drive

    banco.job_retomar()
    job = banco.claim_job()
    banco.update_job(job["job_id"], etapa="PDF")
    b = estudos.barra()
    concluidos = [e["nome"] for e in b["etapas"] if e["tom"] == "concluido"]
    assert concluidos == ["NOTEBOOKLM", "ESTUDO"]  # marcos 4 e 5 provados
    assert b["etapas"][5]["tom"] == "ativo"  # PDF em conversao
    assert b["percentual"] == 29  # 2 marcos do pipeline (base 0)

    banco.job_falhar(job["job_id"], "codigo 1")
    b = estudos.barra()
    assert b["etapas"][5]["tom"] == "erro"  # parou ONDE falhou
    assert "codigo 1" in b["descricao"]


def test_tarefa_concluida_chega_a_cem_sem_fingir_envio(monkeypatch, tmp_path):
    banco = estudos.db
    banco.create_session(
        {"id": "s1", "started_at": time.time(), "state": "COMPLETED"}
    )
    banco.update_session(
        "s1",
        ended_at=time.time(),
        final_path="x.mp3",
        final_bytes=10,
        drive_file_id="g1",
    )
    banco.create_job(audio_path="x.mp3")
    job = banco.claim_job()
    # marcos 1-3 provados pela gravacao, nada do pipeline ainda
    assert estudos._percentual(estudos._marcos_concluidos(job)) == 43

    banco.job_concluir(job["job_id"], etapa="FINAL")
    job = banco.get_job(job["job_id"])
    assert estudos._percentual_job(job) == 100

    # O envio foi pulado, mas a tarefa concluida deve indicar 100%.
    banco.create_session(
        {"id": "s2", "started_at": time.time(), "state": "COMPLETED"}
    )
    banco.update_session(
        "s2",
        ended_at=time.time(),
        final_path="y.mp3",
        final_bytes=10,
        drive_file_id="g2",
    )
    banco.create_job(audio_path="y.mp3")
    job2 = banco.claim_job()
    banco.job_concluir(job2["job_id"], etapa="FINAL_SEM_ENVIO")
    job2 = banco.get_job(job2["job_id"])
    assert estudos._percentual(estudos._marcos_concluidos(job2)) == 86
    assert estudos._percentual_job(job2) == 100
    assert estudos._job_publico()["percentual"] == 100
    barra = estudos.barra()
    assert barra["percentual"] == 100
    assert barra["descricao"].startswith("Estudo pronto")
    assert barra["etapas"][-1]["nome"] == "WHATSAPP (PULADO)"
    assert barra["etapas"][-1]["tom"] == "pulado"


def test_evento_final_sem_envio_publica_cem(monkeypatch, tmp_path):
    capturas = []
    monkeypatch.setattr(estudos, "notify", lambda *a, **k: capturas.append(k["payload"]))
    estudos._publicar_job(
        {"job_id": "j1", "estado": "CONCLUIDO", "etapa": "FINAL_SEM_ENVIO"},
        "FINAL_SEM_ENVIO",
    )
    assert capturas[0]["percentual"] == 100
    assert capturas[0]["etapa"] == "FINAL_SEM_ENVIO"


def test_drenagem_so_emite_o_que_ja_foi_escrito(monkeypatch, tmp_path):
    capturas = []
    monkeypatch.setattr(
        estudos, "notify", lambda *a, **k: capturas.append((a, k))
    )
    banco = estudos.db
    banco.create_job(audio_path="x.mp3")
    job = banco.claim_job()
    arquivo = tmp_path / "handoff_1.log"
    # passo 5 completo + linha 6 ainda INCOMPLETA (sem quebra de linha)
    arquivo.write_bytes(b"# handoff\n=== 5. Gerando o ESTUDO\n=== 6.")
    visto = {"envio": False, "pulado": False}
    esperado_p1 = len(b"# handoff\n=== 5. Gerando o ESTUDO\n")

    p1 = estudos._drenar_log(arquivo, 0, job, visto)
    assert p1 == esperado_p1  # consumiu ate a ultima quebra de linha
    assert banco.get_job(job["job_id"])["etapa"] == "ESTUDO"
    assert len(capturas) == 1
    assert capturas[0][0][0] == "job_progress"
    payload = capturas[0][1]["payload"]
    assert payload["job_id"] == job["job_id"]
    assert payload["etapa"] == "ESTUDO"
    assert payload["percentual"] == 14  # 1 de 7
    assert payload["seq"] > 0

    # a MESMA drenagem de novo nao emite nada (a linha incompleta do fim
    # nao forma marco e sera relida quando completar)
    assert estudos._drenar_log(arquivo, p1, job, visto) == p1
    assert len(capturas) == 1

    # resto + passo 6 completo + passo 8 (envio) + fim
    with open(arquivo, "ab") as fh:
        fh.write(b" Baixando o relatorio\n=== 8. Enviando PDF\n=== CONCLUIDO\n")
    p2 = estudos._drenar_log(arquivo, p1, job, visto)
    assert p2 == arquivo.stat().st_size  # termina em \n: tudo consumido
    assert visto["envio"] is True
    etapas = [c[1]["payload"]["etapa"] for c in capturas]
    assert etapas == ["ESTUDO", "PDF", "WHATSAPP"]
    assert banco.get_job(job["job_id"])["etapa"] == "WHATSAPP"


def test_seq_de_progresso_sempre_cresce(monkeypatch, tmp_path):
    # duas emissoes no MESMO milissegundo nao podem empatar: o agente
    # descarta seq <= ultima e o marco final sumiria do celular
    a = estudos._seq()
    b = estudos._seq()
    assert b > a


def test_espera_emite_marco_de_alerta(monkeypatch, tmp_path):
    _configura(monkeypatch, tmp_path)
    capturas = []
    monkeypatch.setattr(
        estudos, "notify", lambda *a, **k: capturas.append((a, k))
    )
    monkeypatch.setattr(estudos, "verificar_saude", lambda force=False: "auth")
    monkeypatch.setattr(estudos, "_renovar_sessao", lambda: False)

    estudos.enfileirar(str(tmp_path / "pregacao.mp3"))
    assert _espera(
        lambda: estudos.db.job_contagens().get("AGUARDANDO_INTERVENCAO", 0) == 1
    )

    progresso = [
        k["payload"]
        for a, k in capturas
        if a and a[0] == "job_progress"
    ]
    # o primeiro marco e a entrada do job (pre-flight)...
    assert progresso and progresso[0]["etapa"] == "PRE-FLIGHT"
    # ...e o ultimo e o alerta da espera, com motivo e nivel de aviso
    alerta = [p for p in progresso if p["estado"] == "AGUARDANDO_INTERVENCAO"]
    assert alerta and "autenticacao" in alerta[-1]["descricao"]
    avisos_de_nivel = [
        k.get("level") for a, k in capturas
        if a and a[0] == "job_progress" and a[1] == alerta[-1]["descricao"]
    ]
    assert avisos_de_nivel and avisos_de_nivel[0] == "warning"


def test_status_expoe_job_e_barra(monkeypatch, tmp_path):
    _configura(monkeypatch, tmp_path)
    banco = estudos.db
    banco.create_job(audio_path="x.mp3")

    st = estudos.status()
    assert st["job"] and st["job"]["job_id"]
    assert st["job"]["etapa"] == "PENDENTE" or st["job"]["estado"] == "PENDENTE"
    assert st["barra"]["mostrar"] is True
    assert st["barra"]["job_id"] == st["job"]["job_id"]
