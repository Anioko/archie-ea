"""Is the page telling the user it is broken while returning HTTP 200?

Written 31 Aug 2026, after the owner opened /capability-maturity/search and got
a page that rendered perfectly, returned 200, and carried a banner reading

    "This page could not load its data ... Error searching capabilities.
     Please try again."

The cause was raw SQL selecting `capability_type`, a column that does not exist
on the table. The reason nobody caught it is the whole point of this file: an
error banner is served with HTTP 200. An audit of 21,978 page loads across 1,221
routes passed that page, because it only ever looked at the status line.

Every gate in scripts/verify.py reads SOURCE, so none of them can see a runtime
query failure. The browser suite next door checks rendering, overflow and
naming, so none of them can see a page that renders correctly and says it is
broken. This gate asks the one remaining question, and it asks it about the
SYMPTOM rather than any one cause -- bad SQL, a dead API, a missing column, a
failed fetch and a 500 swallowed by an except handler all surface here as the
same finding.

What counts as a finding
------------------------
    flashed error/danger    routes flash(..., "error"); components/toast-container.html
                            turns those into a Platform.toast error, which renders as
                            role="alert" + aria-live="assertive" inside
                            #platform-toast-container. On a GET of a landing page a
                            flashed error is by definition not user input being
                            rejected -- nothing was submitted.
    load_error banner       partials/_data_load_error.html, included by
                            layouts/admin_base.html on every page: "This page could
                            not load its data".
    broken copy in an alert copy such as "could not load", "please try again",
                            "something went wrong", "failed to load" -- derived by
                            grepping the templates and the flash() call sites rather
                            than invented; see PHRASES.

What is deliberately NOT a finding, because getting this wrong makes the gate
useless and it gets switched off:

    empty states            "No capabilities found" is a WORKING page with no data.
                            No phrase in PHRASES matches an empty state, and that is
                            asserted by test_empty_state_copy_is_not_a_finding below.
    validation messages     these appear only after a bad submit. This suite only
                            ever performs GETs, so a form error cannot be reached.
    hidden / dismissed      an alert container a template renders collapsed (x-show
                            false, display:none, aria-hidden, a zero box) is not
                            something the user is being told.

Ratcheted per archetype against error_banner_baseline.json rather than asserted
at zero, for the same reason the other ratchets exist: the debt is real, and a
gate that fails red on day one gets disabled instead of paid down. Capture the
baseline by measurement, never by hand:

    SMOKE_WRITE_ERROR_BANNER_BASELINE=1 pytest tests/smoke/test_no_error_banners.py
"""

import json
import os

import pytest

from .conftest import ARCHETYPES, PAGE_TIMEOUT, PASSWORD
from .test_archetype_journeys import JOURNEY

pytestmark = [pytest.mark.smoke, pytest.mark.journey]

BASELINE_PATH = os.path.join(os.path.dirname(__file__), "error_banner_baseline.json")

# Copy that means "this is broken", lowercased. Every entry was taken from a
# real string in app/templates or a real flash(..., "error") call site; none is
# a guess, and none of them can match an empty state.
PHRASES = [
    "could not load",
    "could not be loaded",
    "could not be read",
    "could not be run",
    "could not be completed",
    "could not be built",
    "could not be verified",
    "could not be updated",
    "failed to load",
    "unable to load",
    "please try again",
    "something went wrong",
    "an error occurred",
    "error loading",
    "error searching",
    "error retrieving",
    "error generating",
]

DETECT = r"""(phrases) => {
  const seen = [];
  const textOf = (el) => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();

  const visible = (el) => {
    // A container the template renders collapsed is not something the user is
    // being told. Opacity is NOT part of this: toasts animate in from opacity-0
    // and would otherwise be missed for their first 300ms.
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    if (el.hasAttribute('hidden') || el.getAttribute('aria-hidden') === 'true') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  const add = (kind, el, text) => {
    const t = (text || '').slice(0, 160);
    if (!t) return;
    if (seen.some(f => f.text === t)) return;   // one banner, not one per nesting level
    seen.push({kind: kind, text: t});
  };

  // 1. Flashed error/danger. toast-container.html routes flash categories
  //    error/danger to Platform.toast.error, the only toast rendered with
  //    aria-live="assertive" and a destructive border.
  for (const el of document.querySelectorAll('#platform-toast-container [role="alert"]')) {
    const isError = el.getAttribute('aria-live') === 'assertive'
                    || String(el.className).indexOf('border-destructive') !== -1;
    if (isError) add('flashed-error', el, textOf(el));
  }

  // 2. Alert regions -- the load_error banner and anything else the page renders
  //    as an alert -- whose copy says the page is broken.
  for (const el of document.querySelectorAll('[role="alert"], [role="alertdialog"]')) {
    if (el.closest('#platform-toast-container')) continue;   // counted above
    if (!visible(el)) continue;
    const text = textOf(el).toLowerCase();
    if (phrases.some(p => text.indexOf(p) !== -1)) add('alert-banner', el, textOf(el));
  }

  return seen;
}"""


def _load_baseline():
    try:
        with open(BASELINE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _login(page, base, email):
    """Sign in the way a user does. Mirrors tests/smoke/test_archetype_journeys.py."""
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    try:
        page.click("#submit", force=True, no_wait_after=True)
    except TypeError:                     # newer Playwright dropped the kwarg
        page.locator("#submit").dispatch_event("click")
    try:
        page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)
    except Exception:
        pass
    page.wait_for_timeout(800)
    assert "/account/login" not in page.url, (
        "could not sign in as %s - still on the login page." % email)


def _scan(page, base, path):
    """GET the page as a user would, and return what it is telling them."""
    try:
        response = page.goto(base + path, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    except Exception as exc:
        # Not a page: a download, an asset, a redirect the browser aborts. There
        # is nothing for a user to read, so there is nothing for this gate to
        # judge -- and one such path must not take the whole scan down with it,
        # which is exactly what /favicon.ico did to the first full sweep.
        return None, [], str(exc)[:120]
    # Long enough for the flash-to-toast script (DOMContentLoaded) and the first
    # round of fetches to land, short enough that a 6s error toast is still up.
    page.wait_for_timeout(2500)
    try:
        page.eval_on_selector_all(
            "[x-show='showOnboarding']", "els => els.forEach(e => e.remove())")
    except Exception:
        pass
    status = response.status if response else 0
    return status, page.evaluate(DETECT, PHRASES), None


@pytest.mark.parametrize("archetype", ARCHETYPES)
def test_no_page_says_it_is_broken_on_a_200(archetype, live_server, seeded, browser):
    """Every page this persona is sent to, checked for a 200 that reports failure.

    The page list is JOURNEY from test_archetype_journeys, so coverage follows
    the personas' real surfaces rather than one landing page, and a persona
    gaining a screen gains it here for free.
    """
    base = live_server
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.set_default_timeout(PAGE_TIMEOUT)
    ctx.set_default_navigation_timeout(PAGE_TIMEOUT)
    page = ctx.new_page()
    findings = []
    try:
        _login(page, base, seeded["emails"][archetype])
        # Ad-hoc probing hook. A gate nobody has watched go red is just a number
        # (docs/TESTING_STANDARD.md rule 7), and the defect that prompted this
        # file lives on a page no persona's JOURNEY lists. Point the detector at
        # any comma-separated path list to reproduce a report:
        #   SMOKE_ERROR_BANNER_PATHS=/capability-maturity/search pytest ...
        extra = [p for p in os.environ.get("SMOKE_ERROR_BANNER_PATHS", "").split(",") if p]
        for path in JOURNEY[archetype] + extra:
            status, found, unreachable = _scan(page, base, path)
            # A 4xx/5xx is already caught by test_archetype_journeys; this gate
            # exists for the page that claims success and reports failure.
            if unreachable is not None or status >= 400:
                continue
            for item in found:
                findings.append("%s [%s] %s" % (path, item["kind"], item["text"]))
    finally:
        ctx.close()

    if os.environ.get("SMOKE_WRITE_ERROR_BANNER_BASELINE") == "1":
        # Capture the current truth so the ratchet starts from a measurement
        # rather than a guess. Never set in CI -- that would make the gate
        # rewrite its own baseline and pass forever.
        current = _load_baseline()
        current[archetype] = len(findings)
        with open(BASELINE_PATH, "w", encoding="utf-8") as fh:
            json.dump(current, fh, indent=2, sort_keys=True)
            fh.write(chr(10))
        print("\n[error-banner] %s: %d finding(s)" % (archetype, len(findings)))
        for item in findings:
            print("  " + item)
        pytest.skip("baseline captured for %s: %d" % (archetype, len(findings)))

    allowed = _load_baseline().get(archetype, 0)
    assert len(findings) <= allowed, (
        "%s: %d page(s) return HTTP 200 while telling the user they are broken "
        "(baseline %d).\nThis is what the user is reading:\n  %s"
        % (archetype, len(findings), allowed, "\n  ".join(findings[:12])))


KNOWN_BAD_PAGE = """
<!-- partials/_data_load_error.html, verbatim, as the view that started this
     renders it: except -> flash(..., "error") + load_error -> banner. -->
<div class="relative w-full rounded-lg border border-destructive/50 bg-destructive/10 p-4"
     role="alert">
  <div class="flex items-start gap-3">
    <div class="flex-1 text-sm">
      <p class="font-semibold">This page could not load its data</p>
      <p class="mt-1">The capability search could not be run. Reload to try again.</p>
    </div>
  </div>
</div>

<!-- What core/04-toast.js builds for a flashed error category. -->
<div id="platform-toast-container" class="fixed top-4 right-4">
  <div role="alert" aria-live="assertive" aria-atomic="true"
       class="flex items-start gap-3 rounded-lg border p-4 border-destructive">
    Error searching capabilities. Please try again.
  </div>
</div>

<!-- A legitimate empty state on a WORKING page, and an alert the template
     renders collapsed. Neither is the user being told anything is broken. -->
<div class="p-8 text-center">No capabilities found</div>
<div role="alert" style="display:none">Something went wrong</div>
"""


def test_the_detector_fires_on_a_known_bad_page(browser):
    """A gate nobody has watched go red is just a number.

    docs/TESTING_STANDARD.md rule 7 asks for the defect to be reintroduced and
    the gate seen failing. The original defect -- raw SQL selecting a column
    that does not exist -- has since been repaired in the route, and app/ is not
    this test's to break, so the proof is run against the exact markup that
    defect produced: the real _data_load_error.html banner and the real toast
    element core/04-toast.js builds for a flashed error, on one page alongside a
    genuine empty state and a collapsed alert.
    """
    page = browser.new_page()
    try:
        page.set_content(KNOWN_BAD_PAGE)
        found = page.evaluate(DETECT, PHRASES)
    finally:
        page.close()

    kinds = sorted(f["kind"] for f in found)
    texts = " | ".join(f["text"] for f in found)
    assert kinds == ["alert-banner", "flashed-error"], (
        "expected exactly the banner and the flashed error, got %r: %s" % (kinds, texts))
    assert "could not load its data" in texts
    assert "Error searching capabilities" in texts
    # The two exclusions the gate's usefulness depends on.
    assert "No capabilities found" not in texts, "an empty state was reported as a failure"
    assert "Something went wrong" not in texts, "a collapsed alert was reported as visible"


def test_empty_state_copy_is_not_a_finding():
    """The distinction the whole gate rests on, pinned as a test.

    "No capabilities found" is a page that WORKS and has no data. If a phrase
    ever starts matching an empty state this gate becomes noise and the next
    person turns it off -- so the exclusion is asserted, not assumed.
    """
    empty_states = [
        "No capabilities found",
        "No applications yet. Create your first application to get started.",
        "0 results",
        "Nothing to show for the selected filters.",
        "No data available",
        "No results found. Try a different search term.",
        "This organisation has no contracts.",
    ]
    for copy in empty_states:
        lowered = copy.lower()
        matched = [p for p in PHRASES if p in lowered]
        assert not matched, "empty-state copy %r matched error phrase(s) %r" % (copy, matched)
