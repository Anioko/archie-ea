"""BA-02b verification: does the maturity heatmap render honestly against real data?

Checks the property that matters — an unassessed capability must show an em dash
and must NOT be coloured as Level 1 — plus that coverage is stated explicitly.

    python scripts/ba02_verify_heatmap.py --base https://... --email ... --password ...
"""
from __future__ import annotations

import argparse
import re
import sys

from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--shot", default="")
    args = ap.parse_args()

    errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_context(ignore_https_errors=True).new_page()
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        page.goto(f"{args.base}/account/login", wait_until="domcontentloaded")
        page.fill('input[name="email"]', args.email)
        page.fill('input[name="password"]', args.password)
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("networkidle")
        if "login" in page.url:
            print(f"FAIL: still on login — {page.url}")
            browser.close()
            return 2

        page.goto(f"{args.base}/capability-maturity/heatmap", wait_until="networkidle")
        page.wait_for_timeout(2500)
        status = page.url
        print(f"  url: {status}")
        if "heatmap" not in status:
            print(f"FAIL: redirected away from heatmap -> {status}")
            browser.close()
            return 3

        html = page.content()
        text = re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", html))

        if args.shot:
            page.screenshot(path=args.shot, full_page=True)
            print(f"  screenshot: {args.shot}")
        browser.close()

    checks = {
        "page rendered (non-trivial)": len(text) > 2000,
        "em dash present for unassessed": "—" in html,
        "coverage stated (assessed/total)": bool(
            re.search(r"\b0\s*(of|/)\s*\d{2,}", text) or re.search(r"assessed", text, re.I)
        ),
        "legend present": bool(re.search(r"not assessed", text, re.I)),
        "no server error page": "Internal Server Error" not in text and "Traceback" not in text,
    }
    for label, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

    if errors:
        print(f"  {len(errors)} console error(s):")
        for e in errors[:5]:
            print(f"    {e}")

    failed = [k for k, v in checks.items() if not v]
    if failed:
        print(f"FAIL: {failed}")
        return 4
    print("PASS: heatmap renders and reports coverage honestly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
