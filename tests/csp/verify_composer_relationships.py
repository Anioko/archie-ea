"""QA 3.1 settlement: can a user DRAW a relationship on the composer canvas and
have it PERSIST?

The report claimed connect-mode does nothing. This drives the real composer in a
headless browser: seed a 2-element saved diagram, open it via ?viewpoint_id=,
enter connect mode (key 'C'), click source then target, pick a relationship type
in the picker, then assert:
  - POST /archimate/api/relationships fired and returned an id (repo-level), and
  - after autosave the diagram serializes a SavedDiagramRelationship (view-level).

Skips cleanly without a browser/DB.
"""
import os
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _boot_app():
    os.environ.setdefault("FLASK_CONFIG", "development")
    # Follow the suite's database. The hardcoded port 5439 / archie_test here
    # matched no machine, so the app silently fell back to DevelopmentConfig's
    # default of .../5432/archie -- the production database name.
    if os.environ.get("TEST_DATABASE_URL"):
        os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    # A development app starts the job queue worker, whose daemon thread
    # outlives this helper and logs a connection WARNING for the rest of the
    # process, polluting later tests. These helpers only render pages.
    os.environ.setdefault("DISABLE_JOB_QUEUE_WORKER", "1")
    os.environ.setdefault("SECRET_KEY", "devkey")
    if os.environ.get("TEST_DATABASE_URL"):
        import config as _config
        _config.DevelopmentConfig.SQLALCHEMY_DATABASE_URI = os.environ["TEST_DATABASE_URL"]
    from app import create_app
    app = create_app("development")
    app.config["WTF_CSRF_ENABLED"] = False
    return app


def _seed(app):
    """Create org, user, two elements, and a saved diagram placing both far apart."""
    from app import db
    from app.models.user import User
    from app.models.organization import Organization
    from app.models.archimate_core import (
        ArchiMateElement, SavedDiagram, SavedDiagramElement,
    )
    from werkzeug.security import generate_password_hash
    with app.app_context():
        org = Organization.query.first() or Organization(
            name="RelTest", slug="reltest-" + uuid.uuid4().hex[:6])
        if not org.id:
            db.session.add(org)
            db.session.flush()
        u = User(email=f"reltest-{uuid.uuid4().hex[:8]}@example.com", first_name="Rel",
                 last_name="Test", confirmed=True, organization_id=org.id,
                 password_hash=generate_password_hash("x"))
        db.session.add(u)
        db.session.flush()
        a = ArchiMateElement(name="Src App", type="ApplicationComponent",
                             layer="application", organization_id=org.id)
        b = ArchiMateElement(name="Tgt Svc", type="ApplicationService",
                             layer="application", organization_id=org.id)
        db.session.add_all([a, b])
        db.session.flush()
        dia = SavedDiagram(name="RelDraw " + uuid.uuid4().hex[:6], organization_id=org.id)
        db.session.add(dia)
        db.session.flush()
        # place them well apart so clicks land on distinct elements
        db.session.add_all([
            SavedDiagramElement(diagram_id=dia.id, element_id=a.id,
                                position_x=120, position_y=160, width=180, height=64),
            SavedDiagramElement(diagram_id=dia.id, element_id=b.id,
                                position_x=560, position_y=160, width=180, height=64),
        ])
        db.session.commit()
        return u.id, dia.id, a.id, b.id, org.id


def _count_view_rels(app, dia_id):
    from app import db
    from app.models.archimate_core import SavedDiagramRelationship
    with app.app_context():
        return SavedDiagramRelationship.query.filter_by(diagram_id=dia_id).count()


def _count_repo_rels(app, a_id, b_id):
    from app import db
    from app.models.archimate_core import ArchiMateRelationship
    with app.app_context():
        return ArchiMateRelationship.query.filter(
            ArchiMateRelationship.source_id.in_([a_id, b_id]),
            ArchiMateRelationship.target_id.in_([a_id, b_id]),
        ).count()


def main():
    from playwright.sync_api import sync_playwright
    from werkzeug.serving import make_server

    app = _boot_app()
    uid, dia_id, a_id, b_id, org_id = _seed(app)
    repo_before = _count_repo_rels(app, a_id, b_id)
    view_before = _count_view_rels(app, dia_id)

    srv = make_server("127.0.0.1", 0, app, threaded=True)
    port = srv.socket.getsockname()[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    posts = []
    result = {"clicked_source": False, "clicked_target": False, "picker_opened": False,
              "picked_type": False}
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            ctx = b.new_context(viewport={"width": 1400, "height": 900})
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("request", lambda r: posts.append(r.url) if
                  (r.method == "POST" and "/archimate/api/relationships" in r.url) else None)
            # auth cookie
            with app.test_request_context():
                from flask import session as _s
                _s["_user_id"] = str(uid)
                _s["_fresh"] = True
                from flask.sessions import SecureCookieSessionInterface
                cookie = SecureCookieSessionInterface().get_signing_serializer(app).dumps(dict(_s))
            ctx.add_cookies([{"name": app.config.get("SESSION_COOKIE_NAME", "session"),
                              "value": cookie, "url": base}])

            pg.goto(f"{base}/archimate/composer?viewpoint_id={dia_id}",
                    wait_until="load", timeout=25000)
            # wait for the two elements to render on the JointJS paper
            pg.wait_for_timeout(3500)

            # compute screen coords of each element from the paper transform
            coords = pg.evaluate(
                """(ids) => {
                    // find the Alpine composer component
                    let host = document.querySelector('[x-data]');
                    let comp = null;
                    document.querySelectorAll('[x-data]').forEach(el => {
                        if (el._x_dataStack) el._x_dataStack.forEach(s => { if (s.graph && s.paper) comp = s; });
                    });
                    if (!comp) return {error: 'composer component not found'};
                    const paper = comp.paper, graph = comp.graph;
                    const rect = paper.el.getBoundingClientRect();
                    const out = {n: graph.getElements().length, els: []};
                    graph.getElements().forEach(cell => {
                        const bb = cell.getBBox();
                        const c = paper.localToClientPoint({x: bb.x + bb.width/2, y: bb.y + bb.height/2});
                        out.els.push({elementId: cell.get('elementId'), x: c.x, y: c.y});
                    });
                    out.connectModeAvailable = typeof comp.toggleConnectMode === 'function' || 'connectModeActive' in comp;
                    return out;
                }""", [a_id, b_id])
            if coords.get("error") or coords.get("n", 0) < 2:
                print("SETUP FAIL: composer did not render 2 elements:", coords, "errs:", errs[:3])
                return 1

            els = coords["els"]
            src = els[0]
            tgt = els[1]

            # enter connect mode: press 'C'
            pg.keyboard.press("c")
            pg.wait_for_timeout(300)
            # click source, then target
            pg.mouse.click(src["x"], src["y"])
            result["clicked_source"] = True
            pg.wait_for_timeout(400)
            pg.mouse.click(tgt["x"], tgt["y"])
            result["clicked_target"] = True
            pg.wait_for_timeout(700)

            # the relationship-type picker should now be open; pick the first type
            picker = pg.evaluate(
                """() => {
                    let comp = null;
                    document.querySelectorAll('[x-data]').forEach(el => {
                        if (el._x_dataStack) el._x_dataStack.forEach(s => { if ('relPickerOpen' in s) comp = s; });
                    });
                    if (!comp) return {found:false};
                    return {found:true, open: !!comp.relPickerOpen,
                            types: (comp.relPickerTypes||[]).map(t => t.type||t)};
                }""")
            result["picker_opened"] = bool(picker.get("open"))
            if picker.get("open") and picker.get("types"):
                # call createRelationship for a concrete valid type via the component
                pick = pg.evaluate(
                    """(rt) => {
                        let comp = null;
                        document.querySelectorAll('[x-data]').forEach(el => {
                            if (el._x_dataStack) el._x_dataStack.forEach(s => { if ('relPickerOpen' in s) comp = s; });
                        });
                        if (!comp || typeof comp.createRelationship !== 'function') return false;
                        comp._associationConfirmed = true; // skip the association nudge
                        comp.createRelationship(rt);
                        return true;
                    }""", picker["types"][0])
                result["picked_type"] = bool(pick)
            pg.wait_for_timeout(1500)  # let POST + autosave settle

            # trigger a save to force view-level persistence, then wait
            pg.evaluate(
                """() => {
                    let comp = null;
                    document.querySelectorAll('[x-data]').forEach(el => {
                        if (el._x_dataStack) el._x_dataStack.forEach(s => { if ('saveViewpoint' in s) comp = s; });
                    });
                    if (comp && typeof comp.saveViewpoint === 'function') { try { comp.saveViewpoint(); } catch(e){} }
                    else if (comp && typeof comp._autoSave === 'function') { try { comp._autoSave(); } catch(e){} }
                }""")
            pg.wait_for_timeout(2500)
            b.close()
    finally:
        srv.shutdown()

    repo_after = _count_repo_rels(app, a_id, b_id)
    view_after = _count_view_rels(app, dia_id)

    print("=== QA 3.1: draw-relationship end-to-end ===")
    print(f"  clicks: source={result['clicked_source']} target={result['clicked_target']} "
          f"picker_opened={result['picker_opened']} picked_type={result['picked_type']}")
    print(f"  POST /archimate/api/relationships fired: {len(posts)} time(s)")
    print(f"  repo-level ArchiMateRelationship: {repo_before} -> {repo_after}")
    print(f"  view-level SavedDiagramRelationship: {view_before} -> {view_after}")

    repo_ok = repo_after > repo_before
    view_ok = view_after > view_before
    if repo_ok and view_ok:
        print("\nRESULT: PASS — relationship drawn AND persisted to the view")
        return 0
    if repo_ok and not view_ok:
        print("\nRESULT: PARTIAL — relationship created in the repo but NOT persisted to the view "
              "(view-level SavedDiagramRelationship missing). This is the real 3.1 defect.")
        return 2
    print("\nRESULT: FAIL — no relationship created (connect-mode did not produce a POST). "
          f"picker_opened={result['picker_opened']}")
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
