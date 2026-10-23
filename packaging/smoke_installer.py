"""Smoke Windows do instalador com fixtures sinteticas e destino temporario.

Nao usa o ZIP de producao nem inicia gravador, navegador ou integracoes. Compila
duas fixtures minimas com SmokeTestBuild, que desativa atalho e registro do
desinstalador. Mantem instalacoes, backups e logs na pasta de evidencia impressa.
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def builder_module():
    spec = importlib.util.spec_from_file_location("installer_smoke_builder", ROOT / "packaging/build_installer.py")
    require(spec is not None and spec.loader is not None, "Montador do instalador indisponivel")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(bundle: Path, revision: int) -> dict[str, bytes]:
    """Somente conteudo sintetico; o Python do payload nao e executavel."""
    files = {
        "Iniciar Pregacao.cmd": b"@echo off\r\nexit /b 0\r\n",
        "Verificar Pacote.cmd": b"@echo off\r\nexit /b 0\r\n",
        "gravador/app/launcher.py": f"# fixture sintetica {revision}\n".encode(),
        "gravador/config/default.json": json.dumps({"fixture": revision}).encode(),
        "runtime/python/python.exe": f"nao executar: fixture {revision}".encode(),
        "pipeline/pipeline.py": f"# pipeline sintetico {revision}\n".encode(),
        "pipeline/prompt.txt": f"prompt sintetico {revision}\n".encode(),
    }
    for relative, data in files.items():
        file = bundle / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
    manifest = {"name": "PregacaoRecorder", "schema_version": 1,
                "version": f"smoke-{revision}",
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    data = json.dumps(manifest, indent=2).encode()
    (bundle / "package-manifest.json").write_bytes(data)
    return dict(files, **{"package-manifest.json": data})


def compile_fixture(builder, compiler: Path, bundle: Path, work: Path, revision: int) -> Path:
    output = work / f"build-{revision}"
    script, name = builder.prepare_script(bundle, output / "script", output, smoke=True)
    require(name.endswith("-smoke"), "Somente builds de smoke podem ser instalados por este script")
    require("#define SmokeTestBuild" in script.read_text(encoding="utf-8-sig"), "Macro de isolamento ausente")
    log = output / "compiler.log"
    with log.open("w", encoding="utf-8") as stream:
        proc = subprocess.run([str(compiler), str(script)], stdout=stream, stderr=subprocess.STDOUT,
                              creationflags=FLAGS, timeout=120)
    require(proc.returncode == 0, f"Compilacao falhou; consultar {log}")
    executable = output / (name + ".exe")
    require(executable.is_file(), "Compilador nao gerou o instalador de smoke")
    return executable


def install(executable: Path, target: Path, log: Path) -> tuple[int, str]:
    require(executable.name.endswith("-smoke.exe"), "Recusado instalador sem isolamento de smoke")
    proc = subprocess.run([str(executable), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
                           f"/DIR={target}", f"/LOG={log}"], creationflags=FLAGS, timeout=90)
    text = log.read_text(encoding="utf-8-sig", errors="replace") if log.exists() else ""
    return proc.returncode, text


def uninstall(target: Path, log: Path) -> tuple[int, str]:
    executable = target / "uninstall/unins000.exe"
    require(executable.is_file(), "Desinstalador sintetico nao foi gerado")
    proc = subprocess.run([str(executable), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/LOG={log}"],
                          creationflags=FLAGS, timeout=90)
    text = log.read_text(encoding="utf-8-sig", errors="replace") if log.exists() else ""
    return proc.returncode, text


def expect_files(root: Path, expected: dict[str, bytes]) -> None:
    for relative, data in expected.items():
        file = root / relative
        require(file.is_file() and file.read_bytes() == data, "Arquivo alterado/ausente: " + relative)


def backups(target: Path) -> list[Path]:
    parent = Path(str(target) + "-dados-anteriores")
    return sorted(parent.iterdir()) if parent.exists() else []


def seed_private(target: Path) -> dict[str, bytes]:
    files = {
        "gravador/.env": b"PREGACAO_SECRET=segredo-sintetico-do-smoke\n",
        "gravador/config/config.json": b'{"audio":{"device":"fixture"}}',
        "gravador/config/google_token.json": b'{"token":"sintetico-sem-acesso"}',
        "gravador/data/notebooklm/storage_state.json": b'{"cookies":[],"origins":[]}',
        "pipeline/.env": b"FIXTURE_ONLY=1\n",
        "pipeline/config.json": b'{"fixture":"preferencias-preservadas"}',
        "pipeline/whatsapp/auth/creds.json": b'{"fixture":"perfil-sem-conta"}',
        "gravador/recordings/audio-sintetico.mp3": b"audio sintetico; nenhum microfone foi capturado",
    }
    for relative, data in files.items():
        file = target / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
    database = target / "gravador/data/smoke.sqlite"
    with closing(sqlite3.connect(database)) as connection:
        with connection:
            connection.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, estado TEXT)")
            connection.execute("INSERT INTO jobs VALUES (1, 'AGUARDANDO_INTERVENCAO')")
    files["gravador/data/smoke.sqlite"] = database.read_bytes()
    return files


@contextmanager
def launcher_lock(target: Path):
    """Mesmo contrato msvcrt do launcher, sem importar/iniciar a aplicacao."""
    import msvcrt

    path = target / "gravador/logs/inicializacao.lock"
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def synthetic_process(target: Path):
    # Este filho somente dorme; o destino no argumento permite prova WMI.
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(90)",
                              str(target / "processo-sintetico-nao-executar")],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=FLAGS)
    try:
        yield child
    finally:
        if child.poll() is None:
            child.terminate()  # Somente o filho sintetico criado acima.
        child.wait(timeout=10)


def expect_refusal(executable: Path, target: Path, log: Path, reason: str,
                   managed: dict[str, bytes], private: dict[str, bytes]) -> None:
    before = backups(target)
    code, text = install(executable, target, log)
    require(code != 0 and reason.lower() in text.lower(), "Instalador nao recusou o destino esperado; consultar " + str(log))
    expect_files(target, managed)
    expect_files(target, private)
    require(backups(target) == before, "Recusa criou backup ou substituiu dados")


def expect_uninstall_refusal(target: Path, log: Path, reason: str, managed, private) -> None:
    before = backups(target)
    code, text = uninstall(target, log)
    require(code != 0 and reason.lower() in text.lower(), "Desinstalador nao recusou destino ocupado; consultar " + str(log))
    expect_files(target, managed)
    expect_files(target, private)
    require(backups(target) == before, "Recusa de desinstalacao alterou backups")


def check_unrecognized_directory(executable: Path, work: Path) -> None:
    target = work / "pasta existente sem manifesto"
    target.mkdir()
    marker = target / "sentinela.txt"
    marker.write_bytes(b"conteudo anterior sintetico")
    code, text = install(executable, target, work / "recusa-pasta-arbitraria.log")
    require(code != 0 and "sem pacote reconhecido" in text.lower(), "Instalador aceitou pasta arbitraria existente")
    require(list(target.iterdir()) == [marker] and marker.read_bytes() == b"conteudo anterior sintetico",
            "Recusa escreveu na pasta arbitraria")
    require(not Path(str(target) + "-dados-anteriores").exists(), "Recusa criou backup de pasta arbitraria")


def check_blocked_backup(executable: Path, target: Path, work: Path, managed, private) -> None:
    blocker = Path(str(target) + "-dados-anteriores")
    require(blocker.resolve().is_relative_to(work.resolve()) and not blocker.exists(), "Destino do bloqueio sintetico invalido")
    blocker.write_bytes(b"arquivo sintetico impedindo a pasta de backup")
    try:
        code, text = install(executable, target, work / "recusa-backup-bloqueado.log")
        require(code != 0 and "arquivar" in text.lower(), "Instalador ignorou falha ao arquivar dados")
        expect_files(target, managed)
        expect_files(target, private)
        require(blocker.read_bytes() == b"arquivo sintetico impedindo a pasta de backup", "Instalador substituiu bloqueio de backup")
    finally:
        blocker.unlink()  # Apenas o arquivo sintetico criado acima.


def check_junction(executable: Path, target: Path, work: Path, managed, private) -> str:
    original = target / "runtime-original"
    link = target / "runtime"
    external = work / "fora do destino"
    # Todos os caminhos resolvidos ficam dentro do sandbox antes de qualquer move.
    require(all(path.resolve().is_relative_to(work.resolve()) for path in (original, link, external)),
            "Caminho de junction fora do sandbox")
    external.mkdir()
    (external / "sentinela.txt").write_text("nao substituir", encoding="utf-8")
    link.rename(original)
    made = False
    try:
        env = os.environ.copy()
        env.update(PREGACAO_SMOKE_LINK=str(link), PREGACAO_SMOKE_TARGET=str(external))
        # Comando do shell fixo; caminhos passam por ambiente e ficam entre
        # aspas. Evita list2cmdline inserir escapes nas aspas de cmd /c.
        shell = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
        require('"' not in shell, "COMSPEC invalido")
        command = f'"{shell}" /d /c mklink /J "%PREGACAO_SMOKE_LINK%" "%PREGACAO_SMOKE_TARGET%"'
        proc = subprocess.run(command,
                              env=env, capture_output=True, creationflags=FLAGS, timeout=10)
        if proc.returncode:
            return "SKIP: Windows recusou criar junction de teste"
        made = True
        before = backups(target)
        code, text = install(executable, target, work / "recusa-junction.log")
        require(code != 0 and "juncoes" in text.lower(), "Instalador aceitou junction no destino")
        require((external / "sentinela.txt").read_text(encoding="utf-8") == "nao substituir",
                "Instalador alterou o destino da junction")
        require(sorted(path.name for path in external.iterdir()) == ["sentinela.txt"], "Arquivo escrito atraves de junction")
        require(backups(target) == before, "Junction deveria ser recusada antes do backup")
        return "PASS"
    finally:
        if made:
            require(bool(link.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT),
                    "Recusa remover caminho que deixou de ser junction")
            os.rmdir(link)  # Remove apenas a junction sintetica; nunca sua arvore.
        original.rename(link)
        expect_files(target, managed)
        expect_files(target, private)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iscc", type=Path, help="ISCC.exe do Inno Setup 7; somente compilacao local")
    parser.add_argument("--work", type=Path, help="Nova pasta vazia para todas as evidencias; padrao .w/ no projeto")
    options = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("Este smoke executa o instalador Windows")
    cached = ROOT / ".bundle-cache/inno-7.1.0/compiler/ISCC.exe"
    compiler = (options.iscc or (cached if cached.is_file() else Path(shutil.which("ISCC.exe") or ""))).resolve()
    if not compiler.is_file():
        parser.error("Informe --iscc com um compilador Inno Setup 7")
    if options.work:
        work = options.work.resolve()
        if work.exists():
            parser.error("--work deve ser uma pasta nova, para impedir uso de dados existentes")
        work.mkdir(parents=True)
    else:
        work_root = ROOT / ".w"
        work_root.mkdir(exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="s-", dir=work_root))
    print("EVIDENCIAS:", work, flush=True)
    report = {"work": str(work), "checks": {}, "uses_real_accounts": False,
              "writes_desktop_or_registry": False}
    checks = report["checks"]
    try:
        builder = builder_module()
        bundle = work / "fixture publica"
        managed1 = fixture(bundle, 1)
        exe1 = compile_fixture(builder, compiler, bundle, work, 1)
        target = work / "Instalacao pregação com espaços & teste" / "PregacaoRecorder"
        code, _ = install(exe1, target, work / "primeira-instalacao.log")
        require(code == 0, "Primeira instalacao falhou")
        expect_files(target, managed1)
        require(not backups(target), "Instalacao nova criou backup desnecessario")
        checks["initial_install_accents_spaces_ampersand"] = "PASS"
        private = seed_private(target)
        managed2 = fixture(bundle, 2)
        exe2 = compile_fixture(builder, compiler, bundle, work, 2)
        check_unrecognized_directory(exe2, work)
        checks["refuse_existing_unrecognized_directory_without_writes"] = "PASS"

        with synthetic_process(target) as child:
            expect_refusal(exe2, target, work / "recusa-processo.log", "programa desta instalacao esta aberto", managed1, private)
            require(child.poll() is None, "Instalador encerrou o processo sintetico")
            checks["refuse_live_process_without_killing"] = "PASS"

        with launcher_lock(target):
            expect_refusal(exe2, target, work / "recusa-lock.log", "iniciador ou instalador esta em uso", managed1, private)
        checks["refuse_launcher_lock"] = "PASS"
        checks["refuse_junction"] = check_junction(exe2, target, work, managed1, private)
        check_blocked_backup(exe2, target, work, managed1, private)
        checks["refuse_backup_failure_before_replacement"] = "PASS"

        code, _ = install(exe2, target, work / "reinstalacao.log")
        require(code == 0, "Reinstalacao falhou")
        expect_files(target, managed2)
        require(all(not (target / relative).exists() for relative in private),
                "Reinstalacao deve comecar sem dados locais anteriores")
        saved = backups(target)
        require(len(saved) == 1, "Reinstalacao deveria criar exatamente um backup")
        require((saved[0] / "gravador/config/default.json").read_bytes() ==
                managed1["gravador/config/default.json"], "Config antiga nao foi arquivada")
        expect_files(saved[0], private)
        with closing(sqlite3.connect(saved[0] / "gravador/data/smoke.sqlite")) as connection:
            require(connection.execute("SELECT estado FROM jobs WHERE id=1").fetchone() == ("AGUARDANDO_INTERVENCAO",),
                    "Registro SQLite nao foi arquivado")
        checks["reinstall_starts_clean_and_archives_previous_data"] = "PASS"
        checks["previous_recordings_moved_without_copy"] = "PASS"

        with synthetic_process(target) as child:
            expect_uninstall_refusal(target, work / "recusa-desinstalacao-processo.log", "Conclua gravacoes", managed2, {})
            require(child.poll() is None, "Desinstalador encerrou processo sintetico")
        checks["refuse_uninstall_live_process_without_killing"] = "PASS"
        with launcher_lock(target):
            expect_uninstall_refusal(target, work / "recusa-desinstalacao-lock.log", "Desinstalacao cancelada", managed2, {})
        checks["refuse_uninstall_launcher_lock"] = "PASS"
        code, _ = uninstall(target, work / "desinstalacao.log")
        require(code == 0, "Desinstalacao ociosa falhou")
        require(all(not (target / relative).exists() for relative in managed2), "Desinstalacao deixou componentes gerenciados")
        require(all(not (target / relative).exists() for relative in private),
                "Desinstalacao ressuscitou dados locais arquivados")
        require(backups(target) == saved, "Desinstalacao alterou pastas de backup")
        expect_files(saved[0], private)
        checks["uninstall_removes_managed_preserves_archived_data"] = "PASS"
        code, _ = install(exe2, target, work / "instalacao-apos-desinstalar.log")
        require(code == 0, "Instalacao apos desinstalar falhou em pasta residual")
        expect_files(target, managed2)
        require(all(not (target / relative).exists() for relative in private),
                "Pasta residual trouxe dados antigos para a instalacao nova")
        checks["install_after_uninstall_with_residual_folder"] = "PASS"
        print(json.dumps(checks, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        report["error"] = str(exc)
        print("FALHA:", exc, file=sys.stderr)
        return 1
    finally:
        (work / "smoke-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
