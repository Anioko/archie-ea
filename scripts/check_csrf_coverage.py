#!/usr/bin/env python
"""verify.py gate: every state-changing route must be CSRF-protected or on
the explicit, justified opt-out list in app/_bootstrap/csrf_coverage.py.

P-04 (S1): CSRF was found enforced on none of the JSON write endpoints in a
live probe, despite flask-wtf's CSRFProtect being wired globally. Whatever
the live cause, the fix required is default-deny with an enumerated,
asserted route table — this script IS that assertion, runnable outside a
live server so it can gate CI.

Exit 0: every write route is either protected, or exempt for a reason
recorded in csrf_coverage.py.
Exit 1: an exemption exists that is not declared and justified.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    os.environ.setdefault("FLASK_CONFIG", "testing")
    os.environ.setdefault(
        "TEST_DATABASE_URL",
        os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/archie_test"),
    )

    from app import create_app
    from app._bootstrap.csrf_coverage import audit

    app = create_app("testing")
    # Boot-time assertion already ran inside create_app(); re-run the audit
    # here purely to report numbers (create_app would already have raised
    # CsrfCoverageError and aborted if coverage were bad).
    result = audit(app)

    print(f"CSRF coverage: {result['total']} write routes total")
    print(f"  protected (flask-wtf CSRFProtect): {len(result['protected'])}")
    print(f"  justified opt-outs:                {len(result['exempt_allowed'])}")
    print(f"  UNJUSTIFIED exemptions:            {len(result['exempt_unjustified'])}")

    if result["exempt_unjustified"]:
        for e in result["exempt_unjustified"]:
            print(f"    - {e['dest']} ({', '.join(e['methods'])} {e['rule']})")
        print("FAIL: undeclared CSRF exemption(s) found.")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
