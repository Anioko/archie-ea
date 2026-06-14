"""
A.R.C.H.I.E. Production Gunicorn Configuration (S2-03)

Usage:
    gunicorn -c gunicorn.conf.py manage:app

Environment variables:
    GUNICORN_WORKERS      — Number of worker processes (default: CPU*2+1)
    GUNICORN_THREADS      — Threads per worker (default: 4)
    GUNICORN_BIND         — Bind address (default: 0.0.0.0:5000)
    GUNICORN_TIMEOUT      — Worker timeout in seconds (default: 120)
    GUNICORN_GRACEFUL_TIMEOUT — Graceful shutdown timeout (default: 30)
    GUNICORN_MAX_REQUESTS  — Requests before worker restart (default: 2000)
    GUNICORN_LOG_LEVEL    — Log level (default: info)
"""

import multiprocessing
import os

# ---------------------------------------------------------------------------
# Server socket
# ---------------------------------------------------------------------------
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:5000")
backlog = 2048

# ---------------------------------------------------------------------------
# Worker processes
# ---------------------------------------------------------------------------
# Default: 2 * CPU cores + 1 (recommended by Gunicorn docs)
_default_workers = multiprocessing.cpu_count() * 2 + 1
workers = int(os.environ.get("GUNICORN_WORKERS", _default_workers))

# Use gthread worker class for mixed I/O workloads (DB queries + API calls)
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", 4))

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
# Worker timeout — kill workers that hang longer than this
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))

# Graceful shutdown — time to finish in-flight requests before SIGKILL
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", 30))

# Keep-alive connections — seconds to wait for next request on same connection
keepalive = 5

# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------
# Restart workers after N requests to prevent memory leaks
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 10000))

# Jitter: randomize restart to avoid all workers restarting simultaneously
max_requests_jitter = 200

# Preload app for faster worker fork (shared memory for read-only data)
preload_app = True

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
accesslog = "-"  # stdout
errorlog = "-"   # stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# ---------------------------------------------------------------------------
# Process naming
# ---------------------------------------------------------------------------
proc_name = "archie"

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
# Limit request sizes to prevent abuse
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# ---------------------------------------------------------------------------
# Server hooks
# ---------------------------------------------------------------------------


def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("A.R.C.H.I.E. starting with %d workers", server.app.cfg.workers)


def post_fork(server, worker):
    """Called after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)


def worker_exit(server, worker):
    """Called when a worker exits."""
    server.log.info("Worker exited (pid: %s)", worker.pid)
