#!/usr/bin/env python
"""Level 10 archetype walkthrough (docs/TESTING_STANDARD.md).

Levels 0-8 ask "does this break?". Level 9 asks "can this person do their
job?". This is Level 10: "is the journey worth completing?" -- the questions a
gate cannot answer, run against a real browser rather than reasoned about.

It drives a real Chromium at a FIXED 1440x900 viewport, signed in as a
NON-ADMIN user per archetype, and per the standard's own rules it:

  * measures geometry instead of photographing it (rule 3) -- a screenshot
    grows to fit its content and therefore cannot show dead space or overflow;
  * runs as a normal Architect role, never an admin (rule 4) -- an admin
    session satisfies every require_roles guard on the way through and hides
    the authorisation defects this level exists to find;
  * checks DISCOVERABILITY, not just reachability: a page the archetype can
    only reach by typing a URL is broken for real users however green the
    gates are. That is exactly what this harness found on its first run --
    the CTO was authorised to classify technology on the radar
    (/technology/radar/classify names "cto" in its own require_roles list) and
    no CTO sidebar zone linked the page.

It needs a running server and a seeded tenant, so it is not a verify.py gate.
Run it before a deploy, against the deployment you are about to ship:

    python scripts/walkthrough_archetypes.py            # default http://127.0.0.1:5001

Seed data expectations are in the PERSONAS table below; a step whose data is
absent reports the absence rather than passing quietly.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("WALKTHROUGH_BASE_URL", "http://127.0.0.1:5001")
PASSWORD = os.environ.get("WALKTHROUGH_PASSWORD", "Walk!2026")
VIEWPORT = {"width": 1440, "height": 900}

findings = []


def note(persona, step, verdict, evidence):
    findings.append({"persona": persona, "step": step, "verdict": verdict,
                     "evidence": evidence})
    print("%-20s %-46s %-14s %s" % (persona, step, verdict, evidence), flush=True)


def sign_in(page, email):
    page.goto(BASE + "/account/login", wait_until="domcontentloaded")
    page.fill("input[name='email']", email)
    page.fill("input[name='password']", PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_load_state("domcontentloaded")
    return "/login" not in page.url


def geometry(page):
    """Content height vs viewport, and horizontal overflow. Rule 3."""
    return page.evaluate("""() => {
        const d = document.documentElement, b = document.body;
        return {
            scrollH: Math.max(d.scrollHeight, b.scrollHeight),
            clientH: d.clientHeight,
            scrollW: Math.max(d.scrollWidth, b.scrollWidth),
            clientW: d.clientWidth,
        };
    }""")


def check_page(page, persona, label, path, must_contain=()):
    errors = []
    handler = lambda m: errors.append(m.text) if m.type == "error" else None
    page.on("console", handler)
    page.on("pageerror", lambda e: errors.append("pageerror: %s" % e))
    resp = page.goto(BASE + path, wait_until="networkidle")
    status = resp.status if resp else 0
    body = page.content()
    geo = geometry(page)

    problems = []
    if status >= 400:
        problems.append("HTTP %d" % status)
    for token in must_contain:
        if token not in body:
            problems.append("missing %r" % token)
    if geo["scrollW"] > geo["clientW"] + 1:
        problems.append("horizontal overflow %dpx > %dpx" % (geo["scrollW"], geo["clientW"]))
    if geo["scrollH"] > 12000:
        problems.append("page is %dpx tall" % geo["scrollH"])
    if errors:
        problems.append("console: %s" % "; ".join(errors[:3]))

    page.remove_listener("console", handler)
    verdict = "WORKS WELL" if not problems else "BROKEN" if status >= 400 else "WORKS BUT POOR"
    note(persona, label, verdict, "; ".join(problems) or "HTTP %d, %dpx tall" % (status, geo["scrollH"]))
    return not problems


def discoverable(page, persona, needle):
    """Rule: could the archetype find this without reading the source?"""
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    hit = any(needle in (h or "") for h in hrefs)
    note(persona, "discoverable: %s" % needle, "WORKS WELL" if hit else "WORKS BUT POOR",
         "%d nav links, %s" % (len(hrefs), "linked" if hit else "NOT linked from this page"))
    return hit


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for persona, email, steps in [
        ("cto", "cto@walkthrough.example.com", "radar"),
        ("enterprise_architect", "ea@walkthrough.example.com", "capabilities"),
        ("portfolio_manager", "pm@walkthrough.example.com", "rationalization"),
        ("arb_member", "arb@walkthrough.example.com", "arb"),
    ]:
        ctx = browser.new_context(viewport=VIEWPORT)
        page = ctx.new_page()
        if not sign_in(page, email):
            note(persona, "sign in", "BROKEN", "still on the login page")
            ctx.close()
            continue
        note(persona, "sign in", "WORKS WELL", "landed on %s" % page.url.replace(BASE, ""))

        check_page(page, persona, "landing page", "/")
        if steps == "radar":
            discoverable(page, persona, "/technology/radar")
            check_page(page, persona, "technology radar", "/technology/radar/",
                       must_contain=("Kafka 3.x",))
        elif steps == "capabilities":
            discoverable(page, persona, "capability")
            check_page(page, persona, "capability map", "/capability-map/")
        elif steps == "rationalization":
            discoverable(page, persona, "rationalization")
            check_page(page, persona, "rationalization dashboard", "/applications/rationalization")
            check_page(page, persona, "planning for one app",
                       "/applications/rationalization/planning/1")
        elif steps == "arb":
            discoverable(page, persona, "/arb")
            check_page(page, persona, "ARB dashboard", "/arb/")
            check_page(page, persona, "ARB review queue", "/arb/reviews")
        ctx.close()
    browser.close()

json.dump(findings, open("walkthrough_report.json", "w"), indent=2)
bad = [f for f in findings if f["verdict"] != "WORKS WELL"]
print("\n%d step(s) not WORKS WELL out of %d" % (len(bad), len(findings)))
sys.exit(1 if bad else 0)
