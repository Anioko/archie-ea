"""How much of the product has ever been exercised?

Coverage tools measure lines. This measures *routes* — the unit a user actually
touches. A route no test has ever hit is unverified by definition, however green
the line coverage looks, and this repo has 3,466 of them.

Run as a pytest plugin, it records every endpoint served during a test run:

    python -m pytest tests/ -p scripts.route_verification_audit -q

then writes ``route_verification.json`` and prints the gap. Run standalone, it
reports the static picture — every route, whether it is reachable from any
persona's navigation, and whether a test has ever exercised it:

    python scripts/route_verification_audit.py [--count]

``--count`` prints a single integer (unverified routes that ARE in navigation),
for use as a verify.py ratchet: a route a user can click and no test has ever
run is the combination that actually hurts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

RESULTS = REPO / "route_verification.json"

# ── pytest plugin half ────────────────────────────────────────────────────────
_seen: set[str] = set()


def pytest_configure(config):  # noqa: ARG001 - pytest hook
    """Wrap Flask's full_dispatch_request so every served endpoint is recorded."""
    try:
        from flask import Flask, request
    except ImportError:  # pragma: no cover
        return

    original = Flask.full_dispatch_request

    def recording_dispatch(self):
        try:
            response = original(self)
        finally:
            endpoint = getattr(request, "endpoint", None)
            if endpoint:
                _seen.add(endpoint)
        return response

    Flask.full_dispatch_request = recording_dispatch


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001 - pytest hook
    RESULTS.write_text(json.dumps(sorted(_seen), indent=0), encoding="utf-8")
    print(f"\nroute-verification: {len(_seen)} endpoints exercised -> {RESULTS.name}")


# ── standalone report half ────────────────────────────────────────────────────
def _nav_endpoints() -> set[str]:
    from app.utils.role_access import SIDEBAR_ZONES

    return {
        link.get("endpoint")
        for zones in SIDEBAR_ZONES.values()
        for zone in zones
        for link in zone.get("links", [])
        if link.get("endpoint")
    }


def _all_endpoints() -> set[str]:
    from app import create_app

    app = create_app("testing")
    return {r.endpoint for r in app.url_map.iter_rules() if "static" not in r.endpoint}


def _exercised() -> set[str]:
    if RESULTS.exists():
        return set(json.loads(RESULTS.read_text(encoding="utf-8")))
    return set()


def unverified_in_nav() -> int:
    """Routes a user can reach from the sidebar that no test has ever exercised."""
    return len((_nav_endpoints() & _all_endpoints()) - _exercised())


def main() -> int:
    if "--count" in sys.argv:
        print(unverified_in_nav())
        return 0

    every = _all_endpoints()
    nav = _nav_endpoints() & every
    run = _exercised() & every

    print(f"  routes total              {len(every):>6}")
    print(f"  reachable from navigation {len(nav):>6}  ({len(nav) / len(every) * 100:.1f}%)")
    if _exercised():
        print(f"  exercised by a test       {len(run):>6}  ({len(run) / len(every) * 100:.1f}%)")
        print(f"  IN NAV and never tested   {len(nav - run):>6}   <- the ones that hurt")
        for ep in sorted(nav - run):
            print(f"      {ep}")
    else:
        print("  exercised by a test          n/a  (run pytest with -p scripts.route_verification_audit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
