"""Linux-only, loopback-only Gunicorn recycling regression; no Archie imports.

Run with the Gunicorn version under investigation installed in this interpreter.
All measured HTTP failures are retained; no measured request is retried.
"""

import argparse
import http.client
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time


def app(environ, start_response):
    """Minimal in-memory WSGI application, also imported by Gunicorn."""
    body = json.dumps({"pid": os.getpid()}).encode("ascii")
    start_response("200 OK", [("Content-Type", "application/json"),
                              ("Content-Length", str(len(body)))])
    return [body]


def _request(connection, path):
    connection.request("GET", path)
    response = connection.getresponse()
    body = response.read(1024)
    if response.status != 200:
        raise ValueError("HTTP %d" % response.status)
    pid = json.loads(body)["pid"]
    if type(pid) is not int or pid <= 0:
        raise ValueError("response did not identify a worker PID")
    return pid


def _deadline(signum, frame):
    raise TimeoutError("75-second diagnostic deadline exceeded")


def _stop(process):
    """Only signal the new process group created for this diagnostic."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    # The master may have exited while a worker remained. Kill this owned group
    # as well, without finding or touching any unrelated Gunicorn processes.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=(
        "Check real Gunicorn gthread worker recycling over loopback on Linux. "
        "Prints request evidence, a JSON summary and server logs; exits nonzero "
        "on any failure or fewer than three responding worker PIDs. Runtime <90s."))
    parser.parse_args(argv)
    if not sys.platform.startswith("linux"):
        print("Unsupported platform: run this diagnostic on Linux.", file=sys.stderr)
        return 2
    try:
        version = importlib.metadata.version("gunicorn")
    except importlib.metadata.PackageNotFoundError:
        print("Gunicorn must already be installed in this interpreter.", file=sys.stderr)
        return 2

    started = time.monotonic()
    records = []
    error = None
    cleanup_error = None
    process = None
    connection = None
    old_handler = signal.signal(signal.SIGALRM, _deadline)
    signal.alarm(75)
    server_log = ""
    try:
        with tempfile.TemporaryDirectory(prefix="gunicorn-recycling-") as directory:
            log_path = Path(directory) / "server.log"
            try:
                with socket.socket() as listener, log_path.open("w+b") as log:
                    listener.bind(("127.0.0.1", 0))
                    listener.listen(128)
                    port = listener.getsockname()[1]
                    # Reserve the exact loopback socket through startup. The
                    # temp cwd prevents repo gunicorn.conf.py from loading.
                    command = [sys.executable, "-m", "gunicorn",
                               "--bind", "fd://%d" % listener.fileno(),
                               "--pythonpath", str(Path(__file__).resolve().parent),
                               "--workers", "1", "--worker-class", "gthread",
                               "--threads", "8", "--max-requests", "10",
                               "--max-requests-jitter", "0",
                               "--error-logfile", "-", "--log-level", "info",
                               "check_worker_recycling:app"]
                    env = os.environ.copy()
                    env.pop("GUNICORN_CMD_ARGS", None)
                    env.pop("PYTHONPATH", None)
                    process = subprocess.Popen(
                        command, cwd=directory, env=env, stdout=log,
                        stderr=subprocess.STDOUT, start_new_session=True,
                        pass_fds=(listener.fileno(),))
                    # A readiness request is separate from measured traffic.
                    # The listening socket is already reserved: this first
                    # request can wait for worker startup without polling.
                    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                    readiness_pid = _request(connection, "/ready")
                    connection.close()
                    connection = None
                    print(json.dumps({"event": "ready", "pid": readiness_pid,
                                      "gunicorn": version}), flush=True)

                    for mode in ("fresh", "reused"):
                        for index in range(40):
                            if time.monotonic() - started >= 65:
                                raise TimeoutError("measured request budget exhausted")
                            if process.poll() is not None:
                                raise RuntimeError("Gunicorn master exited during measurement")
                            if connection is None:
                                connection = http.client.HTTPConnection(
                                    "127.0.0.1", port, timeout=2)
                            record = {"event": "request", "sequence": len(records) + 1,
                                      "mode": mode}
                            try:
                                record["pid"] = _request(connection, "/%s/%d" % (mode, index))
                                record["success"] = True
                            except (OSError, http.client.HTTPException, ValueError, KeyError) as exc:
                                record["success"] = False
                                record["error"] = ("%s: %s" % (type(exc).__name__, exc))[:300]
                                connection.close()
                                connection = None
                            records.append(record)
                            print(json.dumps(record), flush=True)
                            if mode == "fresh" and connection is not None:
                                connection.close()
                                connection = None
            finally:
                # Keep cleanup inside the temporary-directory lifetime so the
                # server log remains available even after startup/HTTP errors.
                signal.alarm(0)
                if connection is not None:
                    connection.close()
                if process is not None:
                    try:
                        _stop(process)
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        cleanup_error = "%s: %s" % (type(exc).__name__, exc)
                if log_path.exists():
                    server_log = log_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, http.client.HTTPException, ValueError, KeyError, RuntimeError) as exc:
        error = ("%s: %s" % (type(exc).__name__, exc))[:300]
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    successes = sum(record["success"] for record in records)
    pids = sorted({record["pid"] for record in records if record["success"]})
    passed = (len(records) == 80 and successes == 80 and len(pids) >= 3
              and error is None and cleanup_error is None)
    print(json.dumps({"event": "summary", "passed": passed, "gunicorn": version,
                      "measured_requests": len(records), "successes": successes,
                      "failures": len(records) - successes, "worker_pids": pids,
                      "minimum_worker_pids": 3, "error": error,
                      "cleanup_error": cleanup_error,
                      "elapsed_seconds": round(time.monotonic() - started, 3)}, sort_keys=True),
          flush=True)
    print("--- Gunicorn subprocess log ---", flush=True)
    print(server_log[-24000:], flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
