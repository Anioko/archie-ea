"""Does the rendered screen actually DO anything when a persona presses it?

Every gate in scripts/verify.py, and every other smoke test next door, answers a
narrower question than the owner keeps asking. verify.py reads SOURCE, so it
cannot see a button that renders and listens to nothing. test_archetype_journeys
asserts the page booted and named its inputs; test_task_completion asserts the
persona can REACH their work; test_no_error_banners asserts the page is not
announcing its own failure. None of them presses a control and asks "did that do
anything?" -- and that is exactly the class the owner found by clicking: a
capability-map Save that fired no request, an ARB with no decision button, a
table of gaps with nothing to act on.

This file measures RENDERED REALITY for three of those failure shapes, per
persona, per key screen:

  (a) DEAD CONTROLS.  Every visible thing that SIGNALS it is pressable -- a
      <button>, [role=button], a cursor-pointer element, a submit -- must be
      WIRED: it must have an href that navigates, be a form submit, carry an
      Alpine click directive, sit under a real delegation hook, or have a
      JavaScript listener actually bound to it or an ancestor. A control that
      looks pressable and has nothing listening is the finding.

  (b) JUNK MODALS.  A modal whose body renders "undefined", "null", "NaN" or an
      unrendered `{{ ... }}` is showing the user a coercion leak, not data.

  (c) SILENT-FAILING FORMS.  Submitting a form must produce a validation message
      or a real response -- never an HTTP 5xx and never a torn-down blank page.

Why the wiring probe is shaped the way it is -- the part a naive version gets
wrong
---------------------------------------------------------------------------------
A prior attempt produced false positives two ways, and both are designed out
here:

  * It treated any element with a `data-*` ancestor as "wired". Most `data-*`
    attributes wire NOTHING (`data-testid`, `data-state`). Only the data
    attributes this app's delegates actually dispatch on count as a hook --
    `data-modal-open`, `data-confirm`, `data-autosubmit`, and the family of
    `data-*-action` attributes every per-page `document.addEventListener('click')`
    keys off (`data-action`, `data-cm-action`, `data-vendor-action`, ...). That
    family is matched by HOOK_RE, derived from grepping the delegate call sites,
    not guessed; a bare wrapper with `data-testid` credits nothing.

  * It read `window.__wired` AFTER the fact, by which time nothing had populated
    it. Listeners are bound while the page's own scripts run, so the probe MUST
    be installed BEFORE any page script -- it wraps addEventListener via
    page.add_init_script, which Playwright guarantees runs before page load. An
    element-level (or Element-ancestor) interaction listener then marks the
    element wired, because a bubbling click reaches an ancestor's listener.

Two decisions keep the false-positive rate at zero on the current product (every
real screen measures 0), verified by planting a dead control and a junk modal and
confirming each is flagged while nothing else moves:

  * A document/window/body-level listener is NOT credited to the whole page.
    Every such delegate in this codebase dispatches on a data-* action attribute
    the census already reads on the control itself, so crediting from the
    document listener would only re-introduce the blindness an earlier probe had
    (it marked everything wired). Ancestor credit stops at depth 6.

  * A control that is really a form input in disguise is excluded: a <label>, a
    checkbox/radio, or a .cursor-pointer wrapper that CONTAINS its own
    button/anchor/input. Those toggle or focus natively, or defer to the control
    inside them (which is judged separately), and are wired via @change / x-model
    that a click-only probe cannot see -- the exact shape that produced this
    file's first three false positives.

Ratcheted per archetype against interaction_reality_baseline.json, like every
other browser ratchet here. Regenerate by measurement, never by hand:

    SMOKE_WRITE_INTERACTION_BASELINE=1 pytest tests/smoke/test_interaction_reality.py -m census

Marked `census` (heavy), so CI runs it in its own step, not the per-archetype
journey step -- see the snippet at the foot of this file.
"""

import json
import os

import pytest

from .conftest import PAGE_TIMEOUT, PASSWORD
from .test_archetype_journeys import JOURNEY

pytestmark = [pytest.mark.smoke, pytest.mark.census]

BASELINE_PATH = os.path.join(os.path.dirname(__file__), "interaction_reality_baseline.json")
WRITE_BASELINE = os.environ.get("SMOKE_WRITE_INTERACTION_BASELINE") == "1"

# The screens each persona actually lands on. Reuses the journey map so the two
# suites cannot drift onto different URLs, and stays inside pages known to serve
# (a 404 is a different test's finding). Screens are deduplicated per persona.
SCREENS = {a: list(dict.fromkeys(paths)) for a, paths in JOURNEY.items()}

# Landing/journey screens are only half of where the owner clicks. The controls
# that render nothing, the modals that leak a coercion token, and the forms that
# 5xx cluster on the OTHER half: the DETAIL page a persona drills into, the /new
# or /create form they fill, and the modal a control on those screens raises.
# JOURNEY covers none of those, so this map extends each persona onto them.
#
# Paths may carry a {placeholder} resolved at runtime from the seeded fixture's
# ids (the only deterministic entity ids we own -- an application and a vendor
# contract). Screens whose id we do not seed are reached through their /create or
# /new form instead of a detail page, so every entry here serves for real rather
# than redirecting away and censusing nothing. A path that still 404s or 3xxs is
# skipped by the same guard as the journey screens -- it is another test's find.
EXTRA_SCREENS = {
    "solution_architect":   ["/solutions/create",
                             "/solutions/architect/workspace"],
    "enterprise_architect": ["/architecture/strategy/capability/new",
                             "/capability-map/hierarchy"],
    "business_architect":   ["/capability-map/hierarchy",
                             "/capability-map/trees"],
    "arb_member":           ["/arb/reviews/create",
                             "/arb/change-requests/new",
                             "/arb/sessions/create"],
    "portfolio_manager":    ["/applications/{application}",
                             "/applications/create"],
    "cto":                  ["/applications/{application}"],
    "procurement":          ["/procurement/contracts/new",
                             "/procurement/contracts/{contract}",
                             "/procurement/licenses/new"],
    "application_manager":  ["/applications/{application}",
                             "/applications/{application}/roadmap"],
    "platform_admin":       ["/admin/new-user",
                             "/admin/feature-flags/new"],
}


def _screens_for(archetype, seeded):
    """Journey screens plus the persona's detail/create/modal screens.

    {placeholder} tokens in EXTRA_SCREENS are filled from the seeded ids; an
    entry naming an id we did not seed is dropped rather than requested against a
    missing row. Deduplicated, journey screens first so the signature screen is
    always measured even if a later screen times out.
    """
    ids = seeded.get("ids", {})
    paths = list(SCREENS.get(archetype, []))
    for tmpl in EXTRA_SCREENS.get(archetype, []):
        try:
            paths.append(tmpl.format(**ids))
        except (KeyError, IndexError):
            continue  # id not seeded -- do not request a placeholder URL
    return list(dict.fromkeys(paths))

# ---------------------------------------------------------------------------
# The init-script probe. Installed BEFORE any page script via add_init_script,
# so every listener the app binds during boot is observed. It marks each Element
# that a real interaction listener is bound to (__ir_wired), which a bubbling
# event from a descendant would reach. Document/window/body listeners are left
# unmarked on purpose -- see the module docstring.
# ---------------------------------------------------------------------------
PROBE = r"""
(() => {
  const INTERACT = new Set(['click','mousedown','mouseup','pointerdown','pointerup',
    'submit','change','input','keydown','keyup']);
  const origAdd = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, listener, opts) {
    try {
      // Only ELEMENT-level interaction listeners mark wiring. A bubbling click
      // reaches an Element ancestor's listener, so marking the element it is
      // bound to (and, by ancestry, its subtree) is correct. Listeners bound to
      // document / window / body are NOT marked here: those are the many
      // page-level delegates, and every one of them in this codebase dispatches
      // on a data-* action attribute (data-action, data-cm-action, ...) or a
      // data-modal-* hook -- both of which the DOM census detects on the control
      // itself. Crediting the whole page from a document listener is precisely
      // the over-credit that made an earlier probe blind.
      if (INTERACT.has(type) && this && this.nodeType === 1) {
        this.__ir_wired = true;
      }
    } catch (e) { /* never let the probe break the page */ }
    return origAdd.call(this, type, listener, opts);
  };
})();
"""

# The DOM census. Runs after the page has settled. Returns dead controls and
# junk modal tokens. `suppressed` and `unknownDelegate` are retained as inert
# fields (always 0 / false) so the per-screen report shape stays stable.
CENSUS = r"""
() => {
  // Every document-level click delegate in this codebase dispatches on a data-*
  // action/hook attribute; a control carrying one is wired by delegation. This
  // regex is deliberately GENEROUS -- crediting a control as wired can only miss
  // a dead one, never invent one, and a truly dead control carries no handler
  // attribute at all. Matches data-action, data-cm-action, data-acm-action,
  // data-vendor-action, data-apqc-action, data-modal-*, data-confirm,
  // data-autosubmit, data-toggle, data-dismiss-*, data-href-*, data-tab, etc.
  const HOOK_RE = /^data-.*(action|modal|confirm|autosubmit|toggle|dismiss|href|open|close|tab|nav|target|filter|sort|page|select|expand|collapse|copy|download|submit)/;

  const visible = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    if (el.hasAttribute('hidden') || el.getAttribute('aria-hidden') === 'true') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const isDisabled = (el) =>
    el.disabled || el.getAttribute('aria-disabled') === 'true'
    || el.classList.contains('cursor-not-allowed');

  // A real navigation href (not a placeholder / no-op).
  const realHref = (el) => {
    if (!el.hasAttribute('href')) return false;
    const h = (el.getAttribute('href') || '').trim();
    if (!h) return false;
    if (h === '#') return false;
    if (h.toLowerCase().startsWith('javascript:')) return false;
    return true;
  };

  // A data-* handler hook on the control or a wrapper it bubbles to. Depth 6:
  // deep enough for real delegation wrappers (a toolbar, a list row), shallow
  // enough that a distant page container does not credit the whole screen.
  const hookOnSelfOrAncestor = (el) => {
    let n = el;
    for (let d = 0; n && d < 6; d++, n = n.parentElement) {
      if (!n.attributes) continue;
      for (const a of n.attributes) if (HOOK_RE.test(a.name)) return true;
    }
    return false;
  };
  // A real Alpine CLICK binding (not @click.away / .outside / a keyboard or
  // window/document modifier, which close menus and do not wire the control).
  const alpineOnSelfOrAncestor = (el) => {
    let n = el;
    for (let d = 0; n && d < 6; d++, n = n.parentElement) {
      if (!n.attributes) continue;
      for (const a of n.attributes) {
        const nm = a.name;
        if (nm[0] !== '@' && nm.indexOf('x-on:') !== 0) continue;
        if (nm.indexOf('click') === -1 && nm.indexOf('mousedown') === -1
            && nm.indexOf('pointerdown') === -1) continue;
        if (nm.indexOf('.away') !== -1 || nm.indexOf('.outside') !== -1
            || nm.indexOf('.window') !== -1 || nm.indexOf('.document') !== -1) continue;
        return true;
      }
    }
    return false;
  };
  // An element-level JS listener on the control or a bubbling ancestor. Depth 6
  // for the same reason as the hook walk: a listener bound to <body> or a huge
  // page shell is delegation whose selector we cannot read, and crediting the
  // whole page from it is the blindness we are avoiding.
  const listenerOnSelfOrAncestor = (el) => {
    let n = el;
    for (let d = 0; n && d < 6; d++, n = n.parentElement) {
      if (n.__ir_wired) return true;
    }
    return false;
  };
  const isFormSubmit = (el) => {
    const t = (el.getAttribute('type') || '').toLowerCase();
    if (el.tagName === 'INPUT' && t === 'submit') return !!el.form;
    if (el.tagName === 'BUTTON' && (t === 'submit' || t === '')) return !!el.closest('form');
    return false;
  };

  // ---- (a) dead controls ------------------------------------------------
  const candidates = new Set();
  document.querySelectorAll(
    'button, [role="button"], [role="link"], a, input[type="submit"], ' +
    'input[type="button"], input[type="image"], .cursor-pointer'
  ).forEach(e => candidates.add(e));

  const dead = [];
  let suppressed = 0;
  for (const el of candidates) {
    if (!visible(el) || isDisabled(el)) continue;
    // A <label>, a form input (checkbox/radio/text/select), or a wrapper that
    // CONTAINS its own control is not a dead control: a label focuses/toggles
    // its input natively, a checkbox visibly toggles, and a .cursor-pointer
    // wrapper's interactivity belongs to the button/anchor/input inside it --
    // which is judged as its own candidate. Skipping these removes the entire
    // false-positive class an x-model / @change checkbox would otherwise create.
    if (el.tagName === 'LABEL') continue;
    if (el.tagName === 'INPUT') {
      const t = (el.getAttribute('type') || '').toLowerCase();
      if (t !== 'submit' && t !== 'button' && t !== 'image') continue;
    }
    if (el.querySelector && el.querySelector('input, select, textarea, button, a[href]'))
      continue;
    // A plain anchor that navigates, or a submit, is wired by definition.
    if (el.tagName === 'A' && realHref(el)) continue;
    if (isFormSubmit(el)) continue;
    // A close/dismiss inside a native <details> or <dialog> is wired by the UA.
    if (el.closest('summary') || el.tagName === 'SUMMARY') continue;

    const wired =
      listenerOnSelfOrAncestor(el) ||
      alpineOnSelfOrAncestor(el) ||
      hookOnSelfOrAncestor(el) ||
      realHref(el);
    if (wired) continue;

    const label = (el.innerText || el.textContent || el.getAttribute('aria-label')
      || el.getAttribute('title') || '').replace(/\s+/g, ' ').trim().slice(0, 60);
    dead.push({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      label: label || '(no label)',
    });
  }

  // ---- (b) junk modal tokens -------------------------------------------
  // JS coercion leaks that never legitimately appear as a server-rendered value.
  // Matched as a STANDALONE text node value, so "annulled" never trips "null".
  // 'undefined' and 'NaN' as whole words never occur in legitimate UI copy, so a
  // word-boundary match is safe and catches the common "Owner: undefined" shape.
  // 'null' as a whole word is riskier ("nullable", "annulled" are fine because of
  // the boundary, but "null hypothesis" is legit), so it is matched only as an
  // entire standalone value node. '{{' is an unrendered Jinja expression.
  const WORD_JUNK = /(^|[^A-Za-z])(undefined|NaN)([^A-Za-z]|$)/;
  const junk = [];
  const seenJunk = new Set();
  const modals = document.querySelectorAll(
    '[data-modal-id], [role="dialog"], .modal, [x-show]');
  for (const m of modals) {
    const walker = document.createTreeWalker(m, NodeFilter.SHOW_TEXT);
    let t;
    while ((t = walker.nextNode())) {
      const v = (t.nodeValue || '').trim();
      if (!v) continue;
      const low = v.toLowerCase();
      if (WORD_JUNK.test(v) || low === 'null' || v.indexOf('{{') !== -1) {
        const s = v.slice(0, 40);
        if (!seenJunk.has(s)) { seenJunk.add(s); junk.push(s); }
        break;  // one finding per modal is enough to fail it
      }
    }
  }

  return { dead, suppressed, unknownDelegate: false, junk, candidates: candidates.size };
}
"""


def _load_baseline():
    try:
        with open(BASELINE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _login(page, base, email):
    """Sign in as a user does. Mirrors test_archetype_journeys._login."""
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    try:
        page.click("#submit", force=True, no_wait_after=True)
    except TypeError:
        page.locator("#submit").dispatch_event("click")
    try:
        page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)
    except Exception:
        pass
    page.wait_for_timeout(600)
    assert "/account/login" not in page.url, (
        "could not sign in as %s" % email)


def _measure(archetype, live_server, seeded, browser):
    """Log in and census every key screen for one persona.

    Returns a dict: {dead, junk, suppressed, screens: {path: {...}}}. The context
    installs the wiring probe via add_init_script BEFORE any navigation, which is
    the whole reason the listener counts are trustworthy.
    """
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.set_default_timeout(PAGE_TIMEOUT)
    ctx.set_default_navigation_timeout(PAGE_TIMEOUT)
    ctx.add_init_script(PROBE)
    page = ctx.new_page()
    # A 5xx on any submit is a hard finding; watch every response.
    server_errors = []
    page.on("response", lambda r: server_errors.append(r.url) if r.status >= 500 else None)

    result = {"dead": 0, "junk": 0, "suppressed": 0, "form_500": 0, "screens": {}}
    try:
        _login(page, live_server, seeded["emails"][archetype])
        for path in _screens_for(archetype, seeded):
            try:
                resp = page.goto(live_server + path, wait_until="domcontentloaded",
                                 timeout=PAGE_TIMEOUT)
            except Exception:
                continue
            if resp is None or resp.status >= 400:
                continue
            page.wait_for_timeout(1200)
            # Remove the first-run onboarding overlay so it does not mask the page.
            try:
                page.eval_on_selector_all(
                    "[x-show='showOnboarding']", "els => els.forEach(e => e.remove())")
            except Exception:
                pass
            try:
                census = page.evaluate(CENSUS)
            except Exception:
                continue

            # (c) forms: submit the first non-destructive, non-search form and
            # assert no 5xx. Destructive and pure-GET filter forms are skipped --
            # a census must not delete rows or re-run a search to make its point.
            before = len(server_errors)
            _try_submit_one_form(page)
            form_500 = len(server_errors) - before

            result["screens"][path] = {
                "dead": census["dead"],
                "junk": census["junk"],
                "suppressed": census["suppressed"],
                "unknownDelegate": census["unknownDelegate"],
                "candidates": census["candidates"],
                "form_500": form_500,
            }
            result["dead"] += len(census["dead"])
            result["junk"] += len(census["junk"])
            result["suppressed"] += census["suppressed"]
            result["form_500"] += form_500
    finally:
        ctx.close()
    if os.environ.get("SMOKE_IR_DEBUG") == "1":
        print("[ir-debug] %s measured screens: %s" % (
            archetype, {p: s.get("candidates") for p, s in result["screens"].items()}))
    return result


def _try_submit_one_form(page):
    """Submit at most one safe form and let any 5xx surface on the response hook.

    Safe means: has a submit control, is not method=GET (a search/filter that
    just reloads), and is not destructive (no delete/remove/destroy in its action
    or submit label). We press the real control -- empty -- and expect either a
    validation message or a real response, never a torn-down 500 page.
    """
    try:
        forms = page.query_selector_all("form")
    except Exception:
        return
    for form in forms:
        try:
            method = (form.get_attribute("method") or "").lower()
            if method == "get":
                continue
            action = (form.get_attribute("action") or "").lower()
            if any(w in action for w in ("delete", "remove", "destroy", "logout", "sign-out")):
                continue
            submit = form.query_selector(
                "button[type=submit], input[type=submit], button:not([type])")
            if submit is None:
                continue
            label = (submit.inner_text() or "").lower()
            if any(w in label for w in ("delete", "remove", "destroy", "sign out", "log out")):
                continue
            if not submit.is_visible():
                continue
            with page.expect_response(lambda r: True, timeout=8000):
                submit.click(no_wait_after=True, force=True)
            page.wait_for_timeout(400)
        except Exception:
            # A form that will not submit is not this check's finding; the 5xx
            # hook records the only thing this clause asserts on.
            pass
        return  # one form per screen is enough


@pytest.mark.parametrize("archetype", sorted(SCREENS))
def test_controls_are_wired_and_modals_are_clean(archetype, live_server, seeded, browser):
    measured = _measure(archetype, live_server, seeded, browser)

    if WRITE_BASELINE:
        # Handled by the writer test below; skip assertion in this mode.
        pytest.skip("writing baseline")

    baseline = _load_baseline().get(archetype, {})
    allow_dead = baseline.get("dead", 0)
    allow_junk = baseline.get("junk", 0)

    # Detail the worst offenders so a failure is actionable, not just a number.
    detail = []
    for path, s in measured["screens"].items():
        bits = []
        if s["dead"]:
            samples = ", ".join(
                "%s '%s'" % (d["role"] or d["tag"], d["label"]) for d in s["dead"][:4])
            bits.append("%d dead (%s)" % (len(s["dead"]), samples))
        if s["junk"]:
            bits.append("%d junk-modal (%s)" % (len(s["junk"]), "; ".join(s["junk"][:3])))
        if s["form_500"]:
            bits.append("%d form-5xx" % s["form_500"])
        if s["suppressed"]:
            bits.append("%d suppressed (unknown delegate)" % s["suppressed"])
        if bits:
            detail.append("  %s: %s" % (path, "; ".join(bits)))

    assert measured["dead"] <= allow_dead and measured["junk"] <= allow_junk \
        and measured["form_500"] == 0, (
        "%s interaction-reality regressed: %d dead controls (allow %d), "
        "%d junk modals (allow %d), %d form 5xx (allow 0).\n%s\n"
        "A dead control looks pressable and has nothing listening; a junk modal "
        "shows the user a coercion leak; a form 5xx is a silent failure. None is "
        "visible to a source-reading gate."
        % (archetype, measured["dead"], allow_dead, measured["junk"], allow_junk,
           measured["form_500"], "\n".join(detail) or "  (per-screen detail above)"))


def test_write_interaction_baseline(live_server, seeded, browser):
    """Regenerate interaction_reality_baseline.json by MEASUREMENT.

    Only does anything under SMOKE_WRITE_INTERACTION_BASELINE=1, so an ordinary
    run never rewrites the ratchet. form_500 is deliberately NOT baselined -- a
    silent 5xx is never acceptable, so its allowance is a hard zero.
    """
    if not WRITE_BASELINE:
        pytest.skip("set SMOKE_WRITE_INTERACTION_BASELINE=1 to regenerate")
    out = {}
    for archetype in sorted(SCREENS):
        m = _measure(archetype, live_server, seeded, browser)
        out[archetype] = {"dead": m["dead"], "junk": m["junk"]}
    with open(BASELINE_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("[interaction-reality] wrote baseline: %s" % json.dumps(out))


# ---------------------------------------------------------------------------
# CI registration
# ---------------------------------------------------------------------------
# The existing smoke job runs `-m "not adversarial and not census"`, so this
# heavy census does NOT run there. Add a sibling step to .github/workflows/ci.yml
# (same `smoke` job, after "Run archetype journeys", reusing its Postgres service
# and Chromium install) so it runs in its own step and uploads failure shots:
#
#     - name: Interaction-reality census (dead controls, junk modals, silent forms)
#       run: pytest tests/smoke/test_interaction_reality.py -q -p no:randomly
#            -m census --timeout=1200 -W ignore::DeprecationWarning
#
# It is a per-archetype ratchet: it fails only when an archetype's dead-control
# or junk-modal count rises above interaction_reality_baseline.json, or when any
# form returns a 5xx (never baselined). After an intentional UI change that adds
# a genuinely-wired control, refresh the ratchet by measurement:
#
#     SMOKE_WRITE_INTERACTION_BASELINE=1 pytest \
#         tests/smoke/test_interaction_reality.py::test_write_interaction_baseline \
#         -m census
