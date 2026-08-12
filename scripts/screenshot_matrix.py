"""Wave screenshot-matrix harness (scratch-quality, reused every wave).

Logs in as ADMIN_EMAIL/ADMIN_PASSWORD (from .env), dismisses the first-login
onboarding modal if shown, then screenshots a fixed route x width matrix plus
two special captures: the guided-mode (empty-state) dashboard for a freshly
seeded sparse org, and the AI-chat conversation rail in its collapsed state.

Console errors collected across ANY page/navigation fail the run (exit 1) --
a screenshot matrix that silently tolerates a JS error is not evidence.

Usage:
    python scripts/screenshot_matrix.py [--base http://127.0.0.1:5100]

Requires: `pip install playwright && playwright install chromium` once,
and a running dev server at --base (default http://127.0.0.1:5100) backed
by the worktree's .env DATABASE_URL.
"""
from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import urlsplit

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = REPO_ROOT / "docs" / "superpowers" / "evidence" / "wave1"

WIDTHS = [1024, 1280, 1440]
ROUTES = [
    "/dashboard/overview",
    "/ai-chat/",
    "/applications/",
    "/capability-map/",
    "/capability-map/hierarchy",
    "/solutions/",
]
VIEWPORT_HEIGHT = 900


def resolve_first_application_id(page, base_url: str) -> str | None:
    """Read a real application id off the list page's own links, rather
    than querying the DB directly or hardcoding one -- the smallest honest
    way to get a route the matrix can screenshot without ever being wrong
    about what id exists in this run's database.
    """
    page.goto(f"{base_url}/applications/", wait_until="networkidle")
    # The list page also links to non-detail /applications/... paths (its own
    # index link, /applications/vendors, /<id>/edit, ...) -- scan every anchor
    # for the first one that is exactly /applications/<digits>, rather than
    # trusting the first match in DOM order to already be a detail link.
    anchors = page.locator('a[href^="/applications/"]')
    for i in range(anchors.count()):
        raw = anchors.nth(i).get_attribute("href") or ""
        match = re.match(r"^/applications/(\d+)$", raw)
        if match:
            return match.group(1)
    return None


def _load_dotenv(env_path: Path) -> dict:
    values = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _is_local_base(base_url: str) -> bool:
    """True only for a localhost/127.0.0.1/::1 --base -- seeding a fixture
    org+user is a write against whatever database the target server is
    backed by, and this harness must never do that against a non-local
    (i.e. possibly production or shared staging) host by habit."""
    host = urlsplit(base_url).hostname or ""
    return host.lower() in LOCAL_HOSTS


def _route_slug(route: str) -> str:
    slug = route.strip("/").replace("/", "-")
    return slug or "root"


def dismiss_onboarding_if_present(page) -> None:
    """Click through the 3-step onboarding wizard, or Escape as a fallback."""
    try:
        modal = page.locator("[x-show='showOnboarding']").first
        if modal.count() == 0:
            return
        # Give Alpine a moment to evaluate x-show / x-cloak on first paint.
        page.wait_for_timeout(300)
        if not modal.is_visible():
            return
        # Step 1 -> 2 -> 3: both intermediate steps expose a "Continue" button.
        for _ in range(2):
            continue_btn = page.locator("button:visible", has_text="Continue").first
            if continue_btn.count() == 0:
                break
            continue_btn.click()
            page.wait_for_timeout(200)
        # Step 3: dismiss via "Skip for now" so we do not navigate away.
        skip_btn = page.locator("button:visible", has_text="Skip for now").first
        if skip_btn.count() > 0:
            skip_btn.click()
        else:
            page.keyboard.press("Escape")
        page.wait_for_timeout(200)
    except Exception as exc:  # noqa: BLE001 - best-effort dismissal, never fatal to the run
        print(f"  [onboarding] dismissal attempt raised (continuing): {exc}")


def login(page, base_url: str, email: str, password: str) -> None:
    page.goto(f"{base_url}/account/login", wait_until="networkidle")
    page.fill("#email", email)
    page.fill("#password", password)
    page.click("#submit")
    page.wait_for_load_state("networkidle")
    dismiss_onboarding_if_present(page)


def capture_matrix(page, base_url: str, console_errors: list, label_prefix: str = "", routes=None) -> list:
    produced = []
    for width in WIDTHS:
        for route in (routes if routes is not None else ROUTES):
            page.set_viewport_size({"width": width, "height": VIEWPORT_HEIGHT})
            page.goto(f"{base_url}{route}", wait_until="networkidle")
            dismiss_onboarding_if_present(page)
            slug = _route_slug(route)
            filename = f"{label_prefix}{slug}-{width}.png"
            out_path = EVIDENCE_DIR / filename
            page.screenshot(path=str(out_path), full_page=True)
            produced.append(out_path)
            print(f"  captured {out_path.relative_to(REPO_ROOT)}")
    return produced


def seed_sparse_org(app_module) -> tuple[str, str]:
    """Idempotently seed a single sparse org + admin user for guided-mode capture.

    Returns (email, password). Password is generated fresh each run and never
    persisted anywhere (not printed to a log file, not stored on the user row
    beyond its hash) -- it only lives in this process's memory for this run.
    """
    from app import db
    from app.models.organization import Organization
    from app.models.user import User

    # NOTE: the brief specifies "w1-evidence@example.test", but the login form's
    # WTForms Email() validator (email_validator library) rejects the RFC 2606
    # reserved TLD ".test" outright ("special-use or reserved name that cannot
    # be used") -- confirmed directly against email_validator.validate_email.
    # That is a real, pre-existing constraint of the login form, not something
    # this harness should route around by bypassing validation, so this uses
    # the same fake-but-accepted domain already established in this repo for
    # ADMIN_EMAIL (qa-admin@example.com, see .env).
    email = "w1-evidence@example.com"
    password = secrets.token_urlsafe(24)

    app = app_module.create_app(os.getenv("FLASK_CONFIG") or "default")
    with app.app_context():
        org = Organization.query.filter_by(slug="w1-evidence-sparse-org").first()
        if org is None:
            org = Organization(name="W1 Evidence Sparse Org", slug="w1-evidence-sparse-org")
            db.session.add(org)
            db.session.flush()

        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                first_name="W1",
                last_name="Evidence",
                email=email,
                confirmed=True,
                enterprise_role="solution_architect",
            )
            user.organization_id = org.id
            user.password = password
            db.session.add(user)
        else:
            # Re-run: rotate the password so this run's credential is known,
            # and keep onboarding_completed_at set so the modal stays out of
            # the guided-mode screenshot.
            user.password = password
            user.organization_id = org.id
        import datetime

        user.onboarding_completed_at = datetime.datetime.utcnow()
        db.session.commit()

    return email, password


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:5100")
    args = parser.parse_args()
    base_url = args.base.rstrip("/")

    env = _load_dotenv(REPO_ROOT / ".env")
    admin_email = env.get("ADMIN_EMAIL") or os.environ.get("ADMIN_EMAIL")
    admin_password = env.get("ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        print("ERROR: ADMIN_EMAIL / ADMIN_PASSWORD not found in .env or environment.")
        return 1

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. `pip install playwright && playwright install chromium`.")
        return 1

    console_errors: list[str] = []
    produced_files: list[Path] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        def on_console(msg):
            if msg.type == "error":
                console_errors.append(f"{page.url} :: {msg.text}")

        page.on("console", on_console)

        print(f"Logging in at {base_url}/account/login as {admin_email} ...")
        login(page, base_url, admin_email, admin_password)

        print("Resolving a real application id for the detail-page route ...")
        detail_app_id = resolve_first_application_id(page, base_url)
        matrix_routes = list(ROUTES)
        if detail_app_id:
            matrix_routes.append(f"/applications/{detail_app_id}")
            print(f"  resolved id {detail_app_id} -> /applications/{detail_app_id}")
        else:
            print("  WARNING: no application id found on /applications/ -- "
                  "skipping the detail-page route (nothing seeded to link to).")

        print("Capturing main route x width matrix ...")
        produced_files += capture_matrix(page, base_url, console_errors, routes=matrix_routes)

        print("Capturing AI-chat rail collapsed state at 1280 ...")
        page.set_viewport_size({"width": 1280, "height": VIEWPORT_HEIGHT})
        page.goto(f"{base_url}/ai-chat/", wait_until="networkidle")
        dismiss_onboarding_if_present(page)
        toggle = page.locator('button[aria-label="Toggle conversation panel"]').first
        if toggle.count() > 0:
            toggle.click()
            page.wait_for_timeout(300)
        else:
            print("  WARNING: rail toggle button not found; capturing current state as-is.")
        collapsed_path = EVIDENCE_DIR / "ai-chat-rail-collapsed-1280.png"
        page.screenshot(path=str(collapsed_path), full_page=True)
        produced_files.append(collapsed_path)
        print(f"  captured {collapsed_path.relative_to(REPO_ROOT)}")

        context.close()
        browser.close()

        # --- Guided-mode (sparse org) dashboard capture: fresh login as the seeded user ---
        if not _is_local_base(base_url):
            print(
                f"REFUSED: --base '{base_url}' is not localhost/127.0.0.1/::1 -- "
                "skipping guided-mode fixture seeding (seed_sparse_org writes an "
                "Organization + User row) and the guided-mode dashboard capture. "
                "Re-run against a local dev server to capture those screenshots."
            )
        else:
            print("Seeding sparse-org guided-mode user ...")
            sys.path.insert(0, str(REPO_ROOT))
            import manage as app_module  # noqa: E402  (import after sys.path fixup, deliberate)

            guided_email, guided_password = seed_sparse_org(app_module)

            browser2 = p.chromium.launch()
            context2 = browser2.new_context()
            page2 = context2.new_page()

            def on_console2(msg):
                if msg.type == "error":
                    console_errors.append(f"{page2.url} :: {msg.text}")

            page2.on("console", on_console2)

            print(f"Logging in as guided-mode user {guided_email} ...")
            login(page2, base_url, guided_email, guided_password)

            print("Capturing guided-mode dashboard ...")
            for width in WIDTHS:
                page2.set_viewport_size({"width": width, "height": VIEWPORT_HEIGHT})
                page2.goto(f"{base_url}/dashboard/overview", wait_until="networkidle")
                dismiss_onboarding_if_present(page2)
                out_path = EVIDENCE_DIR / f"dashboard-guided-{width}.png"
                page2.screenshot(path=str(out_path), full_page=True)
                produced_files.append(out_path)
                print(f"  captured {out_path.relative_to(REPO_ROOT)}")

            context2.close()
            browser2.close()

    print(f"\nTotal screenshots produced: {len(produced_files)}")
    for f in produced_files:
        print(f"  {f.relative_to(REPO_ROOT)}")

    if console_errors:
        print(f"\nFAIL: {len(console_errors)} console error(s) collected:")
        for err in console_errors:
            print(f"  {err}")
        return 1

    print("\nNo console errors collected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
