"""Measure the Architecture Journey hub's real geometry at a fixed viewport.

The screenshots taken during the journeys wave grew the viewport to fit content
before capturing, which is precisely the technique that hides a layout defect: a
page with a large empty region below its content looks correct once the window is
as tall as the region. This measures instead of photographing, at the viewport a
user actually has.

It reports, for the shell and every scroll container:

    clientHeight   what the user can see
    scrollHeight   how tall the box thinks its content is
    content bottom the y of the last element that actually paints

A large gap between the last painted element and scrollHeight is the defect: dead
space the user can scroll through for no reason.
"""

from __future__ import annotations

import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

REPO = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "LayoutProbe!2026"
VIEWPORT = {"width": 1440, "height": 900}


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _seed():
    sys.path.insert(0, str(REPO))
    from app import create_app, db
    from app.models.organization import Organization
    from app.models.user import Role, User

    app = create_app("testing")
    with app.app_context():
        db.create_all()
        Role.insert_roles()
        suffix = uuid.uuid4().hex[:8]
        org = Organization(name=f"Layout {suffix}", slug=f"layout-{suffix}")
        db.session.add(org)
        db.session.flush()
        email = f"layout-{suffix}@example.com"
        user = User(
            email=email, first_name="Lay", last_name="Out", confirmed=True,
            organization_id=org.id, enterprise_role="business_architect",
        )
        user.password = PASSWORD
        db.session.add(user)
        db.session.commit()
        return email


def _boot(port, log):
    env = dict(os.environ)
    env.setdefault("FLASK_CONFIG", "testing")
    url = env.get("TEST_DATABASE_URL") or env.get("DATABASE_URL")
    if url:
        env["DATABASE_URL"] = env["TEST_DATABASE_URL"] = url
    handle = open(log, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "manage", "run", "--no-reload",
         "--port", str(port)],
        cwd=str(REPO), env=env, stdout=handle, stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 240
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"server died; see {log}")
        try:
            urllib.request.urlopen(base + "/health", timeout=3)
            return proc, base
        except urllib.error.HTTPError:
            return proc, base
        except Exception:
            time.sleep(2)
    proc.terminate()
    raise SystemExit("server did not boot")


OFFENDERS = """() => {
    // Which elements actually extend past the viewport? documentElement is taller
    // than body, so the culprit is out of body's flow: fixed, absolute, or a
    // portal rendered outside the overflow-hidden shell.
    const vh = window.innerHeight;
    const found = [];
    document.querySelectorAll('body *').forEach((el) => {
        const r = el.getBoundingClientRect();
        if (r.height > 0 && r.bottom > vh + 4) {
            const cs = getComputedStyle(el);
            found.push({
                tag: el.tagName.toLowerCase(),
                id: el.id || '',
                cls: (el.className || '').toString().slice(0, 80),
                pos: cs.position,
                display: cs.display,
                top: Math.round(r.top),
                bottom: Math.round(r.bottom),
                height: Math.round(r.height),
                parent: el.parentElement ? el.parentElement.tagName.toLowerCase()
                        + '.' + (el.parentElement.className || '').toString().slice(0, 40) : '',
            });
        }
    });
    // Deepest first is noisy; report the tallest few.
    found.sort((a, b) => b.bottom - a.bottom);
    return found.slice(0, 8);
}"""

PROBE = """() => {
    const out = { viewport: window.innerHeight, doc: document.documentElement.scrollHeight,
                  body: document.body.scrollHeight, boxes: [] };
    // Every element that can scroll, plus the deepest painted content.
    document.querySelectorAll('*').forEach((el) => {
        const cs = getComputedStyle(el);
        const scrolls = /(auto|scroll)/.test(cs.overflowY);
        if (scrolls && el.scrollHeight > 0) {
            let lastBottom = 0;
            el.querySelectorAll('*').forEach((c) => {
                const r = c.getBoundingClientRect();
                const er = el.getBoundingClientRect();
                if (r.height > 0 && r.width > 0) {
                    lastBottom = Math.max(lastBottom, r.bottom - er.top + el.scrollTop);
                }
            });
            out.boxes.push({
                tag: el.tagName.toLowerCase(),
                cls: (el.className || '').toString().slice(0, 70),
                clientHeight: el.clientHeight,
                scrollHeight: el.scrollHeight,
                contentBottom: Math.round(lastBottom),
                deadSpace: Math.round(el.scrollHeight - lastBottom),
            });
        }
    });
    return out;
}"""


def main():
    email = _seed()
    port = _free_port()
    log = REPO / "layout-probe-server.log"
    proc, base = _boot(port, log)
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_context(viewport=VIEWPORT).new_page()
            page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=60000)
            page.fill("#email", email)
            page.fill("#password", PASSWORD)
            try:
                page.click("#submit", force=True, no_wait_after=True)
            except TypeError:
                page.locator("#submit").dispatch_event("click")
            try:
                page.wait_for_url(lambda u: "/account/login" not in u, timeout=90000)
            except Exception:
                pass
            page.wait_for_timeout(1200)
            if "/account/login" in page.url:
                raise SystemExit("could not sign in")

            for path in ("/architecture-journey/",):
                page.goto(base + path, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1500)
                page.eval_on_selector_all(
                    "[x-show='showOnboarding']", "els => els.forEach(e => e.remove())"
                )
                page.wait_for_timeout(300)
                data = page.evaluate(PROBE)
                offenders = page.evaluate(OFFENDERS)
                print(f"\n=== {path} at {VIEWPORT['width']}x{VIEWPORT['height']} ===")
                print(f"  window.innerHeight        {data['viewport']}")
                print(f"  documentElement.scroll    {data['doc']}")
                print(f"  body.scrollHeight         {data['body']}")
                print("  scroll containers:")
                for b in data["boxes"]:
                    flag = "   <-- DEAD SPACE" if b["deadSpace"] > 120 else ""
                    print(f"    {b['tag']:6s} client={b['clientHeight']:5d} "
                          f"scroll={b['scrollHeight']:5d} content={b['contentBottom']:5d} "
                          f"dead={b['deadSpace']:5d}{flag}")
                    print(f"           class={b['cls']}")
                print("  elements extending past the viewport:")
                for o in offenders:
                    print(f"    {o['tag']:6s} pos={o['pos']:8s} top={o['top']:5d} "
                          f"bottom={o['bottom']:5d} h={o['height']:5d} id={o['id']}")
                    print(f"           class={o['cls']}")
                    print(f"           parent={o['parent']}")
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
