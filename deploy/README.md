# Deployment artefacts (host-level, not container-level)

These live outside Docker on the app droplet. They are checked in here because
they otherwise exist on exactly one machine with no version history.

| File | Installed to | Purpose |
|---|---|---|
| `archie-watchdog.sh` | `/usr/local/bin/` | Restarts `archie-ea-server-1` when `/health` stops answering |
| `archie-watchdog.{service,timer}` | `/etc/systemd/system/` | Runs the watchdog every 60s |
| `Caddyfile.proxy` | `/etc/caddy/Caddyfile` on the **proxy** droplet (165.22.125.156) | TLS termination, timeouts, HSTS, upstream health checks; proxies to the app over the VPC address 10.106.0.6 |
| `caddy/caddy-restart-override.conf` | `/etc/systemd/system/caddy.service.d/override.conf` on the **proxy** droplet | `Restart=on-failure`. The unit shipped with no `Restart=` at all, so systemd's default of `Restart=no` applied to the single ingress point |
| `archie-backup.sh` | `/usr/local/bin/` | Verified 6-hourly `pg_dump` with retention and a success marker |
| `archie-backup.{service,timer}` | `/etc/systemd/system/` | Schedules the backup |

## Backups

`archie-backup.sh` runs every 6 hours. It verifies each dump is restorable
(`pg_restore --list`) rather than merely present, prunes at 14 days, and writes
`/var/backups/archie/LAST_SUCCESS`. The watchdog warns if that marker is more
than 18 hours old, because a backup that stops silently looks exactly like one
that works.

These dumps are on the SAME DISK as the database. That survives a bad query, not
a lost droplet. Shipping them off-box needs object-storage credentials.

Install:

    cp archie-backup.sh /usr/local/bin/ && chmod +x /usr/local/bin/archie-backup.sh
    cp archie-backup.service archie-backup.timer /etc/systemd/system/
    systemctl daemon-reload && systemctl enable --now archie-backup.timer

## Why the watchdog exists

Gunicorn's `timeout` cannot detect wedged `gthread` request threads: the worker's
main thread keeps answering the arbiter heartbeat while every request thread is
blocked. On 24-30 July 2026 all 8 request threads were pinned this way and the
site returned nothing for six days while the container reported healthy.

Install:

    cp archie-watchdog.sh /usr/local/bin/ && chmod +x /usr/local/bin/archie-watchdog.sh
    cp archie-watchdog.service archie-watchdog.timer /etc/systemd/system/
    systemctl daemon-reload && systemctl enable --now archie-watchdog.timer
