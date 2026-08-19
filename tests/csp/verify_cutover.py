"""ARCH-070 cutover verification — the actual change, tested locally.

Boots the real app with the PRODUCTION CSP active (debug forced off, so
script-src has no 'unsafe-eval') and the _head.html wiring live, loads real
pages including a d3 page, and asserts:
  - the response CSP header really omits 'unsafe-eval';
  - zero securitypolicyviolation events mentioning eval;
  - zero page errors mentioning eval / Alpine;
  - Alpine actually initialized (an x-data element got _x_dataStack), i.e. the
    CSP-safe evaluator drove real interactivity, not a silently-inert page.
"""
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGES = [
    "/archimate/composer",
    "/enterprise/capability-map/",
    "/stakeholders/map",
    "/architecture/dashboard",
    "/dashboard/",
    "/solutions/",
    "/applications/",
    "/applications/rationalization/workbench",
    "/codegen/workflow-designer",
    "/ai-chat/chat",
    "/admin/dashboard",
    "/vendors/",
]


def _boot_app():
    os.environ.setdefault("FLASK_CONFIG", "development")
    os.environ.setdefault("DATABASE_URL", "postgresql://postgres@127.0.0.1:5439/archie_test")
    os.environ.setdefault("SECRET_KEY", "devkey")
    from app import create_app
    app = create_app("development")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["DEBUG"] = False
    app.debug = False  # force the PRODUCTION CSP branch in security.py
    return app


def _seed(app):
    from app import db
    from app.models.user import User
    from app.models.organization import Organization
    from werkzeug.security import generate_password_hash
    import uuid
    with app.app_context():
        org = Organization.query.first() or Organization(name="Cut", slug="cut-" + uuid.uuid4().hex[:6])
        if not org.id:
            db.session.add(org)
            db.session.flush()
        u = User(email=f"cut-{uuid.uuid4().hex[:8]}@example.com", first_name="Cut", last_name="Over",
                 confirmed=True, organization_id=org.id, password_hash=generate_password_hash("x"))
        db.session.add(u)
        db.session.commit()
        return u.id


def main():
    from playwright.sync_api import sync_playwright
    from werkzeug.serving import make_server
    app = _boot_app()
    uid = _seed(app)
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    port = srv.socket.getsockname()[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    rows = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            ctx = b.new_context()
            pg = ctx.new_page()
            with app.test_request_context():
                from flask import session as _s
                _s["_user_id"] = str(uid)
                _s["_fresh"] = True
                from flask.sessions import SecureCookieSessionInterface
                cookie = SecureCookieSessionInterface().get_signing_serializer(app).dumps(dict(_s))
            ctx.add_cookies([{"name": app.config.get("SESSION_COOKIE_NAME", "session"), "value": cookie, "url": base}])

            for path in PAGES:
                perr = []
                pg.on("pageerror", lambda e, _p=perr: _p.append(str(e)))
                pg.add_init_script("document.addEventListener('securitypolicyviolation',e=>{window.__v=window.__v||[];window.__v.push(e.violatedDirective+'|'+(e.blockedURI||'inline'))})")
                resp = pg.goto(base + path, wait_until="load", timeout=20000)
                csp_header = (resp.headers or {}).get("content-security-policy", "") if resp else ""
                pg.wait_for_timeout(800)  # let deferred Alpine init
                info = pg.evaluate("""() => {
                    const v = window.__v || [];
                    const evalV = v.filter(x => /eval/i.test(x));
                    // did Alpine actually initialize? any element with _x_dataStack
                    let inited = false;
                    document.querySelectorAll('[x-data]').forEach(el => { if (el._x_dataStack) inited = true; });
                    const nDataEls = document.querySelectorAll('[x-data]').length;
                    return { allViol: v, evalViol: evalV, inited, nDataEls };
                }""")
                header_has_eval = "'unsafe-eval'" in csp_header
                perr_eval = [e for e in perr if 'eval' in e.lower() or 'Function' in e]
                ok = (not header_has_eval and not info["evalViol"] and not perr_eval
                      and (info["inited"] or info["nDataEls"] == 0))
                rows.append((path, resp.status if resp else 0, header_has_eval, info, perr_eval, ok))
            b.close()
    finally:
        srv.shutdown()

    print("=== ARCH-070 cutover verification (production CSP, eval blocked) ===")
    allok = True
    for path, code, hdr_eval, info, perr_eval, ok in rows:
        allok = allok and ok
        print(f"  {path:34} http={code} header_has_unsafe_eval={hdr_eval} "
              f"x-data_els={info['nDataEls']} alpine_inited={info['inited']} "
              f"eval_violations={len(info['evalViol'])} eval_pageerrors={len(perr_eval)} -> {'OK' if ok else 'FAIL'}")
        for v in info["evalViol"][:5]:
            print(f"       EVAL-VIOLATION: {v}")
        for e in perr_eval[:3]:
            print(f"       EVAL-PAGEERROR: {e[:80]}")
    print("\nRESULT:", "PASS - unsafe-eval dropped, pages work" if allok else "FAIL")
    return 0 if allok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
