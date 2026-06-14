"""
Codegen acceptance-check runner (increment 3).

Bridges the component spec's `acceptance_checks` (prose assertions produced by the
deriver) to executable HTTP checks against a running generated app — the functional
equivalent of clone-website's visual-QA diff.

Two pieces, both honest about what can be automated:
  - plan_acceptance_checks(specs): PURE. Classifies each acceptance check as
    executable (a parseable "METHOD /path -> STATUS" with no path params) or
    manual (needs auth/fixture/state setup). Nothing is silently dropped.
  - run_acceptance_checks(specs, base_url): executes the executable subset via
    urllib and reports pass/fail + the manual coverage that still needs a harness.

verify_generation.sh consumes this via an optional --specs-file; with no specs it
is a no-op, so existing route-testing behaviour is unchanged.
"""

import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List

# "GET /work-orders -> 200"  /  "POST /work-orders -> 201"
_ROUTE_RE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)\s*->\s*(\d{3})\b")


def plan_acceptance_checks(specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Turn every acceptance check across all module specs into a plan entry.

    Executable iff: category == 'route', the assertion parses as METHOD /path -> STATUS,
    and the path has no `{...}` placeholder (those need a real record id first).
    """
    plan = []
    for spec in specs:
        module = spec.get("module_key")
        for chk in spec.get("acceptance_checks", []):
            entry = {
                "module_key": module,
                "id": chk.get("id"),
                "category": chk.get("category"),
                "assertion": chk.get("assertion", ""),
                "source_genome_path": chk.get("source_genome_path"),
                "executable": False,
                "reason": None,
            }
            m = _ROUTE_RE.match(entry["assertion"]) if chk.get("category") == "route" else None
            if m and "{" not in m.group(2):
                entry.update(executable=True, method=m.group(1),
                             path=m.group(2), expected_status=int(m.group(3)))
            else:
                entry["reason"] = (
                    "needs a record id (path param)" if (m and "{" in m.group(2))
                    else f"category '{chk.get('category')}' needs auth/fixture/state setup"
                )
            plan.append(entry)
    return plan


def run_acceptance_checks(specs: List[Dict[str, Any]], base_url: str, timeout: int = 10) -> Dict[str, Any]:
    """Execute the executable plan entries against a running app; report the rest."""
    plan = plan_acceptance_checks(specs)
    base = base_url.rstrip("/")
    results = []
    executed = passed = 0

    for entry in plan:
        if not entry["executable"]:
            results.append({**_public(entry), "outcome": "manual", "detail": entry["reason"]})
            continue
        executed += 1
        ok, detail = _execute(base, entry["method"], entry["path"], entry["expected_status"], timeout)
        if ok:
            passed += 1
        results.append({**_public(entry), "outcome": "pass" if ok else "fail", "detail": detail})

    manual = sum(1 for r in results if r["outcome"] == "manual")
    return {
        "total": len(plan),
        "executed": executed,
        "passed": passed,
        "failed": executed - passed,
        "manual": manual,
        "executable_pass_rate_pct": round(passed / executed * 100, 1) if executed else 0.0,
        "results": results,
    }


def _execute(base, method, path, expected_status, timeout):
    url = base + path
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            got = resp.status
    except urllib.error.HTTPError as e:
        got = e.code
    except Exception as e:  # noqa: BLE001
        return False, f"request error: {str(e)[:80]}"
    return got == expected_status, f"expected {expected_status}, got {got}"


def _public(entry):
    return {k: entry[k] for k in ("module_key", "id", "category", "assertion", "source_genome_path")}


# --------------------------------------------------------------------------- #
# CLI entry — invoked by verify_generation.sh / runner with a specs file.
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Run codegen acceptance checks against a running app.")
    p.add_argument("--specs-file", required=True, help="JSON file: list of component specs.")
    p.add_argument("--base-url", required=True, help="Base URL of the running generated app.")
    p.add_argument("--out", help="Optional JSON output path.")
    args = p.parse_args(argv)

    specs = json.loads(open(args.specs_file, encoding="utf-8").read())
    if isinstance(specs, dict):
        specs = [specs]
    report = run_acceptance_checks(specs, args.base_url)
    text = json.dumps(report, indent=2)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
    print(text)
    # Non-zero exit if any executed check failed (executable subset is the gate).
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
