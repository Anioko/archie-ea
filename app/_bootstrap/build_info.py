"""Single build identity for cache-busting and the /version endpoint (ARCH-062).

Before this module existed, two independent mechanisms computed their own version
stamp: `context_processors.py` used a git short-hash (or a startup timestamp
fallback) to auto-version every `url_for('static', ...)` call, while
`assets.py`'s `asset_url` filter used a per-file mtime. Because those two clocks
disagree, the same deploy could — and did — serve five distinct `?v=` stamps in a
single session, so there was no single build identity to attribute a bug report,
a rollback, or a support ticket to.

`get_build_id()` computes the identifier exactly once per process (git short SHA,
falling back to a process-start timestamp when not running from a git checkout)
and every cache-busting code path — the `url_for` override, the `asset_url`
filter, and the `/version` endpoint — calls this single function.
"""

import subprocess
import time

_build_id = None


def get_build_id():
    """Return this process's build identifier, computing it once and caching it."""
    global _build_id
    if _build_id is not None:
        return _build_id
    try:
        _build_id = subprocess.check_output(
            ["git", "rev-parse", "--short=8", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode("utf-8").strip()
    except Exception:
        _build_id = str(int(time.time()))
    return _build_id
