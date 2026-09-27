#!/usr/bin/env python
"""Photograph the product, so the README shows it instead of describing it.

Archie is a visual product -- capability maps, ArchiMate models, roadmaps, ARB
queues -- and until 31 Aug 2026 the repository contained ZERO images. Someone
evaluating "an open-source LeanIX alternative" decides in a few seconds, from
pictures, and there were none to look at. That is a conversion problem no amount
of SEO fixes, because the traffic that already arrives has nothing to judge.

This drives a real browser against a real seeded database, so the images are the
product as it actually renders rather than a mock-up that will drift. Re-running
it after a UI change refreshes the shop window, and a screenshot that comes back
ugly is a UX finding rather than a marketing inconvenience -- which is the more
useful half of this script.

    # 1. a demo database with data the UI actually reads
    createdb archie_demo
    DATABASE_URL=postgresql://.../archie_demo flask --app manage init-db
    DATABASE_URL=postgresql://.../archie_demo flask --app manage reconcile-schema

    # 2. start the app against it, then:
    python scripts/capture_screenshots.py --base http://127.0.0.1:5100 \
        --email demo@archie.local --password 'DemoPassw0rd!23'

Images land in docs/screenshots/ at 1440x900, which is the width the README
renders at on GitHub without the reader zooming.
"""
from __future__ import annotations

import argparse
import os
import sys

# The surfaces that say what this product IS. Ordered as a story: what the
# estate looks like, what the business does, what runs it, how change is
# governed. Anything that renders empty is reported rather than shipped -- an
# empty screenshot is worse than no screenshot.
PAGES = [
    ("dashboard", "/dashboard/overview", "Executive dashboard"),
    ("capability-map", "/capability-map/", "Business capability map"),
    ("applications", "/applications/", "Application portfolio"),
    ("arb", "/arb/", "Architecture Review Board"),
    ("value-streams", "/value-streams/", "Value streams"),
    ("roadmap", "/capability-map/roadmap", "Capability roadmap"),
    ("archimate", "/architecture/", "ArchiMate model"),
]

VIEWPORT = {"width": 1440, "height": 900}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5100")
    parser.add_argument("--email", default="demo@archie.local")
    parser.add_argument("--password", default="DemoPassw0rd!23")
    parser.add_argument("--out", default=os.path.join("docs", "screenshots"))
    parser.add_argument("--full-page", action="store_true",
                        help="capture the whole scroll height, not just the fold")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed: pip install playwright && "
              "python -m playwright install chromium", file=sys.stderr)
        return 2

    os.makedirs(args.out, exist_ok=True)
    captured, empty, failed = [], [], []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=2)

        page.goto(args.base + "/account/login", wait_until="domcontentloaded",
                  timeout=60000)
        page.fill("#email", args.email)
        page.fill("#password", args.password)
        try:
            page.click("#submit", force=True, no_wait_after=True)
        except TypeError:
            page.locator("#submit").dispatch_event("click")
        page.wait_for_url(lambda url: "/account/login" not in url, timeout=60000)
        print("signed in as", args.email)

        for slug, path, title in PAGES:
            try:
                response = page.goto(args.base + path,
                                     wait_until="networkidle", timeout=60000)
                status = response.status if response else 0
                if status >= 400:
                    failed.append("%s -> HTTP %d" % (path, status))
                    continue
                page.wait_for_timeout(1200)  # let charts and icons settle

                # An empty screen is a finding, not a picture. Report it rather
                # than shipping a shop window full of empty states.
                text = page.evaluate("() => document.body.innerText") or ""
                if len(text.strip()) < 200:
                    empty.append("%s (only %d chars of text)" % (path, len(text.strip())))

                target = os.path.join(args.out, slug + ".png")
                page.screenshot(path=target, full_page=args.full_page)
                captured.append((slug, title, path))
                print("  captured %-16s %s" % (slug, path))
            except Exception as exc:
                failed.append("%s -> %s: %s" % (path, type(exc).__name__, str(exc)[:80]))

        browser.close()

    print()
    print("captured %d, empty %d, failed %d" % (len(captured), len(empty), len(failed)))
    for line in empty:
        print("  LOOKS EMPTY: " + line)
    for line in failed:
        print("  FAILED:      " + line)
    return 0 if captured else 1


if __name__ == "__main__":
    sys.exit(main())
