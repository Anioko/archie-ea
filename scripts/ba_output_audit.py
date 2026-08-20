"""Audit Iain's 12 Business Architecture outputs against what the app can serve.

For each output: does a route exist, is its blueprint actually registered, and is
there any navigation path to it? A route that exists but is unreachable or
unlinked is why a competent architect concluded the feature was missing.

    python scripts/ba_output_audit.py
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# (label, regex matching the URL path of a route that would serve this output)
OUTPUTS = [
    ("1. Capability maps", r"capability-map|capability_map"),
    ("2. Capability maturity", r"capability-maturity"),
    ("3. Value stream maps", r"value-stream|value_stream"),
    ("4. Org & ownership views", r"ownership|org-chart|organisation|organization-view"),
    ("5. Information/data maps", r"data-lineage|information-model|data-map|business-information"),
    ("6. Strategy-to-execution", r"strategy-map|strategy-to-execution|motivation|strategy_map"),
    ("7. Stakeholder maps", r"stakeholder"),
    ("8. Initiative/project alignment", r"work-package|workpackage|initiative|programme|portfolio-roadmap"),
    ("9. KPI/metric dashboards", r"/metric|kpi|measure"),
    ("10. Products & services", r"product-service|products|business-service|service-catalog"),
    ("11. Policies & governance", r"policy|policies|governance"),
    ("12. Gap analysis & roadmaps", r"gap-analysis|gap_analysis|roadmap"),
]

ROUTE_RE = re.compile(r"@(\w+)\.route\(\s*[\"']([^\"']+)[\"']")


def collect_routes() -> list[tuple[str, str, Path]]:
    out = []
    for py in REPO.joinpath("app").rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        try:
            src = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for bp, path in ROUTE_RE.findall(src):
            out.append((bp, path, py))
    return out


def registered_blueprint_vars() -> set[str]:
    """Blueprint *variable* names that appear in a register_blueprint call anywhere."""
    names: set[str] = set()
    for py in REPO.joinpath("app").rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        try:
            src = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"register_blueprint\(\s*([A-Za-z_][\w.]*)", src):
            names.add(m.group(1).split(".")[-1])
        for m in re.finditer(r"fromlist=\[[\"'](\w+)[\"']\]", src):
            names.add(m.group(1))
        for m in re.finditer(r"\(\s*[\"'][\w.]+[\"']\s*,\s*[\"'](\w+)[\"']\s*,", src):
            names.add(m.group(1))
    return names


def nav_mentions() -> str:
    blob = []
    for p in [
        REPO / "app" / "utils" / "role_access.py",
        REPO / "app" / "services" / "sidebar_discovery_service.py",
    ]:
        if p.exists():
            blob.append(p.read_text(encoding="utf-8", errors="replace"))
    for tpl in REPO.joinpath("app", "templates", "components").glob("*sidebar*.html"):
        blob.append(tpl.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(blob)


def main() -> int:
    routes = collect_routes()
    registered = registered_blueprint_vars()
    nav = nav_mentions()

    print(f"scanned {len(routes)} routes; {len(registered)} registered blueprint names\n")
    print(f"{'OUTPUT':34} {'ROUTES':>6} {'REACHABLE':>10} {'IN NAV':>7}")
    print("-" * 62)

    for label, pat in OUTPUTS:
        rx = re.compile(pat, re.I)
        hits = [(bp, path) for bp, path, _ in routes if rx.search(path)]
        bps = {bp for bp, _ in hits}
        # a route is reachable if its blueprint var looks registered
        reachable = sum(1 for bp in bps if bp in registered or f"{bp}_bp" in registered)
        in_nav = "yes" if rx.search(nav) else "NO"
        print(f"{label:34} {len(hits):>6} {reachable:>4}/{len(bps):<5} {in_nav:>7}")

    print("\nlegend: REACHABLE = blueprints registered / blueprints owning those routes")
    print("        IN NAV    = the output is referenced anywhere nav is built")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
