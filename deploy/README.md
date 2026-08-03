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

## Deploying code changes — read this first

`gunicorn.conf.py` sets `preload_app = True`. The application is imported once in
the gunicorn MASTER process, and workers are forked from it.

**`SIGHUP` does NOT reload Python code under preload.** It reloads configuration
and gracefully re-forks workers — from a master still holding the old modules.
Worker PIDs change, the site stays up, and every check looks like a successful
deploy while the running code is unchanged.

This was discovered on 2026-07-31: the master had been running since 13:14 the
previous day while the tree on disk was hours newer, so several Python fixes
appeared deployed and were not.

    Python code (.py)          -> docker restart archie-ea-server-1   (~180s)
    New blueprints/routes      -> docker restart archie-ea-server-1
    Templates (.html), static  -> SIGHUP is sufficient; Jinja reads from disk
                                  and a worker re-fork clears its cache

Verify a Python deploy actually landed rather than assuming — compare the master
process start time against the file you changed:

    docker exec archie-ea-server-1 sh -c 'stat -c %y /proc/<master_pid>'
    stat -c %y /root/archie-ea/<changed_file>

If the master predates the file, the change is not running.

## The deploy procedure

`deploy/deploy.sh` does the whole sequence on the application host. Every step in
it exists because that step has already caught a real failure — see the comments
at the top of the script.

    # from a workstation: put the code on the host, then run the deploy
    git push ssh://root@10.106.0.6/root/archie-ea HEAD:refs/heads/deploy-$(date +%Y%m%d)
    ssh -J root@165.22.125.156 root@10.106.0.6 \
        'cd /root/archie-ea && ./deploy/deploy.sh deploy-YYYYMMDD'

It refuses a non-fast-forward unless given `--force`, dumps the database first,
verifies subresource integrity **before** restarting, restarts rather than
SIGHUPing, and **rolls itself back if health does not return**. It prints the
rollback command and the dump path on the way out.

Then verify what users actually get, in a browser, from a workstation:

    python deploy/verify_production.py https://165-22-125-156.sslip.io

    # optionally walk signed-in pages too
    SMOKE_EMAIL=... SMOKE_PASSWORD=... python deploy/verify_production.py https://...

### Why both, and why the second one matters

`tests/smoke/` runs in CI against a seeded database and proves the **code** is
good. `deploy/verify_production.py` proves the **deployment** is good — that the
bytes being served behave in a browser.

Those are not the same thing, and the gap between them is not theoretical. On
2026-07-31 a Windows checkout rewrote the vendored JavaScript to CRLF, which
changed every file's SHA-384 and so broke the `integrity=` attributes. The
templates stayed valid, every test passed, every route returned 200 — and the
browser refused to execute Alpine, DOMPurify and the icon library, leaving the
entire interface inert. Nothing server-side can see that. `.gitattributes` now
pins those files with `-text`, and `deploy.sh` checks the hashes before it
restarts anything.

### Topology

    https://165-22-125-156.sslip.io   ->  165.22.125.156  archie-proxy  (Caddy)
                                              |  reverse_proxy 10.106.0.6:5000
                                              v
                                          10.106.0.6      archie-oss    (the app)

The app host has no public address; reach it with
`ssh -J root@165.22.125.156 root@10.106.0.6`. The proxy's own key is not
authorised on the app host, so use ProxyJump from a workstation rather than
hopping manually.

### Known friction: the host pulls from a repo we cannot push to

The droplet's `origin` is `Anioko/archie-ea`, and the working credentials get 403
against it. That is why deploys go over SSH to a `deploy-*` branch instead of
`git pull`, and why the host sits on a deploy branch rather than `main`.

Fixing it — grant push access to `Anioko`, or repoint `origin` at
`saint-gobain-archie` — reduces a deploy to `git pull && ./deploy/deploy.sh main`.
Until then, delete merged deploy branches occasionally:

    git branch --list 'deploy-*' --format='%(refname:short)' | while read b; do
        [ "$b" = "$(git rev-parse --abbrev-ref HEAD)" ] && continue
        git merge-base --is-ancestor "$b" HEAD && git branch -D "$b"
    done
