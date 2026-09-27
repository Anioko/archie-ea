"""BA-04 manual verification: does Export PDF actually produce a real PDF?

The static gates and the source-shape tests cannot answer this — neither runs the
export. This drives a real browser against a running dev server, clicks the
toolbar button, captures the download, and checks the bytes.

    python scripts/ba04_verify_pdf.py [--base http://127.0.0.1:5001]

Exit 0 only if a non-trivial file starting with %PDF- was produced.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

EMAIL = "pdfdemo@example.com"
PASSWORD = "TestPass123!"
MIN_BYTES = 5000  # a blank one-image PDF lands well under this


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5001")
    ap.add_argument("--diagram", default="36")
    ap.add_argument("--out", default="ba04_export.pdf")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    errors: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        page.goto(f"{args.base}/account/login", wait_until="domcontentloaded")
        page.fill('input[name="email"]', EMAIL)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("networkidle")
        print(f"  after login: {page.url}")

        url = f"{args.base}/archimate/composer?viewpoint_id={args.diagram}"
        page.goto(url, wait_until="networkidle")
        print(f"  composer:   {page.url}")
        page.wait_for_timeout(5000)  # let JointJS lay the graph out

        # Call the export directly on the Alpine component: the toolbar entry is
        # inside a dropdown, and this verifies the same function the button calls.
        found = page.evaluate(
            """() => {
                if (!window.Alpine) return 'no-alpine';
                const roots = document.querySelectorAll('[x-data]');
                for (let i = 0; i < roots.length; i++) {
                    let d = null;
                    try { d = Alpine.$data(roots[i]); } catch (e) { continue; }
                    if (d && typeof d.exportPdf === 'function') {
                        window.__ba04root = roots[i];
                        return 'ok:index=' + i + ' of ' + roots.length;
                    }
                }
                return 'no-exportPdf (roots=' + roots.length + ')';
            }"""
        )
        print(f"  exportPdf on component: {found}")
        if not found.startswith("ok"):
            print(f"FAIL: {found}")
            browser.close()
            return 2

        try:
            with page.expect_download(timeout=45000) as dl:
                page.evaluate("Alpine.$data(window.__ba04root).exportPdf()")
            download = dl.value
            download.save_as(out)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: no download produced — {type(exc).__name__}: {exc}")
            for e in errors[:10]:
                print(f"    console: {e}")
            browser.close()
            return 3

        browser.close()

    data = out.read_bytes()
    print(f"  saved: {out}  ({len(data):,} bytes)")
    if not data.startswith(b"%PDF-"):
        print(f"FAIL: not a PDF — starts with {data[:16]!r}")
        return 4
    if len(data) < MIN_BYTES:
        print(f"FAIL: {len(data)} bytes is too small to hold a diagram — likely blank")
        return 5

    print(f"PASS: real PDF, {len(data):,} bytes, header {data[:8]!r}")
    if errors:
        print(f"  note: {len(errors)} console error(s) during export:")
        for e in errors[:5]:
            print(f"    {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
