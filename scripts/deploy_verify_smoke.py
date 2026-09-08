"""Authenticated Playwright reachability check for scripts/deploy_verified.sh.

Step 5 of the deploy-verification contract: prove a real browser, with real
credentials, can log in against the just-deployed production site and reach a
real page — not just that a container reports healthy or /version matches.

Deliberately minimal. Its job is to prove END-TO-END REACHABILITY through the
real login flow, not to re-test specific application bugs (that is what
tests/smoke/ is for, run in CI against a disposable database). Never invoked
directly by a developer; scripts/deploy_verified.sh calls it only when
DEPLOY_VERIFY_EMAIL and DEPLOY_VERIFY_PASSWORD are both set in the
environment, and skips it with a loud warning otherwise. No credential is
ever hardcoded here.

Exit code 0 = reached the dashboard while authenticated. Non-zero otherwise,
with a diagnostic on stderr.
"""

import os
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "deploy_verify_smoke: playwright not installed; install it "
        "(`pip install playwright && playwright install chromium`) to use "
        "the optional authenticated smoke check, or leave "
        "DEPLOY_VERIFY_EMAIL/PASSWORD unset to skip it",
        file=sys.stderr,
    )
    sys.exit(1)


def main():
    base_url = os.environ.get("DEPLOY_VERIFY_BASE_URL", "https://165-22-125-156.sslip.io")
    email = os.environ["DEPLOY_VERIFY_EMAIL"]
    password = os.environ["DEPLOY_VERIFY_PASSWORD"]

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--ignore-certificate-errors"])
        try:
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            login_url = f"{base_url.rstrip('/')}/account/login"
            response = page.goto(login_url, timeout=30000, wait_until="domcontentloaded")
            if response is None or not response.ok:
                print(
                    f"deploy_verify_smoke: FAIL - GET {login_url} returned "
                    f"{response.status if response else 'no response'}",
                    file=sys.stderr,
                )
                return 1

            # Fill and submit the real login form - no shortcuts through a
            # session cookie or API token, this is proving the actual journey.
            page.fill("input[type=email], input[name=email]", email)
            page.fill("input[type=password], input[name=password]", password)
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle", timeout=30000)

            if "/login" in page.url:
                print(
                    f"deploy_verify_smoke: FAIL - still on a login-shaped URL "
                    f"after submit ({page.url}); authentication did not succeed",
                    file=sys.stderr,
                )
                return 1

            body_text = page.locator("body").inner_text(timeout=10000)
            if not body_text.strip():
                print(
                    "deploy_verify_smoke: FAIL - authenticated page rendered no "
                    "visible text",
                    file=sys.stderr,
                )
                return 1

            print(f"deploy_verify_smoke: OK - authenticated, landed on {page.url}")
            return 0
        finally:
            browser.close()


if __name__ == "__main__":
    sys.exit(main())
