"""Capture the business-architecture screens and flag visual defects.

Static gates cannot tell you a page looks unfinished. This loads each screen in a
real browser and reports the measurable symptoms of a broken-looking layout:
content that occupies a fraction of its container, grids rendering a single item,
horizontal overflow, and pages whose entire body is an empty state.

    python scripts/ba_design_audit.py --base https://... --email ... --password ...
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SCREENS = [
    ("frameworks", "/capability-maturity/frameworks"),
    ("heatmap", "/capability-maturity/heatmap"),
    ("maturity-search", "/capability-maturity/search"),
    ("capability-map", "/capability-map/"),
    ("dashboard", "/dashboard/overview"),
    ("capability-health", "/strategic/capability-health"),
    ("applications", "/applications/"),
    ("archimate-elements", "/archimate/elements"),
    ("value-streams", "/value-streams/"),
    ("stakeholder-map", "/stakeholders/map"),
    ("gap-analysis", "/enterprise/implementation/gap-analysis"),
    ("roadmap", "/capability-roadmap"),
    ("work-packages", "/enterprise/implementation/work-packages"),
    ("portfolio", "/portfolio/"),
    ("arb-dashboard", "/arb/"),
    ("all-modules", "/modules"),
]


def audit(page, name: str, url: str, out_dir: Path) -> dict:
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(2200)

    metrics = page.evaluate(
        """() => {
        const main = document.querySelector('main') || document.body;
        const r = main.getBoundingClientRect();
        // widest run of real content inside main
        let widest = 0, tallest = 0;
        main.querySelectorAll('div,section,table,article').forEach(el => {
            const b = el.getBoundingClientRect();
            if (b.height > 40 && b.width > widest) widest = b.width;
            if (b.height > tallest) tallest = b.height;
        });
        // grids that render a single child
        let lonelyGrids = 0;
        document.querySelectorAll('[class*="grid-cols-"]').forEach(g => {
            const kids = [...g.children].filter(c => c.getBoundingClientRect().height > 20);
            const cls = g.className || '';
            const m = cls.match(/grid-cols-(\\d+)/g) || [];
            const maxCols = Math.max(...m.map(x => parseInt(x.split('-').pop(), 10)), 1);
            if (kids.length > 0 && maxCols >= 3 && kids.length < maxCols - 1) lonelyGrids++;
        });
        return {
            mainWidth: Math.round(r.width),
            contentWidth: Math.round(widest),
            contentHeight: Math.round(tallest),
            docScrollW: document.documentElement.scrollWidth,
            clientW: document.documentElement.clientWidth,
            lonelyGrids,
            bodyChars: (document.body.innerText || '').replace(/\\s+/g, ' ').length,
        };
    }"""
    )

    shot = out_dir / f"{name}.png"
    page.screenshot(path=str(shot), full_page=True)

    fill = metrics["contentWidth"] / metrics["mainWidth"] if metrics["mainWidth"] else 0
    flags = []
    if fill < 0.55:
        flags.append(f"content fills only {fill:.0%} of the container")
    if metrics["lonelyGrids"]:
        flags.append(f"{metrics['lonelyGrids']} grid(s) rendering far fewer items than columns")
    if metrics["docScrollW"] > metrics["clientW"] + 4:
        flags.append("horizontal overflow — the page scrolls sideways")
    if metrics["bodyChars"] < 400:
        # A 404 renders ~158 chars and 36% fill. Reporting that as a design flaw
        # sends someone to restyle a page that was never reached.
        flags.append(
            f"page has almost no content ({metrics['bodyChars']} chars) — "
            "check this URL resolves before treating it as a layout problem"
        )
    return {"name": name, "url": url, "flags": flags, "metrics": metrics, "shot": str(shot)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--out", default="design_audit")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(f"{args.base}/account/login", wait_until="domcontentloaded")
        page.fill('input[name="email"]', args.email)
        page.fill('input[name="password"]', args.password)
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("networkidle")
        if "login" in page.url:
            print("FAIL: login rejected")
            browser.close()
            return 2

        for name, path in SCREENS:
            try:
                results.append(audit(page, name, f"{args.base}{path}", out_dir))
            except Exception as exc:  # noqa: BLE001
                results.append({"name": name, "url": path, "flags": [f"ERROR {exc}"], "metrics": {}, "shot": ""})
        browser.close()

    print(f"{'SCREEN':18} {'FILL':>6} {'WIDTH':>7}  FLAGS")
    print("-" * 78)
    bad = 0
    for r in results:
        m = r["metrics"]
        fill = (m.get("contentWidth", 0) / m["mainWidth"]) if m.get("mainWidth") else 0
        print(f"{r['name']:18} {fill:>5.0%} {m.get('contentWidth', 0):>7}  {'; '.join(r['flags']) or 'ok'}")
        if r["flags"]:
            bad += 1
    print(f"\n{bad} of {len(results)} screens flagged. Screenshots in {out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
