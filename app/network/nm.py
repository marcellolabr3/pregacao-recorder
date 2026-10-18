"""Camada de gerenciamento de rede (NetworkManager) do pregacao-recorder.

Responsabilidades (separacao pedida na arquitetura do projeto):

    network-manager   -> este modulo (nmcli, interfaces, Access Point)
    network-config    -> app/network/status.py + chaves "network.*" do config
    remote-access     -> app/network/tailscale.py
    watchdog          -> app/network/watchdog.py (servico systemd)

Regras:

* nenhum comando passa por shell (subprocess com lista de argumentos);
* nenhuma senha e logada ou devolvida pela API;
* nao ha dependencia de monitor/teclado: tudo e chamado pela interface web.

A autorizacao para operar o NetworkManager vem da regra polkit
``/etc/polkit-1/rules.d/50-pregacao-network.rules`` instalada pelo install.sh.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from ..logging_setup import get

log = get("network")

# --- constantes -------------------------------------------------------------
AP_PROFILE = "pregacao-ap"  # nome da conexao NM do Access Point de configuracao
AP_ADDRESS = "192.168.50.1/24"
AP_GATEWAY = "192.168.50.1"
DEFAULT_AP_PASSPHRASE = "pregacao12345"
NM_TIMEOUT = 45  # segundos; conectar em Wi-Fi pode demorar
SSID_RE = re.compile(r"^[\x20-\x7e]{1,32}$")  # SSID ASCII imprimivel (1..32)

# mensagens de log no formato pedido na arquitetura do projeto (item 19)
MSG_AP_STARTING = "[NETWORK] Starting configuration AP"
MSG_AP_ACTIVE = "[NETWORK] Configuration AP active"
MSG_AP_STOPPING = "[NETWORK] Stopping configuration AP"
MSG_WIFI_FAILED = "[NETWORK] Wi-Fi connection failed"


class NetworkError(RuntimeError):
    """Falha de operacao de rede com mensagem pronta para a interface."""


# --- execucao basica --------------------------------------------------------
def nmcli_available() -> bool:
    return shutil.which("nmcli") is not None


def run(args: List[str], timeout: int = NM_TIMEOUT,
        stdin: Optional[str] = None) -> Tuple[int, str, str]:
    """Executa ``nmcli <args>`` sem shell. Devolve (codigo, stdout, stderr)."""
    cmd = ["nmcli", *[str(a) for a in args]]
    try:
        proc = subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        return 127, "", "nmcli nao encontrado"
    except subprocess.TimeoutExpired:
        return 124, "", f"tempo esgotado apos {timeout}s"
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _must(args: List[str], timeout: int = NM_TIMEOUT,
          stdin: Optional[str] = None) -> str:
    """Roda nmcli e levanta NetworkError se falhar (mensagem amigavel)."""
    code, out, err = run(args, timeout=timeout, stdin=stdin)
    if code != 0:
        raise NetworkError(_friendly(err or out or f"nmcli retornou {code}"))
    return out


def _friendly(raw: str) -> str:
    """Converte a saida do nmcli em mensagem compreensivel (sem acentos)."""
    text = " ".join(raw.split())
    lowered = text.lower()
    if "not authorized" in lowered or "not permitted" in lowered:
        return "sem permissao para alterar a rede (regra polkit ausente)"
    if "no network with ssid" in lowered or "not found" in lowered:
        return "rede Wi-Fi nao encontrada; verifique o nome e tente de novo"
    if "secrets were required" in lowered or "password" in lowered and "wrong" in lowered:
        return "senha incorreta para essa rede Wi-Fi"
    if "already active" in lowered:
        return "conectado a essa rede"
    if "device or resource busy" in lowered:
        return "interface ocupada; aguarde alguns segundos e tente de novo"
    if "timeout" in lowered or "tempo esgotado" in lowered:
        return "tempo esgotado aguardando a conexao"
    return text[:300]


# --- utilitarios ------------------------------------------------------------
def _rows(text: str) -> List[List[str]]:
    """Converte saida ``-t`` do nmcli em linhas de campos.

    O nmcli escapapa dois-pontos dentro de valores como ``\\:``, entao a
    quebra precisa respeitar a barra invertida.
    """
    rows: List[List[str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields: List[str] = []
        current = ""
        escaped = False
        for ch in line:
            if escaped:
                current += ch
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == ":":
                fields.append(current)
                current = ""
            else:
                current += ch
        fields.append(current)
        rows.append(fields)
    return rows


def devices() -> List[Dict[str, str]]:
    """Lista interfaces geridas pelo NetworkManager."""
    code, out, err = run(["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION",
                          "dev", "status"])
    if code != 0:
        log.warning("[NETWORK] falha ao listar interfaces: %s", err.strip())
        return []
    result = []
    for row in _rows(out):
        if len(row) < 4:
            continue
        device, kind, state, connection = row[0], row[1], row[2], row[3]
        if kind == "loopback":
            continue
        result.append({
            "device": device,
            "type": kind,
            "state": state,
            "connection": connection,
            "connected": state.startswith("connected"),
        })
    return result


def _first(kind: str) -> Optional[Dict[str, str]]:
    for dev in devices():
        if dev["type"] == kind:
            return dev
    return None


def _dev_field(device: str, field: str) -> str:
    code, out, _ = run(["-g", field, "dev", "show", device])
    if code != 0:
        return ""
    return out.strip().splitlines()[0].strip() if out.strip() else ""


def _ip_of(device: str) -> str:
    value = _dev_field(device, "IP4.ADDRESS")
    return value.split("/")[0] if value else ""


def default_gateway(device: str) -> str:
    return _dev_field(device, "IP4.GATEWAY")


def has_default_route() -> bool:
    """Existe rota padrao? (ou seja, caminho de saida pela interface)."""
    try:
        proc = subprocess.run(["ip", "-4", "route", "show", "default"],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return bool(proc.stdout.strip())


# --- ethernet ---------------------------------------------------------------
def ethernet_status() -> Dict[str, Any]:
    dev = _first("ethernet")
    if not dev:
        return {"available": False, "connected": False, "device": "",
                "ip": "", "gateway": "", "state": "nao detectado"}
    connected = dev["connected"]
    return {
        "available": True,
        "connected": connected,
        "device": dev["device"],
        "state": "conectado" if connected else "desconectado",
        "ip": _ip_of(dev["device"]) if connected else "",
        "gateway": default_gateway(dev["device"]) if connected else "",
        "connection": dev["connection"],
    }


# --- Wi-Fi ------------------------------------------------------------------
def wifi_device() -> str:
    dev = _first("wifi")
    return dev["device"] if dev else "wlan0"


def wifi_enabled() -> bool:
    code, out, _ = run(["radio", "wifi"])
    return code == 0 and "enabled" in out


def wifi_status() -> Dict[str, Any]:
    dev = _first("wifi")
    if not dev:
        return {"available": False, "connected": False, "device": "",
                "ssid": "", "ip": "", "gateway": "", "signal": 0,
                "state": "nao detectado"}
    # O proprio Access Point aparece como "conectado" no NetworkManager.
    # Para o painel e para o watchdog isso NAO e conexao Wi-Fi de cliente:
    # sem esse cuidado o watchdog desligaria o AP de recuperacao achando que
    # ha rede boa, e o status mostraria "Wi-Fi em pregacao-ap".
    eh_nosso_ap = dev["connection"] == AP_PROFILE
    connected = dev["connected"] and not eh_nosso_ap
    status: Dict[str, Any] = {
        "available": True,
        "connected": connected,
        "device": dev["device"],
        "state": "conectado" if connected else
                 ("desativado" if not wifi_enabled() else
                  ("emitindo AP" if eh_nosso_ap else "desconectado")),
        "ssid": dev["connection"] if connected else "",
        "ip": _ip_of(dev["device"]) if connected else "",
        "gateway": default_gateway(dev["device"]) if connected else "",
        "signal": 0,
        "security": "",
    }
    if connected and dev["connection"]:
        # sinal/seguranca da rede atual (cache local, sem novo scan)
        for net in scan(rescan=False):
            if net["ssid"] == dev["connection"]:
                status["signal"] = net["signal"]
                status["security"] = net["security"]
                break
    return status


def signal_label(signal: int) -> str:
    if signal >= 70:
        return "Forte"
    if signal >= 45:
        return "Medio"
    if signal > 0:
        return "Fraco"
    return "desconhecido"


def scan(rescan: bool = True) -> List[Dict[str, Any]]:
    """Redes Wi-Fi visiveis, ordenadas por sinal (mais forte primeiro)."""
    if not nmcli_available():
        return []
    args = ["-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE,MODE", "dev", "wifi",
            "list", "--rescan", "yes" if rescan else "no"]
    code, out, err = run(args, timeout=25)
    if code != 0:
        # sem autorizacao ou radio desligado: devolve o cache sem quebrar a tela
        log.warning("[NETWORK] scan de Wi-Fi falhou: %s", err.strip()[:120])
        return []
    seen: Dict[str, Dict[str, Any]] = {}
    for row in _rows(out):
        if len(row) < 4:
            continue
        ssid, signal, security, in_use = row[0], row[1], row[2], row[3]
        mode = row[4] if len(row) > 4 else ""
        if not ssid.strip():
            continue  # rede oculta
        if mode and mode not in ("Infra", "AP"):
            continue
        try:
            value = int(signal or 0)
        except ValueError:
            value = 0
        entry = {
            "ssid": ssid,
            "signal": value,
            "strength": signal_label(value),
            "security": (security or "").strip(),
            "secure": bool((security or "").strip()
                           and security.strip() not in ("--",)),
            "in_use": in_use.strip() == "*",
        }
        current = seen.get(ssid)
        if current is None or entry["signal"] > current["signal"]:
            seen[ssid] = entry
    return sorted(seen.values(), key=lambda item: (-item["signal"], item["ssid"]))


def validate_ssid(ssid: str) -> str:
    ssid = (ssid or "").strip()
    if not SSID_RE.match(ssid):
        raise NetworkError("nome da rede invalido (1 a 32 caracteres)")
    if ssid.startswith("-"):
        raise NetworkError("nome da rede nao pode comecar com hifen")
    return ssid


def validate_passphrase(password: str) -> str:
    password = password or ""
    if len(password) < 8 or len(password) > 63:
        raise NetworkError("a senha do Wi-Fi deve ter de 8 a 63 caracteres")
    return password


def connect(ssid: str, password: Optional[str] = None,
            timeout: int = NM_TIMEOUT) -> None:
    """Conecta o Wi-Fi a uma rede. A senha vai por STDIN (nao aparece em ps).

    O log de sucesso e feito pelo watchdog (transicao); aqui ficam as falhas,
    que o watchdog nao enxerga.
    """
    ssid = validate_ssid(ssid)
    args = ["dev", "wifi", "connect", ssid]
    stdin = None
    if password:
        validate_passphrase(password)
        args.insert(0, "--ask")
        stdin = f"{password}\n"
    try:
        _must(args, timeout=timeout, stdin=stdin)
    except NetworkError:
        log.warning("[NETWORK] Wi-Fi connection failed: %s", ssid)
        raise


def disconnect() -> None:
    """Desconecta o Wi-Fi mantendo a rede salva (para reconectar depois)."""
    dev = wifi_device()
    _must(["dev", "disconnect", dev])


def _profile_type(name: str) -> str:
    code, out, _ = run(["-t", "-f", "NAME,TYPE", "con", "show"])
    if code != 0:
        return ""
    for row in _rows(out):
        if len(row) >= 2 and row[0] == name:
            return row[1]
    return ""


def forget(ssid: str) -> None:
    """Esquece uma rede Wi-Fi. Nunca aceita perfis que nao sejam Wi-Fi."""
    ssid = validate_ssid(ssid)
    if ssid == AP_PROFILE:
        raise NetworkError("essa conexao nao pode ser removida")
    kind = _profile_type(ssid)
    if kind == "":
        # nada salvo: nao e erro (o usuario ja estava sem perfil)
        log.info("[NETWORK] forget ignored (no profile): %s", ssid)
        return
    if kind != "802-11-wireless":
        raise NetworkError("essa conexao nao e uma rede Wi-Fi")
    _must(["con", "delete", "id", ssid])
    log.info("[NETWORK] network forgotten: %s", ssid)


def saved_wifi() -> List[str]:
    """Perfis Wi-Fi salvos (para mostrar no painel)."""
    code, out, _ = run(["-t", "-f", "NAME,TYPE", "con", "show"])
    if code != 0:
        return []
    return [row[0] for row in _rows(out)
            if len(row) >= 2 and row[1] == "802-11-wireless" and row[0] != AP_PROFILE]


# --- Access Point de configuracao -------------------------------------------
def ap_ssid() -> str:
    """SSID unico por aparelho: PREGACAO-PI-XXXX (4 ultimos do MAC do Wi-Fi)."""
    configured = os.environ.get("PREGACAO_AP_SSID", "").strip()
    if configured:
        return configured
    suffix = ""
    try:
        with open("/sys/class/net/wlan0/address", encoding="utf-8") as fh:
            mac = fh.read().strip().replace(":", "")
        if len(mac) >= 6:
            suffix = mac[-4:].upper()
    except OSError:
        pass
    if not suffix:
        try:
            import socket as _socket
            tail = _socket.gethostname().replace("-", "")[-4:]
        except OSError:  # pragma: no cover - defesa
            tail = ""
        suffix = (tail or "PI01").upper()
    return f"PREGACAO-PI-{suffix}"


def ap_passphrase() -> str:
    return (os.environ.get("PREGACAO_AP_PASSPHRASE", "").strip()
            or DEFAULT_AP_PASSPHRASE)


def _ap_active() -> bool:
    """True quando o perfil do Access Point esta ativo (uma unica chamada)."""
    code, out, _ = run(["-t", "-f", "NAME,TYPE", "con", "show", "--active"])
    if code != 0:
        return False
    return any(row and row[0] == AP_PROFILE for row in _rows(out))


def _sem_senha(text: str, secret: str) -> str:
    """Apaga a senha de qualquer texto antes de logar ou devolver ao usuario."""
    if secret and secret in text:
        return text.replace(secret, "***")
    return text


def ap_status() -> Dict[str, Any]:
    active = _ap_active()
    dev = wifi_device()
    return {
        "active": active,
        "ssid": ap_ssid(),
        "ip": AP_GATEWAY,
        "address": AP_ADDRESS,
        "device": dev,
        "profile": AP_PROFILE,
        "state": "ativo" if active else "inativo",
    }


def ap_enable(timeout: int = 40) -> None:
    """Cria (se preciso) e ativa o Access Point de configuracao.

    O perfil e sempre RE-CRIADO quando o AP esta parado. Assim SSID e senha
    vem sempre do .env vigente e nenhuma senha precisa ser lida de volta do
    NetworkManager (a senha nunca aparece em argv, log ou resposta de API).

    Se o AP ja esta ativo nao ha nada a fazer (evita derrubar a conexao de
    quem ja esta configurando o equipamento pelo celular).
    """
    if not nmcli_available():
        raise NetworkError("nmcli indisponivel neste sistema")
    ssid = validate_ssid(ap_ssid())
    passphrase = ap_passphrase()

    if _ap_active():
        log.info("[NETWORK] Access Point ja ativo: %s", ssid)
        return

    log.info(MSG_AP_STARTING)
    if _profile_type(AP_PROFILE) != "":
        _must(["con", "delete", "id", AP_PROFILE], timeout=20)

    _must([
        "con", "add", "type", "wifi", "ifname", wifi_device(),
        "con-name", AP_PROFILE,
        "autoconnect", "no",
        "802-11-wireless.mode", "ap",
        "802-11-wireless.ssid", ssid,
        "802-11-wireless.band", "bg",
        # O driver Broadcom do Raspberry Pi recusa a chave IGTK do 802.11w ao
        # montar o hotspot: o wpa_supplicant aborta com "key setting
        # validation failed" e o NetworkManager derruba a ativacao
        # (raspberrypi/linux#7247). pmf=1 desliga o 802.11w e o AP sobe.
        "802-11-wireless-security.key-mgmt", "wpa-psk",
        "802-11-wireless-security.pmf", "1",
        "ipv4.method", "shared",
        "ipv4.addresses", AP_ADDRESS,
    ], timeout=20)
    log.info("[NETWORK] perfil do Access Point criado: %s", ssid)

    # A senha entra SOMENTE por stdin (`nmcli --ask`): em argv apareceria em
    # `ps`. O `con add --ask` faria varias perguntas, entao o perfil nasce sem
    # a senha e ela e gravada na primeira ativacao, em que o nmcli pede unica
    # e exclusivamente o WPA key. A repeticao cobre um eventual segundo pedido.
    code, _, err = run(["--ask", "con", "up", AP_PROFILE],
                       stdin=f"{passphrase}\n" * 3, timeout=timeout)
    if code != 0:
        # a senha ja ficou gravada no perfil; a falha pode ser transitoria
        # (interface ocupada), entao tenta subir com o segredo ja salvo.
        log.warning("[NETWORK] ativacao do AP: %s",
                    _sem_senha(" ".join((err or "").split())[:200], passphrase))
        try:
            _must(["con", "up", AP_PROFILE], timeout=timeout)
        except NetworkError as exc:
            raise NetworkError(_sem_senha(str(exc), passphrase)) from None

    log.info(MSG_AP_ACTIVE)
    log.info("[NETWORK] AP SSID=%s address=%s", ssid, AP_ADDRESS)


def ap_disable() -> None:
    if _profile_type(AP_PROFILE) == "":
        return
    log.info(MSG_AP_STOPPING)
    code, _, _ = run(["con", "down", AP_PROFILE])
    if code == 0:
        log.info("[NETWORK] Configuration AP inactive")


def ap_delete() -> None:
    if _profile_type(AP_PROFILE) != "":
        _must(["con", "delete", "id", AP_PROFILE])
