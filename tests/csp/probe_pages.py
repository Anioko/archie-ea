"""Pinpoint the exact Alpine expression that fails on given pages (local).

Instruments CSPExpr to (a) record every compiled source and (b) log the source
whose evaluation throws — so a page's "X is not a function" / parse error maps
to the offending expression. Runs against the local app (code is identical to
prod; parser/eval bugs are environment-independent).
"""
import os
import threading
import uuid
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = (ROOT / "app/static/js/csp/csp-evaluator.js").read_text(encoding="utf-8")

PAGES = sys.argv[1:] or [
    "/ai-chat/", "/strategic/investment-matrix", "/arb/change-requests/new",
    "/dashboard/rationalization", "/strategic/risk-assessment",
    "/dashboard/vendor-analysis/new", "/strategic/roadmap",
    "/ai-chat/entity-matching", "/codegen/workflow-designer",
]


def _boot():
    os.environ.setdefault("FLASK_CONFIG", "development")
    os.environ.setdefault("DATABASE_URL", "postgresql://postgres@127.0.0.1:5439/archie_test")
    os.environ.setdefault("SECRET_KEY", "devkey")
    from app import create_app
    app = create_app("development")
    app.config["WTF_CSRF_ENABLED"] = False
    return app


def _seed(app):
    from app import db
    from app.models.user import User
    from app.models.organization import Organization
    from werkzeug.security import generate_password_hash
    with app.app_context():
        org = Organization.query.first() or Organization(name="P", slug="p-" + uuid.uuid4().hex[:6])
        if not org.id:
            db.session.add(org)
            db.session.flush()
        u = User(email=f"probe-{uuid.uuid4().hex[:8]}@example.com", first_name="P", last_name="P",
                 confirmed=True, organization_id=org.id, is_platform_admin=True,
                 password_hash=generate_password_hash("x"))
        db.session.add(u)
        db.session.commit()
        return u.id


def main():
    from playwright.sync_api import sync_playwright
    from werkzeug.serving import make_server
    app = _boot()
    uid = _seed(app)
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    port = srv.socket.getsockname()[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            ctx = b.new_context()
            pg = ctx.new_page()
            with app.test_request_context():
                from flask import session as s
                s["_user_id"] = str(uid)
                s["_fresh"] = True
                from flask.sessions import SecureCookieSessionInterface
                cookie = SecureCookieSessionInterface().get_signing_serializer(app).dumps(dict(s))
            ctx.add_cookies([{"name": app.config.get("SESSION_COOKIE_NAME", "session"),
                              "value": cookie, "url": base}])

            # Intercept the evaluator script and append instrumentation, so the
            # PAGE'S OWN evaluator records which expression fails.
            INSTR = """
;(function(){ if(!window.CSPExpr) return; window.__cerr=[]; window.__perr=[];
  var C=window.CSPExpr.compile, R=window.CSPExpr.run;
  window.CSPExpr.compile=function(s){ try{ var a=C(s); try{a.__src=s;}catch(e){} return a; }
    catch(e){ window.__cerr.push([String(s).slice(0,400), String(e).slice(0,70)]); throw e; } };
  window.CSPExpr.run=function(a,sc){ try{ return R(a,sc); }
    catch(e){ window.__perr.push([((a&&a.__src)||'?').slice(0,400), String(e).slice(0,70)]); throw e; } };
})();
"""
            def handle(route):
                try:
                    resp = route.fetch()
                    body = resp.text() + INSTR
                    route.fulfill(response=resp, body=body)
                except Exception:
                    route.continue_()
            ctx.route("**/csp/csp-evaluator.js*", handle)

            for path in PAGES:
                try:
                    pg.goto(base + path, wait_until="domcontentloaded", timeout=20000)
                except Exception as e:
                    print(f"\n## {path}\n  NAV ERR {str(e)[:50]}")
                    continue
                pg.wait_for_timeout(1800)
                data = pg.evaluate("() => ({c: window.__cerr||[], p: window.__perr||[]})")
                print(f"\n## {path}")
                seen = set()
                for src, err in (data["c"] + data["p"]):
                    key = (src, err)
                    if key in seen:
                        continue
                    seen.add(key)
                    kind = "PARSE" if [x for x in data["c"] if x[0] == src] else "EVAL"
                    print(f"  {kind}: {src!r}\n     -> {err}")
                if not data["c"] and not data["p"]:
                    print("  (no CSPExpr errors captured — error may be non-evaluator)")
            b.close()
    finally:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
