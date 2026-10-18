"""Destinos de gravacao disponiveis e saude do destino escolhido.

Por que este modulo existe
--------------------------
O SSD externo e montado pelo ``fstab`` em ``/mnt/ssd``, mas o systemd so
monta no BOOT - e com ``nofail`` ele desiste em silencio se o disco nao
estiver conectado a tempo. Depois disso o diretorio configurado
(``/mnt/ssd/pregacoes``) continua existindo: e apenas uma pasta na raiz do
cartao SD. A gravacao "funciona", cai no SD e ninguem percebe - que e
exatamente o problema relatado.

Aqui se separa a INTENCAO ("gravar no SSD") do FATO ("o ponto de montagem
esta montado agora?"), para a interface:
  * mostrar o aviso quando o destino caiu no cartao SD;
  * listar os destinos realmente disponiveis, inclusive quando o SSD
    volta em outro ponto (ex.: ``/media/aska/SSD``) apos uma troca.

Tudo aqui e calculado a partir de ``/proc/mounts`` e de ``os.path.ismount``:
nao ha chamadas com sudo nem dependencia nova.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from ..logging_setup import get
from . import layout

log = get("storage")

# Sistemas de arquivos que NUNCA sao destino: pseudo-fs do kernel, tmpfs
# volatil (some no reboot) e o overlay das imagens empacotadas.
PSEUDO_FS = {
    "autofs", "binfmt_misc", "bpf", "cgroup", "cgroup2", "configfs",
    "debugfs", "devpts", "devtmpfs", "fusectl", "mqueue", "nsfs", "overlay",
    "proc", "pstore", "ramfs", "rpc_pipefs", "securityfs", "squashfs",
    "sysfs", "tmpfs", "tracefs",
}

# Prefixos do proprio sistema: gravar ali e gravar no cartao SD.
PREFIXOS_SISTEMA = (
    "/proc", "/sys", "/dev", "/run", "/snap", "/var", "/tmp", "/boot",
    "/usr",
)

SUBPASTA = "pregacoes"  # subpasta criada dentro de cada disco candidato


def _posix(texto: str) -> str:
    """Caminhos deste modulo sao sempre POSIX (o alvo e Debian).

    Os testes rodam tambem no Windows, onde ``Path`` inverte a barra; sem
    normalizar o teste passaria a medir o sistema de arquivos local em vez
    do comportamento do aparelho.
    """
    return texto.replace("\\", "/") if os.name == "nt" else texto


def _junta(raiz: str, nome: str) -> str:
    """Junta em POSIX puro (``Path(a) / b`` mudaria de barra no Windows)."""
    return _posix(raiz).rstrip("/") + "/" + nome


def _unescape(texto: str) -> str:
    """Desfaz o escape do ``/proc/mounts`` (espaco vira ``\\040``)."""
    return (
        texto.replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\\n")
        .replace("\\134", "\\")
    )


def _rotulos() -> Dict[str, str]:
    """Mapa ``/dev/sda1 -> pregacoes`` lido de ``/dev/disk/by-label``.

    Ler por la e mais barato (e nao exige sudo) que chamar ``lsblk``/``blkid``.
    """
    mapa: Dict[str, str] = {}
    try:
        for item in Path("/dev/disk/by-label").iterdir():
            try:
                alvo = str(item.resolve())
            except OSError:
                continue
            mapa[alvo] = item.name.replace("\\x20", " ")
    except OSError:
        pass
    return mapa


def montagens() -> List[Dict[str, str]]:
    """Lista ``/proc/mounts`` sem chamar nenhum programa externo."""
    out: List[Dict[str, str]] = []
    if os.name == "nt":
        # Windows nao tem /proc; os destinos daqui sao resolvidos por
        # os.path.ismount - sem warning (evitava spam no console do PC).
        return out
    try:
        linhas = Path("/proc/mounts").read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        log.warning("nao foi possivel ler /proc/mounts: %s", exc)
        return out
    for linha in linhas.splitlines():
        partes = linha.split()
        if len(partes) < 4:
            continue
        out.append(
            {
                "device": _unescape(partes[0]),
                "mount": _unescape(partes[1]),
                "fstype": partes[2],
                "opts": partes[3],
            }
        )
    return out


def _e_sistema(mount: str) -> bool:
    return mount == "/" or mount in PREFIXOS_SISTEMA or any(
        mount.startswith(p + "/") for p in PREFIXOS_SISTEMA
    )


def externas() -> List[Dict[str, str]]:
    """Montagens que NAO sao o cartao SD nem pseudo-fs (SSD, HD, pen drive)."""
    rotulos = _rotulos()
    return [
        {
            **m,
            "label": rotulos.get(m["device"], ""),
        }
        for m in montagens()
        if m["fstype"] not in PSEUDO_FS and not _e_sistema(m["mount"])
    ]


def monta_raiz(caminho: Path | str) -> str:
    """Ponto de montagem que hospeda ``caminho`` AGORA (o mais próximo)."""
    atual = _posix(str(caminho)).rstrip("/") or "/"
    while True:
        if atual == "/" or os.path.ismount(atual):
            return atual
        pai = str(PurePosixPath(atual).parent)
        if pai == atual:  # chega na raiz sem ismount (caso Windows)
            return atual
        atual = pai


def intencao(caminho: Path | str) -> str:
    """Ponto de montagem que o caminho PRETENDIA usar.

    Sem isto o erro original passaria despercebido: com ``/mnt/ssd``
    desmontado, ``/mnt/ssd/pregacoes`` continua existindo (na raiz do SD) e
    ``monta_raiz`` responderia ``/`` - ou seja, "esta tudo certo", justamente
    quando nao esta. As convencoes ``/mnt/<disco>`` e ``/media/<disco>``
    dizem onde o disco deveria estar; devolve vazio quando nao ha essa
    intencao (ex.: a propria pasta padrao no cartao SD).
    """
    partes = PurePosixPath(_posix(str(caminho))).parts
    if len(partes) < 3 or partes[1] not in ("mnt", "media"):
        return ""
    if partes[1] == "media" and len(partes) >= 4:
        # /media/<usuario>/<disco>/<pasta>: o disco e o terceiro segmento
        return f"/media/{partes[2]}/{partes[3]}"
    return f"/{partes[1]}/{partes[2]}"


def _espaco(raiz: Path) -> Dict[str, Any]:
    try:
        uso = shutil.disk_usage(str(raiz))
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "total_gb": round(uso.total / (1024 ** 3), 1),
        "livre_gb": round(uso.free / (1024 ** 3), 1),
        "livre_mb": uso.free // (1024 * 1024),
        "usado_percent": round(100.0 * uso.used / uso.total, 1) if uso.total else 0.0,
    }


def _gravavel(alvo: Path) -> bool:
    """Consegue gravar aqui? (dir criado, se preciso)"""
    try:
        alvo.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return os.access(alvo, os.W_OK)


def destinos(configurado: Path | str, padrao_sd: Path | str) -> List[Dict[str, Any]]:
    """Candidatos a destino de gravacao, com a situacao real de cada um.

    Sempre inclui o padrao do cartao SD: ele e o colchao de seguranca quando
    o disco externo falhar.
    """
    cfg = _posix(str(configurado))
    sd = _posix(str(padrao_sd))
    itens: List[Dict[str, Any]] = []

    for m in externas():
        raiz = m["mount"]
        alvo = _junta(raiz, SUBPASTA)
        montado = os.path.ismount(raiz)
        disco = _espaco(Path(raiz) if montado else Path(alvo))
        itens.append(
            {
                "caminho": alvo,
                "raiz": raiz,
                "rotulo": m.get("label") or Path(m["device"]).name,
                "device": m["device"],
                "fs": m["fstype"],
                "montado": montado,
                "gravavel": bool(montado and _gravavel(Path(alvo))),
                "externo": True,
                "disco": disco,
            }
        )

    itens.append(
        {
            "caminho": sd,
            "raiz": monta_raiz(sd),
            "rotulo": "Cartao SD",
            "device": "",
            "fs": "",
            "montado": True,
            "gravavel": _gravavel(Path(sd)),
            "externo": False,
            "disco": _espaco(Path(sd)),
        }
    )

    # o destino escolhido precisa aparecer mesmo que nao seja candidato
    # (caminho digitado a mao ou disco que sumiu): sem isso o usuario nao
    # conseguiria trocar para algo que exista.
    if cfg not in {i["caminho"] for i in itens}:
        raiz = intencao(cfg) or monta_raiz(cfg)
        montado = os.path.ismount(raiz)
        itens.append(
            {
                "caminho": cfg,
                "raiz": raiz,
                "rotulo": "Destino digitado",
                "device": "",
                "fs": "",
                "montado": montado,
                "gravavel": bool(montado and _gravavel(Path(cfg))),
                "externo": bool(intencao(cfg)),
                "disco": _espaco(Path(cfg)),
            }
        )

    for item in itens:
        item["atual"] = item["caminho"] == cfg
    itens.sort(key=lambda i: (not i["atual"], not i["montado"], not i["externo"]))
    return itens


def atual(configurado: Path | str, padrao_sd: Path | str) -> Dict[str, Any]:
    """Situacao do destino escolhido: onde de verdade esta gravando.

    Calculado direto (sem listar todos os destinos): esta rota e chamada no
    fluxo de status, que roda a cada segundo via SSE.
    """
    cfg = _posix(str(configurado))
    esperada = intencao(cfg)
    raiz_real = monta_raiz(cfg)
    externos = {m["mount"]: m for m in externas()}

    if esperada:
        # ha intencao de disco externo: vale so se alguma montagem viva
        # cobre o caminho. Com o SSD desmontado ``raiz_real`` vira "/",
        # que nao casa com nenhuma - e e justamente o caso do relato.
        montado = any(
            raiz_real == raiz or raiz_real.startswith(raiz + "/")
            for raiz in externos
        )
    else:
        # sem intencao externa (pasta padrao no SD ou caminho comum): o que
        # estiver montado ja e o lugar certo.
        montado = True

    fonte = externos.get(raiz_real, {})
    return {
        "caminho": cfg,
        "raiz_esperada": esperada or raiz_real,
        "raiz_real": raiz_real,
        "montado": montado,
        "disponivel": montado,
        "externo": bool(esperada),
        "device": fonte.get("device", ""),
        "rotulo": fonte.get("label", ""),
        "no_cartao_sd": raiz_real == "/",
        "disco": _espaco(Path(cfg)),
    }


def aviso(configurado: Path | str, padrao_sd: Path | str) -> Optional[str]:
    """Mensagem curta quando o destino escolhido nao esta no lugar."""
    situacao = atual(configurado, padrao_sd)
    if situacao["disponivel"]:
        return None
    return (
        f"Destino indisponivel: {situacao['caminho']} esperava "
        f"{situacao['raiz_esperada']} montado. As gravacoes estao caindo "
        f"no cartao SD."
    )


def escolher(caminho: str, padrao_sd: Path | str) -> Tuple[bool, str]:
    """Valida um destino ANTES de grava-lo na configuracao.

    Um caminho numa pasta que existe mas que nao esta no ponto de montagem
    certo seria aceito com facilidade - e e justamente o erro que motivou
    este modulo. Por isso a recusa e explicita.
    """
    texto = str(caminho or "").strip()
    if not texto:
        return False, "destino vazio"
    alvo = Path(texto)
    if alvo.is_symlink():
        return False, "destino nao pode ser um link simbolico"

    raiz = monta_raiz(texto)
    externos = {m["mount"] for m in externas()}

    # 1) disco externo de verdade, montado agora
    if raiz in externos:
        if not _gravavel(alvo):
            return False, f"sem permissao de escrita em {texto}"
        return True, ""

    # 2) o caminho PEDIO um disco externo (/mnt/..., /media/...) e ele nao
    #    esta montado. Recusar aqui e o nucleo do modulo: aceitar levaria o
    #    usuario a achar que trocou de destino enquanto a gravacao continuava
    #    caindo no cartao SD.
    esperada = intencao(texto)
    if esperada:
        return False, f"dispositivo {esperada} nao esta montado"

    # 3) filesystem volatil (tmpfs em /tmp e /run) sumiria no reboot
    fstype = next(
        (m["fstype"] for m in montagens() if m["mount"] == raiz), ""
    )
    if fstype in PSEUDO_FS:
        return False, f"{raiz} e arquivo temporario: perde as gravacoes no reboot"

    # 4) cartao SD
    if raiz != monta_raiz(padrao_sd):
        return False, f"{texto} nao esta num dispositivo de armazenamento"
    if not _gravavel(alvo):
        return False, f"sem permissao de escrita em {texto}"
    return True, ""
