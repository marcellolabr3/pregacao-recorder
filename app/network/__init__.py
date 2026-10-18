"""Camada de rede do pregacao-recorder.

Modulos:

    nm.py            -> NetworkManager (Ethernet, Wi-Fi, Access Point)
    connectivity.py  -> teste de Internet (mesma ideia do upload/queue)
    tailscale.py     -> acesso remoto via VPN privada
    status.py        -> monta o JSON de status mostrado no painel
    watchdog.py      -> daemon systemd que mantem o sistema acessivel
"""
