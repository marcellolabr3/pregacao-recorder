"""Destinos de gravacao: SSD desconectado nao pode passar despercebido.

O caso que motivou o modulo: o SSD foi desmontado (o systemd so monta no
boot), o diretorio configurado ``/mnt/ssd/pregacoes`` continuou existindo
dentro do cartao SD e a gravacao "funcionou" la sem que ninguem percebesse.

Os testes mockiam ``/proc/mounts`` e ``os.path.ismount`` para valerem tanto
no Linux quanto no Windows, onde rodam.
"""
from pathlib import Path

from app.storage import destinos as dest

SD = "/opt/pregacao-recorder/recordings"
SSD = "/mnt/ssd"
ALVO_SSD = SSD + "/pregacoes"

MONTAGENS = [
    {"device": "/dev/mmcblk0p2", "mount": "/", "fstype": "ext4", "opts": "rw"},
    {"device": "/dev/sda1", "mount": SSD, "fstype": "ext4", "opts": "rw"},
]
MONTAGENS_SEM_SSD = [MONTAGENS[0]]
MONTAGENS_TMP = MONTAGENS + [
    {"device": "tmpfs", "mount": "/tmp", "fstype": "tmpfs", "opts": "rw"},
]

DISCO = {"ok": True, "livre_gb": 100.0, "total_gb": 200.0, "livre_mb": 102400}


def _prepara(monkeypatch, montados, montagens=None, gravavel=True):
    """Faz o modulo enxergar so as montagens combinadas."""
    montados = set(montados)

    def fake_ismount(p):
        texto = str(p).replace("\\", "/").rstrip("/")
        if texto == "":
            return True  # "/" (a raiz e sempre montagem)
        if texto in montados:
            return True
        # raiz de drive: no Windows e onde a subida de monta_raiz para
        return len(texto) == 2 and texto[1] == ":"

    monkeypatch.setattr(dest.os.path, "ismount", fake_ismount)
    monkeypatch.setattr(dest, "_rotulos", lambda: {})
    monkeypatch.setattr(dest, "_gravavel", lambda p: gravavel)
    monkeypatch.setattr(dest, "_espaco", lambda p: dict(DISCO))
    if montagens is None:
        montagens = MONTAGENS if SSD in montados else MONTAGENS_SEM_SSD
    linhas = montagens
    monkeypatch.setattr(dest, "montagens", lambda: [dict(m) for m in linhas])


# ---------------------------------------------------------------------------
# intencao / monta_raiz - a distincao que sustenta todo o resto
# ---------------------------------------------------------------------------
def test_intencao_aponta_para_o_disco_esperado():
    assert dest.intencao(ALVO_SSD) == SSD
    assert dest.intencao("/mnt/ssd") == SSD
    # /media e ambiguo por projeto: "/media/<label>/<pasta>" e
    # "/media/<usuario>/<label>" tem o mesmo numero de segmentos. O modulo
    # so precisa saber que ALI ha intencao de disco externo - a diferenca de
    # profundidade e resolvida conferindo a montagem real (ver
    # test_sem_aviso_quando_a_montagem_e_um_ancestral).
    assert dest.intencao("/media/SSD/pregacoes") == "/media/SSD/pregacoes"
    assert dest.intencao("/media/aska/SSD/pregacoes") == "/media/aska/SSD"
    # pasta padrao e caminho comum: sem intencao de disco externo
    assert dest.intencao(SD) == ""
    assert dest.intencao("/home/aska/pregacoes") == ""


def test_monta_raiz_sobe_ate_o_ponto_de_montagem(monkeypatch):
    _prepara(monkeypatch, montados={SSD})
    assert dest.monta_raiz(ALVO_SSD) == SSD

    _prepara(monkeypatch, montados=set())
    assert dest.monta_raiz(ALVO_SSD) == "/"


def test_unescape_desfaz_o_escape_do_proc_mounts():
    assert dest._unescape("/mnt/disco\\040novo") == "/mnt/disco novo"
    assert dest._unescape("/mnt/sempce") == "/mnt/sempce"


def test_so_fs_volateis_e_de_sistema_sao_ignorados():
    assert dest._e_sistema("/") is True
    assert dest._e_sistema("/var/log") is True
    assert dest._e_sistema(SSD) is False
    assert dest._e_sistema("/home/aska") is False
    assert "tmpfs" in dest.PSEUDO_FS


# ---------------------------------------------------------------------------
# o bug original: aviso quando o destino caiu no cartao SD
# ---------------------------------------------------------------------------
def test_aviso_quando_ssd_desmontado(monkeypatch):
    _prepara(monkeypatch, montados=set(), montagens=MONTAGENS_SEM_SSD)
    msg = dest.aviso(ALVO_SSD, SD)
    assert msg, "sem aviso o SSD desmontado passaria desperbido"
    assert "cartao SD" in msg
    assert SSD in msg


def test_sem_aviso_quando_ssd_montado(monkeypatch):
    _prepara(monkeypatch, montados={SSD})
    assert dest.aviso(ALVO_SSD, SD) is None


def test_sem_aviso_quando_a_montagem_e_um_ancestral(monkeypatch):
    # o disco pode montar num ancestral do caminho pedido (label com
    # subpasta): continua disponivel, so nao pode ser "/" no lugar dele.
    linhas = MONTAGENS_SEM_SSD + [
        {"device": "/dev/sdb1", "mount": "/media/SSD", "fstype": "ext4", "opts": "rw"}
    ]
    _prepara(monkeypatch, montados={"/media/SSD"}, montagens=linhas)
    assert dest.aviso("/media/SSD/pregacoes", SD) is None

    _prepara(monkeypatch, montados=set(), montagens=MONTAGENS_SEM_SSD)
    assert dest.aviso("/media/SSD/pregacoes", SD) is not None


def test_sem_aviso_para_a_pasta_padrao_do_sd(monkeypatch):
    _prepara(monkeypatch, montados=set(), montagens=MONTAGENS_SEM_SSD)
    assert dest.aviso(SD, SD) is None


def test_atual_revela_onde_de_verdade_esta_gravando(monkeypatch):
    _prepara(monkeypatch, montados=set(), montagens=MONTAGENS_SEM_SSD)
    situacao = dest.atual(ALVO_SSD, SD)
    assert situacao["disponivel"] is False
    assert situacao["no_cartao_sd"] is True
    assert situacao["raiz_esperada"] == SSD
    assert situacao["raiz_real"] == "/"

    _prepara(monkeypatch, montados={SSD})
    situacao = dest.atual(ALVO_SSD, SD)
    assert situacao["disponivel"] is True
    assert situacao["no_cartao_sd"] is False
    assert situacao["raiz_real"] == SSD


# ---------------------------------------------------------------------------
# lista de destinos
# ---------------------------------------------------------------------------
def test_destinos_inclui_ssd_e_cartao_sd(monkeypatch):
    _prepara(monkeypatch, montados={SSD})
    itens = dest.destinos(ALVO_SSD, SD)
    caminhos = [i["caminho"] for i in itens]

    assert ALVO_SSD in caminhos
    assert SD in caminhos
    atual = [i for i in itens if i["atual"]]
    assert len(atual) == 1
    assert atual[0]["caminho"] == ALVO_SSD
    assert atual[0]["externo"] is True


def test_destinos_ssd_desmontado_fica_marcado_como_indisponivel(monkeypatch):
    _prepara(monkeypatch, montados=set(), montagens=MONTAGENS_SEM_SSD)
    itens = dest.destinos(ALVO_SSD, SD)
    alvo = next(i for i in itens if i["caminho"] == ALVO_SSD)
    assert alvo["montado"] is False
    assert alvo["gravavel"] is False  # nao tenta criar pasta no SD por engano
    assert alvo["raiz"] == SSD  # mantem a intencao, nao a raiz real


def test_destinos_sempre_oferece_o_cartao_sd_como_colchao(monkeypatch):
    _prepara(monkeypatch, montados={SSD})
    itens = dest.destinos(ALVO_SSD, SD)
    sd = next(i for i in itens if i["caminho"] == SD)
    assert sd["externo"] is False
    assert sd["montado"] is True
    assert sd["gravavel"] is True


# ---------------------------------------------------------------------------
# escolher - recusar e o que evita o engano
# ---------------------------------------------------------------------------
def test_escolher_aceita_ssd_montado(monkeypatch):
    _prepara(monkeypatch, montados={SSD})
    assert dest.escolher(ALVO_SSD, SD) == (True, "")


def test_escolher_recusa_ssd_desmontado(monkeypatch):
    _prepara(monkeypatch, montados=set(), montagens=MONTAGENS_SEM_SSD)
    ok, erro = dest.escolher(ALVO_SSD, SD)
    assert ok is False
    assert SSD in erro
    assert "montado" in erro


def test_escolher_aceita_o_cartao_sd(monkeypatch):
    _prepara(monkeypatch, montados=set(), montagens=MONTAGENS_SEM_SSD)
    assert dest.escolher(SD, SD) == (True, "")
    assert dest.escolher(SD + "/2026", SD) == (True, "")


def test_escolher_recusa_arquivo_temporario(monkeypatch):
    _prepara(monkeypatch, montados={"/tmp"}, montagens=MONTAGENS_TMP)
    ok, erro = dest.escolher("/tmp/gravacoes", SD)
    assert ok is False
    assert "reboot" in erro


def test_escolher_recusa_vazio(monkeypatch):
    _prepara(monkeypatch, montados=set(), montagens=MONTAGENS_SEM_SSD)
    ok, erro = dest.escolher("", SD)
    assert ok is False
    assert erro  # nunca recusa em silencio


def test_escolher_recusa_dispositivo_fora_da_lista(monkeypatch):
    # /var e ponto de montagem do proprio sistema: fica de fora da lista de
    # destinos e a recusa precisa dizer o motivo.
    linhas = MONTAGENS_SEM_SSD + [
        {"device": "/dev/mmcblk0p3", "mount": "/var", "fstype": "ext4", "opts": "rw"}
    ]
    _prepara(monkeypatch, montados={"/var"}, montagens=linhas)
    ok, erro = dest.escolher("/var/gravacoes", SD)
    assert ok is False
    assert "dispositivo" in erro
