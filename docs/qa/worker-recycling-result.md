# Gunicorn worker recycling diagnostic

Date: 2026-09-05. Status: implemented; Linux runtime verification pending.

The retained smoke-server log associated with CI artifact 33966263332 reportedly
places a max-requests worker recycle immediately before the enterprise architect
request failure. This is a hypothesis to investigate, not a confirmed cause.
[Gunicorn issue 3038](https://github.com/benoitc/gunicorn/issues/3038) documents a
small gthread/max-requests reproduction of connection resets during recycling.
Neither that report nor the timing alone establishes that upgrading fixes this
repository's failure.

Run on Linux with the Gunicorn version to investigate already installed:

```bash
python scripts/qa/check_worker_recycling.py
```

The script uses only the standard library except for the Gunicorn subprocess.
It imports no application code, accesses no database, and sends HTTP only to an
owned ephemeral listener bound to 127.0.0.1. Its temporary working directory
prevents the repository's Gunicorn configuration from loading; inherited
`GUNICORN_CMD_ARGS` and `PYTHONPATH` are removed. A reserved listening descriptor
is passed directly to Gunicorn, avoiding a port-release/rebind race.

The server uses one gthread worker, eight threads, max_requests=10 and zero
jitter. Default keepalive behavior is preserved. One readiness request precedes
80 measured requests: 40 using fresh connections, followed by 40 using a reused
HTTP connection. Every measured failure is recorded without retry; after a
failed connection the next distinct request starts a new connection. There is
no status allowlist. The WSGI response carries the actual responding worker PID.

Standard output contains readiness evidence, one JSON record per measured
request, a JSON summary, and the last 24,000 characters of the Gunicorn log.
The script returns 0 only if all 80 measured requests succeed and at least three
distinct responding worker PIDs prove multiple worker replacements. Any HTTP,
startup, deadline, insufficient-recycling or cleanup failure returns nonzero.
Unsupported platforms and a missing Gunicorn installation return 2.

A 75-second alarm bounds execution and cleanup is limited to another seven
seconds. Cleanup signals only the new process group created for this server,
including its worker. The measured loop also checks a 65-second budget.

Local Windows validation:

- Python bytecode compilation: passed.
- `--help`: passed, without importing or starting Gunicorn.
- Scoped Ruff correctness checks (`F,E4,E7,E9`): passed.
- Scoped whitespace diff check: passed.

No Linux Gunicorn process was run on Windows, and no packages were installed.
There is no runtime pass/fail result yet. CI must run the same script separately
against Gunicorn 22 and 23 and retain complete output. A finite green run is
evidence for this reproduction, not proof that all intermittent failures are
eliminated or that the broader smoke journey passes.
