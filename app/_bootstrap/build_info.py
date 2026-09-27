"""Single build identity for cache-busting and the /version endpoint (ARCH-062).

Before this module existed, two independent mechanisms computed their own version
stamp: `context_processors.py` used a git short-hash (or a startup timestamp
fallback) to auto-version every `url_for('static', ...)` call, while
`assets.py`'s `asset_url` filter used a per-file mtime. Because those two clocks
disagree, the same deploy could — and did — serve five distinct `?v=` stamps in a
single session, so there was no single build identity to attribute a bug report,
a rollback, or a support ticket to.

`get_build_id()` computes the identifier exactly once per process and every
cache-busting code path — the `url_for` override, the `asset_url` filter, and the
`/version` endpoint — calls this single function.

Resolution order, and why it is not just "run git":

1. ``ARCHIE_BUILD_ID`` if set. Lets a deploy pin the identity explicitly.
2. ``git rev-parse``, run with ``safe.directory`` exceptions. The naive call
   FAILS IN PRODUCTION and this was verified on the live container, not assumed:

       $ docker exec archie-ea-server-1 sh -lc 'id; cd /app && git rev-parse HEAD'
       uid=1000(appuser) gid=1000(appuser)
       fatal: detected dubious ownership in repository at '/app'

   docker-compose bind-mounts the host checkout (``./:/app``) and the image drops
   to ``appuser`` (Dockerfile: ``useradd``/``USER appuser``), while the host
   checkout is root-owned. Git refuses to read a repository owned by another
   user. Without the exception every boot fell through to the timestamp branch.
3. A content hash of the committed CSS bundle. Stable across restarts of the
   same code and changes when the code changes — which is the entire property a
   build id needs. The timestamp fallback it replaces was actively harmful: it
   minted a NEW id on every process start, so each OOM restart (see ARCH-001)
   busted every user's asset cache and made /version meaningless for attributing
   a bug report to a build.
4. A timestamp, only if even the source tree cannot be read.
"""

import hashlib
import os
import subprocess
import time
from pathlib import Path

_build_id = None

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Rebuilt whenever templates change, committed to the repo, and present in every
# deployment — so its content is a good proxy for "which build is this".
_FINGERPRINT_FILE = _REPO_ROOT / "app" / "static" / "css" / "tailwind-output.css"


def _from_git():
    """Short SHA, or None. See the module docstring for the ownership caveat."""
    try:
        out = subprocess.check_output(
            [
                "git",
                "-c", "safe.directory=*",
                "-c", f"safe.directory={_REPO_ROOT}",
                "rev-parse", "--short=8", "HEAD",
            ],
            cwd=str(_REPO_ROOT),
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except Exception:
        return None
    return out.decode("utf-8").strip() or None


def _from_content():
    """Hash of the committed CSS bundle, or None if it cannot be read."""
    try:
        digest = hashlib.sha256(_FINGERPRINT_FILE.read_bytes()).hexdigest()
    except Exception:
        return None
    return f"c{digest[:7]}"


def get_build_id():
    """Return this process's build identifier, computing it once and caching it."""
    global _build_id
    if _build_id is not None:
        return _build_id
    _build_id = (
        (os.environ.get("ARCHIE_BUILD_ID") or "").strip()
        or _from_git()
        or _from_content()
        or str(int(time.time()))
    )
    return _build_id
