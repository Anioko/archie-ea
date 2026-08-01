"""Harness for browser smoke journeys.

These render real pages in a real browser against a real database. That matters
because every cheaper layer of verification in this codebase has passed defects
the next layer caught:

  * static analysis passed a front end that never loaded, because the templates
    were valid and only the browser checks integrity hashes
  * route maps passed handlers that 500 on their first row, because an empty
    portfolio never enters the loop
  * HTTP 200 passed a compliance page rendering "Consumed: / Entitled:" with both
    numbers blank, because Jinja prints Undefined as empty string

So the assertions here are deliberately about what a user experiences: does the
page render, does the front end boot, is every control named, does anything
overflow, and does submitted work actually persist and appear where it should.

Skips cleanly when Playwright or a browser is unavailable, so `pytest -q` on a
developer machine is unaffected; CI installs Chromium and runs them for real.
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid

import pytest

pytest.importorskip("playwright", reason="playwright not installed - smoke journeys skipped")
from playwright.sync_api import sync_playwright  # noqa: E402

PASSWORD = "SmokeJourney!2026"
BOOT_TIMEOUT = int(os.environ.get("SMOKE_BOOT_TIMEOUT", "180"))


def _tail(path, lines=40):
    """Last *lines* of the server log - what actually failed, in its own words."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return "".join(fh.readlines()[-lines:])
    except Exception as exc:
        return "(could not read server log: %s)" % exc


class SmokeServer(str):
    """The base URL, plus the server log behind it.

    Subclasses str so every existing `live_server + path` still works, while
    giving a failing test somewhere to look.
    """

    def __new__(cls, base, log_path):
        obj = super().__new__(cls, base)
        obj.log_path = log_path
        return obj

    def tail(self, lines=40):
        return _tail(self.log_path, lines)


def _has_gunicorn():
    """gunicorn imports on Windows but cannot run there - it needs fcntl."""
    if sys.platform.startswith("win"):
        return False
    try:
        import gunicorn  # noqa: F401
        return True
    except Exception:
        return False


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server():
    """Boot the real application on a free port and yield its base URL.

    Runs the app as a subprocess rather than via the test client, because a test
    client cannot execute JavaScript, load a stylesheet or enforce Subresource
    Integrity - which is precisely the class of defect these journeys exist to
    catch.
    """
    port = _free_port()
    env = dict(os.environ)
    env.setdefault("SECRET_KEY", "smoke-only-not-secret-" + "x" * 16)
    env.setdefault("FLASK_CONFIG", "testing")
    env["FLASK_DEBUG"] = "0"
    # TestingConfig reads TEST_DATABASE_URL, not DATABASE_URL. Without this the
    # subprocess silently falls back to the default DSN on port 5432 and every
    # request 500s on "connection refused" - which surfaces as a browser timeout,
    # not as a database error.
    if env.get("TEST_DATABASE_URL") and not env.get("DATABASE_URL"):
        env["DATABASE_URL"] = env["TEST_DATABASE_URL"]
    if env.get("DATABASE_URL") and not env.get("TEST_DATABASE_URL"):
        env["TEST_DATABASE_URL"] = env["DATABASE_URL"]

    # Serve with gunicorn where it exists - which is CI and every deployment.
    #
    # Flask's development server cannot sustain these journeys: each dashboard
    # fires a dozen parallel API calls, and a single-process dev server queues
    # them until the browser gives up. That produced navigation timeouts on pages
    # that are perfectly healthy, and it also means the dev server is not what we
    # want to be asserting against - production runs gunicorn, so the smoke suite
    # should too.
    if _has_gunicorn():
        cmd = [sys.executable, "-m", "gunicorn", "manage:app",
               "--bind", "127.0.0.1:%d" % port,
               "--workers", "2", "--threads", "8",
               "--timeout", "120", "--graceful-timeout", "20",
               # No access log: one line per request, and the errors are what matter.
               "--error-logfile", "-"]
    else:                                   # Windows dev machines: no gunicorn
        cmd = [sys.executable, "-m", "flask", "--app", "manage", "run",
               "--host", "127.0.0.1", "--port", str(port), "--no-reload"]

    # Log to a FILE, never to a pipe.
    #
    # subprocess.PIPE with nothing draining it deadlocks the child as soon as the
    # 64 KB buffer fills. With --access-logfile that is roughly one journey: the
    # first test passed, the second filled the buffer, and every request after it
    # timed out on a server that was blocked writing a log line. A file also means
    # the server log survives to be printed when a test fails.
    log_path = os.path.join(tempfile.gettempdir(), "smoke-server-%d.log" % port)
    log_handle = open(log_path, "w+b")
    proc = subprocess.Popen(cmd, env=env, stdout=log_handle, stderr=subprocess.STDOUT)
    base = "http://127.0.0.1:%d" % port

    deadline = time.time() + BOOT_TIMEOUT
    while time.time() < deadline:
        if proc.poll() is not None:
            out = (proc.stdout.read() or b"").decode("utf-8", "replace")[-2500:]
            pytest.fail("app exited during boot:\n%s" % out)
        try:
            import urllib.error
            import urllib.request
            # Wait for a served response, not just a bound socket: this app takes
            # tens of seconds to finish importing, and a bound port only means
            # the listener exists.
            with urllib.request.urlopen(base + "/health", timeout=5):
                break
        except urllib.error.HTTPError:
            # /health reports 503 when Redis is absent, which is the normal state
            # in CI and locally. Any HTTP response means the app is serving; a
            # degraded dependency is not a reason to refuse to start testing.
            break
        except Exception:
            pass
        time.sleep(3)
    else:
        proc.kill()
        pytest.fail("app did not bind %s within %ss" % (base, BOOT_TIMEOUT))

    # Warm the first template render. Jinja compiles lazily and several services
    # import on first request, so a cold /account/login can take a minute on a
    # loaded machine - long enough to look like a hang rather than a slow start.
    try:
        import urllib.request
        urllib.request.urlopen(base + "/account/login", timeout=180).read()
    except Exception:
        pass

    # Prove the server the browser will talk to is actually serving, and say so.
    # A silent assumption here cost hours: the subprocess was reachable by urllib
    # and the failure surfaced only as an opaque browser navigation timeout.
    import urllib.request as _u
    try:
        with _u.urlopen(base + "/account/login", timeout=60) as r:
            print("[smoke] live_server ready at %s (login page HTTP %s)" % (base, r.status))
    except Exception as exc:
        print("[smoke] live_server at %s NOT serving: %s" % (base, exc))

    yield SmokeServer(base, log_path)

    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def seeded(live_server):
    """One organisation, one user per archetype, and the fixtures they need.

    Returns {archetype: email} plus the ids the journeys navigate to.

    Data is created through the ORM rather than the UI because several archetypes
    have no create path for their own entity - which was itself a finding - and a
    journey should not be blocked from testing a read screen by a missing write
    screen.
    """
    from app import create_app, db

    app = create_app("testing")
    suffix = uuid.uuid4().hex[:8]
    out = {"emails": {}, "ids": {}}

    with app.app_context():
        from app.models.application_owner import ApplicationOwner
        from app.models.application_portfolio import ApplicationComponent, VendorContract
        from app.models.organization import Organization
        from app.models.user import Role, User

        db.create_all()
        Role.insert_roles()
        role = Role.query.filter_by(name="Administrator").first() or Role.query.first()

        org = Organization(name="Smoke Org %s" % suffix, slug="smoke-%s" % suffix)
        db.session.add(org)
        db.session.commit()
        out["ids"]["org"] = org.id

        for archetype in ARCHETYPES:
            email = "smoke.%s.%s@example.com" % (archetype.replace("_", "-"), suffix)
            user = User(
                email=email, first_name="Smoke", last_name=archetype[:12],
                organization_id=org.id, enterprise_role=archetype, confirmed=True,
            )
            user.role = role
            user.password = PASSWORD
            db.session.add(user)
            db.session.commit()
            out["emails"][archetype] = email
            if archetype == "application_manager":
                out["ids"]["app_manager_user"] = user.id

        component = ApplicationComponent(
            name="Smoke Payroll %s" % suffix, organization_id=org.id,
            lifecycle_status="operational", description="Smoke fixture.",
        )
        db.session.add(component)
        db.session.commit()
        out["ids"]["application"] = component.id

        db.session.add(ApplicationOwner(
            user_id=out["ids"]["app_manager_user"], application_id=component.id,
            organization_id=org.id, ownership_type="primary",
        ))
        contract = VendorContract(
            organization_id=org.id, contract_name="Smoke MSA %s" % suffix,
            contract_number="SMOKE-%s" % suffix, status="active",
            contract_value=100000, start_date=__import__("datetime").date.today(),
        )
        db.session.add(contract)
        db.session.commit()
        out["ids"]["contract"] = contract.id

    return out


PAGE_TIMEOUT = int(os.environ.get("SMOKE_PAGE_TIMEOUT", "90000"))


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception as exc:                      # no browser binary in this env
            pytest.skip("chromium unavailable: %s" % str(exc)[:120])
        yield b
        b.close()


# The nine archetypes ENTERPRISE_ROLE_SECTION_MAP defines.
ARCHETYPES = [
    "solution_architect", "enterprise_architect", "business_architect",
    "arb_member", "portfolio_manager", "cto", "procurement",
    "application_manager", "platform_admin",
]
