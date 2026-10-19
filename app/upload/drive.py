"""Integracao com Google Drive (OAuth 2.0, sem senha armazenada).

Fluxo de conexao:
  1. administrador coloca o JSON de credenciais OAuth do Google Console em
     ``config/google_credentials.json`` (nao entra no Git);
  2. na interface web: Configuracoes -> Google Drive -> Conectar conta;
  3. o PC abre um endpoint local ``/oauth`` - o usuario acessa pelo
     navegador do celular/PC na rede da igreja e autoriza a conta;
  4. o token e salvo em ``config/google_token.json`` (arquivo local ignorado pelo Git).

Envio:
  * upload resumivel com barra de progresso;
  * apos o envio, o ``id`` retornado e consultado de novo e o ``size``/``md5Checksum``
    e comparado com o arquivo local - so entao o upload e considerado concluido.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..config import config as app_config
from ..logging_setup import get

log = get("drive")

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

_state_lock = threading.Lock()
_service = None
_authorize_url: Optional[str] = None
_flow = None
# state devolvido pelo Google: valida que o codigo veio mesmo do nosso
# pedido (protege contra codigo injetado por terceiros no callback).
_pending_state: Optional[str] = None


class DriveError(RuntimeError):
    pass


GOOGLE_MODULES = (
    "google.auth.transport.requests",
    "google.oauth2.credentials",
    "google_auth_oauthlib.flow",
    "googleapiclient.discovery",
    "googleapiclient.errors",
)


def _import_google() -> bool:
    """Garante que as bibliotecas do Drive estao instaladas."""
    for name in GOOGLE_MODULES:
        try:
            __import__(name)
        except ImportError as exc:
            raise DriveError(
                "bibliotecas do Google nao instaladas "
                "(pip install google-api-python-client google-auth-oauthlib)"
            ) from exc
    return True


def libraries_available() -> bool:
    try:
        _import_google()
        return True
    except DriveError:
        return False


def manual_credentials() -> Dict[str, str]:
    """Credenciais cadastradas MANUALMENTE pela interface.

    E a fonte preferida: o usuario digita Client ID/Secret em
    CONFIG -> GOOGLE DRIVE (nao precisa editar arquivo no equipamento).
    """
    client_id = str(app_config.get("drive.client_id", "") or "").strip()
    client_secret = str(app_config.get("drive.client_secret", "") or "").strip()
    return {"client_id": client_id, "client_secret": client_secret}


def credentials_source() -> str:
    """De onde vem a credencial: interface, arquivo ou .env ('' = nenhuma)."""
    manual = manual_credentials()
    if manual["client_id"] and manual["client_secret"]:
        return "manual"
    if app_config.google_credentials_file.exists():
        return "arquivo"
    if os.environ.get("GOOGLE_CLIENT_ID", "").strip() and os.environ.get(
        "GOOGLE_CLIENT_SECRET", ""
    ).strip():
        return "env"
    return ""


def credentials_present() -> bool:
    return bool(credentials_source())


def token_present() -> bool:
    return app_config.google_token_file.exists()


def account_email() -> str:
    """E-mail da conta conectada (lido do token, sem chamada de rede)."""
    token_file = app_config.google_token_file
    if not token_file.exists():
        return ""
    try:
        data = json.loads(token_file.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return ""
    id_token = data.get("id_token")
    if not id_token:
        return ""
    try:
        import base64

        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        return str(claims.get("email") or "")
    except Exception:  # noqa: BLE001 - token malformado nao derruba a interface
        return ""


def status() -> Dict[str, Any]:
    manual = manual_credentials()
    return {
        "libraries": libraries_available(),
        "credentials": credentials_present(),
        "source": credentials_source(),
        "client_id": manual["client_id"],
        "connected": is_connected(),
        "account": account_email(),
        "folder": str(app_config.get("drive.folder_name", "Pregacoes") or "Pregacoes"),
        "credentials_file": str(app_config.google_credentials_file),
    }


def _load_creds():
    token_file = app_config.google_token_file
    if not token_file.exists():
        return None
    if not libraries_available():
        # bibliotecas ausentes nao pode derrubar a interface web
        return None

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None
    try:
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    except (ValueError, OSError) as exc:
        log.warning("token do Drive invalido: %s", exc)
        return None
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except Exception as exc:  # noqa: BLE001
            log.warning("falha ao renovar token do Drive: %s", exc)
            return None
    return None


def _save_token(creds) -> None:
    token_file = app_config.google_token_file
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    try:
        os.chmod(token_file, 0o600)
    except OSError:
        pass


def is_connected() -> bool:
    return _load_creds() is not None


def _client_config(client_id: str, client_secret: str, redirect_uri: str) -> Dict[str, Any]:
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }


def _build_flow(redirect_uri: str):
    """Monta o fluxo OAuth. Ordem de preferencia das credenciais:
    INTERFACE (manual) > google_credentials.json > variaveis .env."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    manual = manual_credentials()
    if manual["client_id"] and manual["client_secret"]:
        log.info("usando credenciais cadastradas na interface")
        return InstalledAppFlow.from_client_config(
            _client_config(manual["client_id"], manual["client_secret"], redirect_uri),
            SCOPES,
        )
    if app_config.google_credentials_file.exists():
        log.info("usando credenciais de %s", app_config.google_credentials_file)
        return InstalledAppFlow.from_client_secrets_file(
            str(app_config.google_credentials_file), SCOPES
        )
    env_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    env_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if env_id and env_secret:
        log.info("usando credenciais do ambiente (.env)")
        return InstalledAppFlow.from_client_config(
            _client_config(env_id, env_secret, redirect_uri), SCOPES
        )
    raise DriveError(
        "credenciais OAuth ausentes: cadastre o Client ID e o Client Secret na "
        "interface (CONFIG -> GOOGLE DRIVE) ou envie config/google_credentials.json "
        "(veja docs/GOOGLE_DRIVE.md)"
    )


def start_authorization(redirect_uri: str) -> str:
    """Inicia o fluxo OAuth e devolve a URL que o usuario deve abrir."""
    global _flow, _authorize_url, _pending_state
    _import_google()
    _flow = _build_flow(redirect_uri)
    _flow.redirect_uri = redirect_uri
    # select_account => o Google mostra o seletor de contas, permitindo
    # TROCAR de conta mesmo ja havendo uma conectada.
    url, _state = _flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent select_account",
    )
    _authorize_url = url
    _pending_state = _state
    log.info("fluxo OAuth iniciado (origem das credenciais: %s)", credentials_source())
    return url


def finish_authorization(code: str, state: Optional[str] = None) -> Dict[str, Any]:
    """Troca o codigo pela credencial e grava o token.

    ``state`` vem junto no retorno do Google. Ele e opcional por causa do
    fluxo antigo da interface web, mas quando vem e conferido: um codigo
    valido de OUTRO pedido nao pode ser aceito aqui. O APK do controlador
    remoto sempre envia - ele captura o retorno do navegador em localhost.
    """
    global _service
    _import_google()
    if _flow is None:
        raise DriveError("fluxo OAuth nao iniciado")
    if state:
        if not _pending_state:
            raise DriveError("fluxo OAuth expirado: inicie a conexao de novo")
        if state != _pending_state:
            raise DriveError("state do Google nao confere com o fluxo aberto")
    _flow.fetch_token(code=code)
    creds = _flow.credentials
    _save_token(creds)
    _service = None
    log.info("conta Google conectada com sucesso")
    return {"connected": True, "account": account_email()}


def disconnect() -> None:
    global _service
    token_file = app_config.google_token_file
    if token_file.exists():
        token_file.unlink()
    _service = None
    log.info("conta Google desconectada")


def _service_obj():
    global _service
    creds = _load_creds()
    if creds is None:
        raise DriveError("Google Drive nao conectado")
    if _service is None:
        from googleapiclient.discovery import build

        _service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return _service


def ensure_folder(folder_name: str, folder_id: str = "") -> str:
    """Retorna o id da pasta de destino, criando-a se necessario."""
    service = _service_obj()
    if folder_id:
        return folder_id
    name = folder_name or "Pregacoes"
    query = (
        "mimeType='application/vnd.google-apps.folder' and trashed=false "
        f"and name='{name}'"
    )
    result = service.files().list(q=query, spaces="drive", fields="files(id,name)").execute()
    files = result.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    created = service.files().create(body=meta, fields="id").execute()
    log.info("pasta '%s' criada no Drive (id=%s)", name, created.get("id"))
    return created["id"]


def md5_of(path: Path) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload_file(
    path: Path,
    folder_id: str = "",
    folder_name: str = "Pregacoes",
    progress: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """Envia um arquivo e CONFIRMA o resultado consultando o Drive."""
    from googleapiclient.http import MediaFileUpload

    path = Path(path)
    if not path.exists():
        raise DriveError(f"arquivo nao encontrado: {path}")

    service = _service_obj()
    target_folder = ensure_folder(folder_name, folder_id)
    size = path.stat().st_size
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    local_md5 = md5_of(path)

    body = {
        "name": path.name,
        "parents": [target_folder],
        "description": f"pregacao-recorder | {path.name}",
    }
    media = MediaFileUpload(str(path), mimetype=mime, chunksize=8 * 1024 * 1024, resumable=True)

    request = service.files().create(body=body, media_body=media, fields="id,name,size,md5Checksum")
    response = None
    while response is None:
        status_chunk, response = request.next_chunk()
        if status_chunk and progress:
            try:
                progress(int(status_chunk.progress() * 100), size)
            except Exception:  # pragma: no cover
                pass
    file_id = response.get("id")
    if not file_id:
        raise DriveError("Drive nao retornou id do arquivo")

    # --- confirmacao efetiva -------------------------------------------
    confirm = service.files().get(fileId=file_id, fields="id,name,size,md5Checksum").execute()
    remote_size = int(confirm.get("size") or 0)
    if remote_size != size:
        raise DriveError(
            f"verificacao de integridade falhou: local={size} bytes, drive={remote_size} bytes"
        )
    remote_md5 = confirm.get("md5Checksum")
    if remote_md5 and remote_md5 != local_md5:
        raise DriveError(
            f"verificacao de integridade falhou: md5 local={local_md5} drive={remote_md5}"
        )

    parent = confirm.get("parents") or [target_folder]
    drive_path = f"{folder_name or 'Pregacoes'}/{confirm.get('name')}"
    log.info("upload confirmado: %s (%d bytes) -> %s", file_id, remote_size, drive_path)
    return {
        "file_id": file_id,
        "name": confirm.get("name"),
        "bytes": remote_size,
        "md5": remote_md5,
        "drive_path": drive_path,
        "parent": parent[0],
    }


def describe() -> Dict[str, Any]:
    """Metadados para o registro pos-upload (uso futuro do NotebookLM)."""
    return {
        "provider": "google_drive",
        "oauth": "2.0",
        "scopes": SCOPES,
        "status": status(),
    }


def debug_state() -> Dict[str, Any]:  # pragma: no cover - utilitario
    return json.dumps(
        {"flow": _flow is not None, "service": _service is not None}, default=str
    )
