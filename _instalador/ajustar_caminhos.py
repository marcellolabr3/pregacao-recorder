#!/usr/bin/env python
"""Auto-ajuste da instalacao portatil do PregacaoRecorder.

Rode uma vez (ou deixa os .bat rodarem antes de iniciar) quando a unidade
do SSD aparecer com outra letra que nao E:. O script:

  1. descobre a raiz real da instalacao (a pasta deste arquivo);
  2. reescreve o pyvenv.cfg dos venvs para o Python DESTE disco;
  3. reescreve o shebang embutido nos .exe das venvs;
  4. corrige os caminhos absolutos do config.json do pregacao-recorder;
  5. copia o rclone.conf para %APPDATA%\\rclone se nao existir la;
  6. copia o perfil do NotebookLM para ~\\.notebooklm se nao existir la;
  7. garante que as pastas de trabalho existem.

Nao altera segredos, nao apaga nada, nao mexe no prompt do estudo.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

# raiz = pasta que contem runtime/, pregacao-recorder/, sermon-pipeline/
RAIZ = Path(__file__).resolve().parent.parent
PREG = RAIZ / "pregacao-recorder"
SERMON = RAIZ / "sermon-pipeline"
RUNTIME = RAIZ / "runtime"

CONFIG = PREG / "config" / "config.json"


def log(msg: str) -> None:
    print(f"[ajustar] {msg}", flush=True)


def ajustar_config() -> bool:
    """Corrige os caminhos absolutos do config.json para a raiz atual."""
    if not CONFIG.exists():
        log(f"config.json nao encontrado em {CONFIG}")
        return False

    antes = CONFIG.read_text(encoding="utf-8")
    cfg = json.loads(antes)

    desejado = {
        "storage.recordings_dir": str(PREG / "recordings"),
        "estudos.python": str(SERMON / ".venv" / "Scripts" / "python.exe"),
        "estudos.pasta": str(SERMON),
    }

    mudou = False
    for chave, valor in desejado.items():
        secoes, ultimo = chave.rsplit(".", 1)
        no = cfg
        for secao in secoes.split("."):
            no = no.setdefault(secao, {})
        if no.get(ultimo) != valor:
            log(f"{chave}: {no.get(ultimo)!r} -> {valor!r}")
            no[ultimo] = valor
            mudou = True

    if mudou:
        CONFIG.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        log("config.json atualizado")
    else:
        log("config.json ja esta correto")
    return mudou


def ajustar_pyvenv() -> None:
    """Reescreve o pyvenv.cfg dos venvs para apontar ao runtime DESTE disco.

    Motivo: o pyvenv.cfg guarda o caminho absoluto do Python base. Se o SSD
    aparecer com outra letra (E: -> D:), esse caminho deixa de existir e o
    ``.venv\\Scripts\\python.exe`` nao sobe - o ``python`` cai no runtime base,
    que nao tem os pacotes, e o app reclama "paho-mqtt nao instalado".
    """
    runtime_python = RUNTIME / "python311"
    if not runtime_python.exists():
        log(f"runtime\\python311 nao encontrado em {runtime_python}")
        return

    for venv in (PREG / ".venv", SERMON / ".venv"):
        cfg = venv / "pyvenv.cfg"
        if not cfg.exists():
            log(f"pyvenv.cfg ausente em {venv} (venv nao criado ainda)")
            continue

        desejado = {
            "home": str(runtime_python),
            "executable": str(runtime_python / "python.exe"),
            "command": f"{runtime_python / 'python.exe'} -m venv {venv}",
        }

        linhas = cfg.read_text(encoding="utf-8").splitlines()
        novas: list[str] = []
        mudou = False
        vistos: set[str] = set()
        for linha in linhas:
            chave, _, valor = linha.partition(" = ")
            if chave in desejado:
                vistos.add(chave)
                if valor != desejado[chave]:
                    log(f"{venv.name} {chave}: {valor!r} -> {desejado[chave]!r}")
                    mudou = True
                novas.append(f"{chave} = {desejado[chave]}")
            else:
                novas.append(linha)

        # chaves que nao existiam no arquivo antigo
        for chave, valor in desejado.items():
            if chave not in vistos:
                novas.append(f"{chave} = {valor}")
                mudou = True

        if mudou:
            cfg.write_text("\n".join(novas) + "\n", encoding="utf-8")
            log(f"pyvenv.cfg de {venv.name} corrigido")
        else:
            log(f"pyvenv.cfg de {venv.name} ja esta correto")


# launcher do pip: '#!<caminho absoluto do python.exe da venv>' + '\n' + zip
# (o '#! PATHTEXT' interno do proprio launcher nao casa: nao tem letra de
# unidade nem termina em python.exe)
_SHEBANG = re.compile(rb"#![A-Za-z]:\\[^\x00-\x1f\r\n]*python\.exe\r?\n")


def ajustar_launchers() -> None:
    """Reescreve o shebang embutido nos .exe gerados dentro das venvs.

    Esses .exe (notebooklm.exe, flask.exe, ...) guardam o caminho ABSOLUTO do
    ``python.exe`` da propria venv. Muda a letra da unidade e o caminho some:
    o .exe falha em silencio e o pipeline nao consegue chamar o NotebookLM.

    Prova de que reescrever com tamanho diferente e seguro: um launcher
    apontado para outro python resolve o processo normalmente - so falha no
    import, que e efeito esperado de apontar para um python sem os pacotes.
    """
    total = corrigidos = 0
    for venv in (PREG / ".venv", SERMON / ".venv"):
        scripts = venv / "Scripts"
        if not scripts.is_dir():
            log(f"{venv.name}: Scripts ausente (venv nao criado ainda)")
            continue

        alvo = str(scripts / "python.exe").encode("ascii", "replace")
        if alvo.endswith(b"?"):
            log(f"{venv.name}: caminho da venv nao e ASCII, shebang nao ajustado")
            continue
        desejado = b"#!" + alvo + b"\n"

        for exe in sorted(scripts.glob("*.exe")):
            total += 1
            try:
                dados = exe.read_bytes()
            except OSError as exc:
                log(f"{exe.name}: nao deu para ler ({exc})")
                continue
            m = _SHEBANG.search(dados)
            if not m:
                continue
            if m.group(0) == desejado:
                continue
            try:
                exe.write_bytes(dados[: m.start()] + desejado + dados[m.end() :])
            except OSError as exc:
                log(f"{exe.name}: nao deu para gravar ({exc})")
                continue
            log(f"{exe.name}: shebang -> {alvo.decode('ascii')}")
            corrigidos += 1

    log(f"launchers .exe verificados: {total}, corrigidos: {corrigidos}")


def garantir_pastas() -> None:
    """Cria as pastas que o app espera encontrar."""
    for pasta in (
        PREG / "recordings",
        PREG / "logs",
        PREG / "data",
        PREG / "recovery",
        SERMON / "output",
        SERMON / "logs",
    ):
        pasta.mkdir(parents=True, exist_ok=True)
    log("pastas de trabalho verificadas")


def copiar_rclone_conf() -> None:
    """O rclone procura o conf em %APPDATA%\\rclone; la nao tem no PC novo."""
    origem = RUNTIME / "rclone" / "rclone.conf"
    if not origem.exists():
        log("rclone.conf de origem nao encontrado (ok se usar RCLONE_CONFIG)")
        return
    destino_dir = Path(os.environ.get("APPDATA", "")) / "rclone"
    destino = destino_dir / "rclone.conf"
    if destino.exists():
        log(f"rclone.conf ja existe em {destino} (mantido)")
        return
    try:
        destino_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, destino)
        log(f"rclone.conf copiado para {destino}")
    except OSError as exc:
        log(f"nao deu para copiar rclone.conf: {exc}")


def copiar_perfil_notebooklm() -> None:
    """O perfil do NotebookLM (cookies do Google) fica em ~\\.notebooklm."""
    origem = RAIZ / "perfil-notebooklm"
    destino = Path.home() / ".notebooklm"
    if not origem.exists():
        log("perfil-notebooklm de origem nao encontrado")
        return
    if destino.exists() and any(destino.iterdir()):
        log(f"perfil do NotebookLM ja existe em {destino} (mantido)")
        return
    try:
        shutil.copytree(origem, destino, dirs_exist_ok=True)
        log(f"perfil do NotebookLM copiado para {destino}")
    except OSError as exc:
        log(f"nao deu para copiar o perfil: {exc}")


def main() -> int:
    log(f"raiz detectada: {RAIZ}")
    if not (PREG.exists() and SERMON.exists()):
        log("ERRO: pregacao-recorder/ ou sermon-pipeline/ nao encontrados na raiz")
        return 1
    garantir_pastas()
    ajustar_pyvenv()
    ajustar_launchers()
    ajustar_config()
    copiar_rclone_conf()
    copiar_perfil_notebooklm()
    log("auto-ajuste concluido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
