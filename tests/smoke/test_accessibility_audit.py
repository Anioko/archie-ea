"""WCAG 2.1 A/AA audit with axe-core, on the pages each archetype actually uses.

This engagement already closed 939 unlabelled form controls, which was the single
largest defect class in the product. That work was necessary and it is not
sufficient: "every input has a name" is one success criterion out of dozens, and
an EN 301 549 auditor tests the rest too - contrast, landmarks, heading order,
ARIA validity, focus order, link purpose.

axe-core is what those auditors run. It detects roughly a third of WCAG issues
automatically, so a clean result is a floor rather than a certificate - it means
nothing mechanical is wrong, not that the product is usable with a screen reader.
Manual testing is still owed.

Gated as a ratchet against an accepted baseline, like the bandit and dependency
gates, for the same reason: a check that fails on day one gets disabled on day
two. Serious violations fail the build immediately; everything else may only
decrease.
"""

import json
import os

import pytest

from .conftest import PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.journey]

axe_module = pytest.importorskip(
    "axe_playwright_python.sync_playwright",
    reason="axe-playwright-python not installed - accessibility audit skipped",
)

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "a11y_baseline.json")

# WCAG 2.1 Level A and AA - what EN 301 549 references for public-sector and
# most enterprise procurement.
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]

# One representative page per archetype, signed in as that archetype.
#
# NOTE FOR THE FIRST RUN AFTER /ai-chat WAS ADDED: that page had no entry in
# a11y_baseline.json, because it was in no smoke test at all until now. The
# first run will therefore FAIL with its real violations — that failure is the
# point, and is what proves the gate now sees the page. Record them with:
#
#     SMOKE_A11Y_UPDATE_BASELINE=1 pytest tests/smoke/test_accessibility_audit.py
#
# Then read the diff. Every accepted rule under "/ai-chat" is a known defect
# scheduled for removal in the client rebuild (see
# docs/superpowers/specs/2026-08-07-ai-chat-rebuild-design.md §9), NOT an
# accepted state. Expect at minimum three `select-name` criticals: the domain,
# model and template selects carry no label.
AUDIT = [
    ("procurement", "/procurement/contracts"),
    ("procurement", "/procurement/contracts/new"),
    ("procurement", "/procurement/compliance"),
    ("application_manager", "/my-applications/"),
    ("portfolio_manager", "/applications/"),
    ("business_architect", "/capability-map/"),
    ("cto", "/dashboard/overview"),
    ("enterprise_architect", "/ai-chat"),
]

# An impact level at which a violation is not negotiable: these block a user
# rather than inconvenience them.
BLOCKING = {"critical", "serious"}


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    try:
        page.click("#submit", force=True, no_wait_after=True)
    except TypeError:
        page.locator("#submit").dispatch_event("click")
    try:
        page.wait_for_url(lambda u: "/account/login" not in u, timeout=PAGE_TIMEOUT)
    except Exception:
        pass
    assert "/account/login" not in page.url, "could not sign in as %s" % email


def _load_baseline():
    if not os.path.exists(BASELINE):
        return {}
    with open(BASELINE, encoding="utf-8") as fh:
        return json.load(fh).get("accepted", {})


@pytest.fixture(scope="module")
def audited(browser, live_server, seeded):
    """Run axe once per page and return {path: {rule_id: (impact, count)}}."""
    Axe = axe_module.Axe
    axe = Axe()
    results = {}
    for archetype, path in AUDIT:
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.set_default_timeout(PAGE_TIMEOUT)
        ctx.set_default_navigation_timeout(PAGE_TIMEOUT)
        page = ctx.new_page()
        try:
            _login(page, live_server, seeded["emails"][archetype])
            page.goto(live_server + path, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
            page.wait_for_timeout(2000)
            try:
                # The first-run overlay covers the viewport and would be audited
                # instead of the page underneath it.
                page.eval_on_selector_all(
                    "[x-show='showOnboarding']", "els => els.forEach(e => e.remove())")
            except Exception:
                pass
            report = axe.run(page, options={"runOnly": {"type": "tag", "values": TAGS}})
            data = report.response if hasattr(report, "response") else report
            results[path] = {
                v["id"]: (v.get("impact") or "unknown", len(v.get("nodes") or []))
                for v in data.get("violations", [])
            }
        finally:
            ctx.close()
    return results


def test_no_new_serious_or_critical_violations(audited):
    """Serious and critical violations may not increase.

    A ratchet rather than an absolute gate, for the same reason every other gate
    here is one: the product carries known contrast failures today, and a check
    that can never go green is a check somebody deletes. New violations fail
    immediately; the existing count may only fall.

    What is in the baseline is real, unfixed WCAG failure - an EN 301 549 audit
    will report every entry. Shrinking it is the point.
    """
    baseline = _load_baseline()
    regressions = []
    for path, violations in sorted(audited.items()):
        known = baseline.get(path, {})
        for rule, (impact, count) in sorted(violations.items()):
            if impact not in BLOCKING:
                continue
            was = known.get(rule)
            if was is None:
                regressions.append("%s: NEW %s (%s, %d element%s)"
                                   % (path, rule, impact, count, "" if count == 1 else "s"))
            elif count > was:
                regressions.append("%s: %s worsened %d -> %d elements"
                                   % (path, rule, was, count))
    assert not regressions, (
        "%d new or worsened serious/critical WCAG 2.1 AA violation(s):\n  %s\n\n"
        "These block a user rather than inconvenience them, and are the first "
        "thing an EN 301 549 audit reports."
        % (len(regressions), "\n  ".join(regressions)))


def test_all_violations_do_not_increase(audited):
    """The same ratchet across every impact level."""
    baseline = _load_baseline()
    regressions = []
    for path, violations in sorted(audited.items()):
        known = baseline.get(path, {})
        for rule, (impact, count) in sorted(violations.items()):
            was = known.get(rule)
            if was is None:
                regressions.append("%s: NEW %s (%s, %d)" % (path, rule, impact, count))
            elif count > was:
                regressions.append("%s: %s worsened %d -> %d" % (path, rule, was, count))
    assert not regressions, (
        "%d accessibility regression(s):\n  %s\n\n"
        "Fix them, or accept deliberately by regenerating "
        "tests/smoke/a11y_baseline.json and saying why."
        % (len(regressions), "\n  ".join(regressions)))


def test_the_audit_actually_ran(audited):
    """A crashed audit reports zero violations, which looks like success."""
    assert audited, "no pages were audited"
    assert len(audited) == len({p for _a, p in AUDIT}), (
        "expected %d pages, audited %d - a page failed to load and its result is "
        "missing, which would read as a clean pass"
        % (len({p for _a, p in AUDIT}), len(audited)))


def test_write_baseline_when_asked(audited):
    """Regenerate the accepted set:  SMOKE_A11Y_UPDATE_BASELINE=1 pytest ...

    Deliberately a test rather than a script: the audit needs a live server, a
    seeded database and a browser, all of which the fixtures already stand up.
    """
    if os.environ.get("SMOKE_A11Y_UPDATE_BASELINE") != "1":
        # This is a maintenance utility, not a release assertion. Count it as
        # a clean no-op instead of making every qualification run carry a skip.
        return
    accepted = {p: {r: c for r, (_i, c) in v.items()} for p, v in audited.items()}
    with open(BASELINE, "w", encoding="utf-8") as fh:
        json.dump({
            "_comment": "Accepted axe-core violations per page. Every entry is a "
                        "real WCAG 2.1 AA failure that has not been fixed yet, not "
                        "a statement that the page is accessible. Regenerate with "
                        "SMOKE_A11Y_UPDATE_BASELINE=1.",
            "accepted": accepted,
        }, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("a11y baseline written: %d page(s), %d rule instance(s)"
          % (len(accepted), sum(len(v) for v in accepted.values())))
