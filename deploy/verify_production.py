"""Verify a deployed site in a real browser, from a workstation.

    pip install playwright && python -m playwright install chromium
    python deploy/verify_production.py https://your-host

Exits non-zero if anything fails, so it can gate a deploy.

Two modes:

  anonymous (default)  loads the public pages and checks the things that break
                       silently - the front end failing to boot, integrity
                       mismatches, console errors, horizontal overflow
  authenticated        set SMOKE_EMAIL and SMOKE_PASSWORD to also walk a signed-in
                       page

Why this exists separately from tests/smoke: that suite runs in CI against a
seeded database and proves the CODE is good. This proves the DEPLOYMENT is good -
that the bytes actually being served to users behave. A deploy can be green in CI
and still ship a front end the browser refuses to execute, which is exactly what
happened here on 2026-07-31.
"""
import os
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("playwright is not installed - see the docstring")
    raise SystemExit(2)

PUBLIC_PAGES = ["/health", "/account/login"]
AUTH_PAGES = ["/dashboard/overview", "/value-streams/", "/applications/"]

STATE = """() => {
  const controls = [...document.querySelectorAll('input,select,textarea')]
      .filter(e => !['hidden','submit','button','reset','image'].includes(e.type));
  const unnamed = controls.filter(e => {
      if (e.getAttribute('aria-label') || e.getAttribute('aria-labelledby')) return false;
      if (e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`)) return false;
      if (e.closest('label')) return false;
      return true;
  });
  const slots = document.querySelectorAll('[data-lucide]').length;
  return {
      alpine: typeof window.Alpine,
      purify: typeof window.DOMPurify,
      iconSlots: slots,
      iconsRendered: document.querySelectorAll('svg.lucide, [data-lucide] svg').length,
      cloaked: document.querySelectorAll('[x-cloak]').length,
      overflow: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
      unnamed: unnamed.length,
  };
}"""

results = []


def check(label, ok, detail=""):
    results.append(ok)
    print("  %-44s %s %s" % (label, "PASS" if ok else "FAIL", detail))


def audit(page, base, path, expect_app_shell):
    response = page.goto(base + path, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    try:
        page.eval_on_selector_all("[x-show='showOnboarding']", "e=>e.forEach(x=>x.remove())")
    except Exception:
        pass
    status = response.status if response else 0
    check("%s responds" % path, status < 400, "HTTP %s" % status)
    if status >= 400:
        return
    state = page.evaluate(STATE)
    if expect_app_shell:
        # The signal that matters most: integrity failures are silent in the
        # server log and total for the user.
        check("%s front end booted" % path, state["alpine"] == "object",
              "window.Alpine is %s" % state["alpine"])
        check("%s sanitiser loaded" % path, state["purify"] == "function")
        if state["iconSlots"]:
            check("%s icons rendered" % path,
                  state["iconsRendered"] == state["iconSlots"],
                  "%d/%d" % (state["iconsRendered"], state["iconSlots"]))
        check("%s nothing left cloaked" % path, state["cloaked"] == 0,
              "%d hidden" % state["cloaked"])
    check("%s no horizontal overflow" % path, state["overflow"] == 0,
          "%dpx" % state["overflow"])
    check("%s all controls named" % path, state["unnamed"] == 0,
          "%d unnamed" % state["unnamed"])


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("VERIFY_BASE_URL", "")).rstrip("/")
    if not base:
        print("usage: python deploy/verify_production.py <base-url>")
        return 2
    email = os.environ.get("SMOKE_EMAIL")
    password = os.environ.get("SMOKE_PASSWORD")

    print("verifying %s" % base)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  ignore_https_errors=True)
        page = ctx.new_page()
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        print("\nanonymous")
        for path in PUBLIC_PAGES:
            audit(page, base, path, expect_app_shell=(path != "/health"))

        if email and password:
            print("\nauthenticated as %s" % email)
            page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=60000)
            page.fill("#email", email)
            page.fill("#password", password)
            # The button carries :disabled="isSubmitting"; force past the
            # actionability check and wait for the URL to change instead.
            try:
                page.click("#submit", force=True, no_wait_after=True)
            except TypeError:
                page.locator("#submit").dispatch_event("click")
            try:
                page.wait_for_url(lambda u: "/account/login" not in u, timeout=60000)
            except Exception:
                pass
            signed_in = "/account/login" not in page.url
            check("signed in", signed_in, page.url.replace(base, ""))
            if signed_in:
                errors.clear()
                for path in AUTH_PAGES:
                    audit(page, base, path, expect_app_shell=True)
        else:
            print("\n(set SMOKE_EMAIL and SMOKE_PASSWORD to also check signed-in pages)")

        real = [e for e in errors if "favicon" not in e.lower()]
        check("no console errors", not real, "%d" % len(real))
        for e in real[:5]:
            print("      - %s" % e[:130])
        browser.close()

    passed = sum(1 for r in results if r)
    print("\n%d/%d checks passed" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
