"""SSE responses must not set the hop-by-hop ``Connection`` header.

PEP 3333 forbids a WSGI application from setting hop-by-hop headers - the
server owns the connection. gunicorn tolerates ``Connection: keep-alive`` and
strips it, but waitress asserts on it and turns the response into a 500
(verified: a minimal WSGI app setting the header is served as 500 by waitress).

Five streaming endpoints set it. This test is a source-level guard because the
endpoints themselves need job fixtures and a live stream to reach; the header
is set as a literal in the response-headers dict, so the literal is the thing
to keep out of the tree.
"""

from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"""["']Connection["']\s*:\s*["']keep-alive["']""", re.IGNORECASE)


def test_no_route_sets_the_hop_by_hop_connection_header():
    offenders = []
    for path in (REPO_ROOT / "app").rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{lineno}")
    assert not offenders, (
        "Connection is a hop-by-hop header and is forbidden by PEP 3333; "
        "waitress serves such a response as a 500. Remove it from: "
        + ", ".join(offenders)
    )


def test_waitress_really_does_reject_the_header():
    """Pin the premise, so the guard above cannot be dismissed as pedantry."""
    from waitress.task import hop_by_hop

    assert "connection" in hop_by_hop
