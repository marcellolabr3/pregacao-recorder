"""Destinos de gravacao no Windows, sem fallback para outro disco.

Listar e consultar status nao cria pastas. Somente escolher um destino e
iniciar uma gravacao podem criar a pasta no volume explicitamente escolhido.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SUBPASTA = "pregacoes"


def unidades() -> List[Dict[str, str]]:
    """Discos locais fixos/removiveis usando a API do Windows, sem shell."""
    if os.name != "nt":
        return []  # permite testes isolados sem depender do SO hospedeiro
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetLogicalDrives.restype = wintypes.DWORD
    kernel.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    kernel.GetDriveTypeW.restype = wintypes.UINT
    mask = kernel.GetLogicalDrives()
    result = []
    for indice in range(26):
        if not mask & (1 << indice):
            continue
        raiz = chr(65 + indice) + ":" + chr(92)
        tipo = kernel.GetDriveTypeW(raiz)
        if tipo in (2, 3):  # removivel, fixo; nao listar CD nem rede desconectada
            result.append({"raiz": raiz, "rotulo": "Disco " + raiz[:2],
                           "tipo": "removivel" if tipo == 2 else "fixo"})
    return result


def _pasta_existente(alvo: Path) -> Path:
    while not alvo.exists() and alvo != alvo.parent:
        alvo = alvo.parent
    return alvo


def _raiz(alvo: Path) -> Path:
    return Path(alvo.anchor) if alvo.anchor else alvo


def _espaco(alvo: Path) -> Dict[str, Any]:
    try:
        uso = shutil.disk_usage(str(_pasta_existente(alvo)))
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "total_gb": round(uso.total / 1024 ** 3, 1),
            "livre_gb": round(uso.free / 1024 ** 3, 1),
            "livre_mb": uso.free // (1024 * 1024),
            "usado_percent": round(100 * uso.used / uso.total, 1) if uso.total else 0.0}


def _situacao(caminho: Path | str) -> Dict[str, Any]:
    alvo = Path(caminho).expanduser()
    raiz = _raiz(alvo)
    absoluto = alvo.is_absolute()
    montado = absoluto and raiz.is_dir()
    pasta = _pasta_existente(alvo) if montado else raiz
    gravavel = bool(montado and pasta.is_dir() and os.access(pasta, os.W_OK)
                    and (not alvo.exists() or alvo.is_dir()) and not alvo.is_symlink())
    return {"caminho": str(alvo), "raiz": str(raiz), "device": str(raiz),
            "montado": montado, "gravavel": gravavel,
            "disponivel": gravavel,
            "disco": _espaco(alvo) if montado else {"ok": False}}


def destinos(configurado: Path | str, padrao: Path | str) -> List[Dict[str, Any]]:
    """Mantem o destino configurado visivel mesmo quando o disco sumiu."""
    cfg, default = str(Path(configurado)), str(Path(padrao))
    candidatos = [(cfg, "Destino configurado"), (default, "Pasta padrao do PC")]
    candidatos += [(str(Path(d["raiz"]) / SUBPASTA), d["rotulo"]) for d in unidades()]
    itens, vistos = [], set()
    for caminho, rotulo in candidatos:
        chave = os.path.normcase(os.path.normpath(caminho))
        if chave in vistos:
            continue
        vistos.add(chave)
        situacao = _situacao(caminho)
        itens.append({**situacao, "rotulo": rotulo,
                      "atual": chave == os.path.normcase(os.path.normpath(cfg)),
                      "externo": Path(caminho).anchor != Path(default).anchor})
    return itens


def atual(configurado: Path | str, padrao: Path | str) -> Dict[str, Any]:
    situacao = _situacao(configurado)
    return {**situacao, "raiz_esperada": situacao["raiz"],
            "raiz_real": situacao["raiz"],
            "externo": Path(configurado).anchor != Path(padrao).anchor,
            "rotulo": "Destino configurado"}


def aviso(configurado: Path | str, padrao: Path | str) -> Optional[str]:
    situacao = atual(configurado, padrao)
    if situacao["disponivel"]:
        return None
    return (f"Destino indisponivel: {configurado}. Reconecte o disco ou escolha "
            "uma pasta com permissao de escrita. A gravacao nao sera desviada para outro destino.")


def escolher(caminho: str, padrao: Path | str) -> Tuple[bool, str]:
    texto = str(caminho or "").strip()
    if not texto:
        return False, "destino vazio"
    alvo = Path(texto).expanduser()
    if not alvo.is_absolute():
        return False, "informe um caminho absoluto do Windows (ex.: D:/Pregacoes)"
    if alvo.is_symlink():
        return False, "destino nao pode ser um link simbolico"
    if not _situacao(alvo)["disponivel"]:
        return False, "disco indisponivel ou pasta sem permissao de escrita"
    try:
        alvo.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"nao foi possivel preparar o destino: {exc}"
    return True, ""
