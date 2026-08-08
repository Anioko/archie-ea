#!/usr/bin/env python
"""Compare what requirements.txt pins against what is actually installed and running.

    python scripts/check_deployed_deps.py                 # check the local environment
    python scripts/check_deployed_deps.py --remote        # check the production container
    python scripts/check_deployed_deps.py --json

Why this exists
---------------
`dependency-cves` reads requirements.txt. That measures intent. It reported 62
advisories resolved and stayed green for weeks while production ran every one of
them, because deploy.sh recreated the container from an existing image and never
rebuilt:

    running image built     2026-07-12
    Pillow      pinned >=12.3.0   installed 10.4.0   (24 advisories)
    pypdf       pinned >=6.14.2   installed 5.9.0    (35 advisories)
    weasyprint  pinned >=60.0     installed 60.2

Nothing was comparing the two, so nothing could notice. deploy.sh now builds, but
the missing build step was the symptom; the absent check was the reason it went
unnoticed for weeks. A gate that cannot distinguish "we pinned it" from "it is
running" will report success indefinitely.

This compares the pin to the installed distribution and fails on any package that
is missing or below its floor. It deliberately checks the *floor* only: upper
bounds are a compatibility decision, and a package sitting under its ceiling is
not a security finding.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO_ROOT / "requirements.txt"
HOST = "root@134.122.105.56"

# name, operator, version — ignores extras, markers, comments and unpinned lines.
PIN = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*(?:\[[^\]]+\])?\s*(>=|==)\s*([0-9][0-9A-Za-z._-]*)")


def parse_requirements(path: Path) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """Return (pins, skipped).

    Lines carrying an environment marker are skipped and reported rather than
    checked. python-magic-bin is pinned `; platform_system == "Windows"`, so on
    the Linux container it is correctly absent — reporting that as a mismatch
    would be the check being wrong, not the deployment. Evaluating markers
    properly needs the TARGET environment, which differs between --remote and
    local, so they are surfaced instead of guessed at.
    """
    pins: dict[str, tuple[str, str]] = {}
    skipped: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        if ";" in line:
            match = PIN.match(line)
            skipped.append(match.group(1) if match else line[:40])
            continue
        match = PIN.match(line)
        if match:
            pins[match.group(1).lower().replace("_", "-")] = (match.group(2), match.group(3))
    return pins, skipped


def _version_tuple(value: str) -> tuple:
    """Compare on leading numeric components; good enough for floor checks."""
    parts = []
    for chunk in re.split(r"[._-]", value):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            break
    return tuple(parts)


def installed_local() -> dict[str, str]:
    import importlib.metadata as md

    return {d.metadata["Name"].lower().replace("_", "-"): d.version
            for d in md.distributions() if d.metadata.get("Name")}


def installed_remote() -> dict[str, str]:
    script = (
        "import importlib.metadata as md, json; "
        "print(json.dumps({d.metadata['Name'].lower().replace('_','-'): d.version "
        "for d in md.distributions() if d.metadata.get('Name')}))"
    )
    proc = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=25", HOST,
         f"cd /root/archie-ea && docker compose exec -T server python -c \"{script}\" 2>/dev/null"],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError(f"could not read remote packages: {(proc.stderr or '')[:200]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--remote", action="store_true",
                        help="check the running production container instead of this machine")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    pins, skipped = parse_requirements(REQUIREMENTS)
    try:
        have = installed_remote() if args.remote else installed_local()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    problems = []
    for name, (op, want) in sorted(pins.items()):
        got = have.get(name)
        if got is None:
            problems.append({"package": name, "pinned": f"{op}{want}",
                             "installed": None, "issue": "not installed"})
            continue
        if op == "==" and got != want:
            problems.append({"package": name, "pinned": f"=={want}",
                             "installed": got, "issue": "version mismatch"})
        elif op == ">=" and _version_tuple(got) < _version_tuple(want):
            problems.append({"package": name, "pinned": f">={want}",
                             "installed": got, "issue": "BELOW the pinned floor"})

    where = "production container" if args.remote else "local environment"
    if args.json:
        print(json.dumps({"checked": len(pins), "where": where,
                          "skipped_env_markers": skipped, "problems": problems}, indent=2))
    else:
        for p in problems:
            print(f"  {p['package']:24s} pinned {p['pinned']:<16s} "
                  f"installed {str(p['installed']):<12s} {p['issue']}")
        if problems:
            print(f"\n{len(problems)} of {len(pins)} pinned package(s) do not match the "
                  f"{where}.\nThe pin is not what is running — rebuild the image "
                  f"(deploy.sh now does this).")
        else:
            print(f"All {len(pins)} pinned package(s) match the {where}.")
        if skipped:
            print(f"({len(skipped)} pin(s) skipped for carrying an environment marker: "
                  f"{', '.join(skipped)})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
