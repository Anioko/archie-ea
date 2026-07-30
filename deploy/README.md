# Deployment artefacts (host-level, not container-level)

These live outside Docker on the app droplet. They are checked in here because
they otherwise exist on exactly one machine with no version history.

| File | Installed to | Purpose |
|---|---|---|
| `archie-watchdog.sh` | `/usr/local/bin/` | Restarts `archie-ea-server-1` when `/health` stops answering |
| `archie-watchdog.{service,timer}` | `/etc/systemd/system/` | Runs the watchdog every 60s |
| `Caddyfile.proxy` | `/etc/caddy/Caddyfile` on the **proxy** droplet (165.22.125.156) | TLS termination, timeouts, upstream health checks |

## Why the watchdog exists

Gunicorn's `timeout` cannot detect wedged `gthread` request threads: the worker's
main thread keeps answering the arbiter heartbeat while every request thread is
blocked. On 24-30 July 2026 all 8 request threads were pinned this way and the
site returned nothing for six days while the container reported healthy.

Install:

    cp archie-watchdog.sh /usr/local/bin/ && chmod +x /usr/local/bin/archie-watchdog.sh
    cp archie-watchdog.service archie-watchdog.timer /etc/systemd/system/
    systemctl daemon-reload && systemctl enable --now archie-watchdog.timer
