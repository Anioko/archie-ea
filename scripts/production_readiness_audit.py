#!/usr/bin/env python
"""Exhaustive production-readiness audit of every reachable Archie surface.

The existing gates check the tree; the smoke tests check a dozen chosen journeys.
Neither looks at what a user actually gets on every page, which is how a page
shipped with 400px of dead space under its content and nothing went red.

This drives a real browser over every GET route the app exposes, as every
persona, at a desktop and a phone viewport, and records what it finds. It
measures rather than photographs: a screenshot that grows to fit its content
cannot show dead space, which is precisely the defect that reached the owner.

Levels, in increasing depth. Each is independently selectable with --level so a
failing area can be re-run in seconds:

  L0  route inventory      every rule in url_map, and whether it is reachable
  L1  http status          no 5xx, no unexpected 4xx for a permitted persona
  L2  render integrity     exactly one h1, no Jinja/Undefined leakage in the body
  L3  runtime errors       console errors and failed network requests
  L4  layout geometry      dead vertical space, horizontal overflow, offscreen content
  L5  forms and controls   every input labelled, every form has CSRF, controls named
  L6  accessibility        landmark structure (axe/focus remain in smoke CI)
  L7  link integrity       every in-app href resolves; no href="#" dead ends
  L8  authorisation        non-admin/admin outcomes on administration routes
  L9  data honesty         a rendered 0/—/placeholder that the API never measured
  L10 interaction outcomes activate safe controls from a fresh page; mutation
                           controls are classified for seeded journeys

Findings are written incrementally to the report path, so a killed run keeps
everything measured up to that point. Exit status is the number of
non-informational findings, capped at 250, so expected denials remain evidence
without making a clean audit permanently red.

    python scripts/production_readiness_audit.py
    python scripts/production_readiness_audit.py --level 4 --level 5
    python scripts/production_readiness_audit.py --persona business_architect
    python scripts/production_readiness_audit.py --route /architecture-journey/
    python scripts/production_readiness_audit.py --report audit.json --summary
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

REPO = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "AuditProbe!2026"

DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}

# One user per enterprise_role the sidebar and dashboard branch on. A surface that
# only ever gets audited as an admin is a surface whose permission handling is
# untested.
def _valid_roles():
    """The personas the PRODUCT defines, read from app/models/user.py.

    This list used to be hardcoded, and it had drifted badly: it audited four
    personas that do not exist in VALID_ROLES -- data_architect,
    technology_architect, security_architect, product_owner -- and skipped five
    that do, including arb_member, cto and platform_admin. So the audit spent a
    third of its run on fictional users while never once loading a page as an
    ARB member, and reported a coverage it did not have.

    Parsed rather than imported, for the same reason the journey-coverage gate
    parses it: an audit that needs the ORM to tell you which personas exist is
    an audit that cannot run until the app boots. Adding a persona to the
    product now adds it to this audit automatically.
    """
    import ast

    path = os.path.join(str(REPO), "app", "models", "user.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    constants, roles = {}, []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not node.targets:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            constants[target.id] = node.value.value
        elif target.id == "VALID_ROLES" and isinstance(node.value, ast.List):
            for element in node.value.elts:
                if isinstance(element, ast.Name) and element.id in constants:
                    roles.append(constants[element.id])
                elif isinstance(element, ast.Constant):
                    roles.append(element.value)
    if not roles:
        raise RuntimeError("could not read VALID_ROLES from app/models/user.py")
    return roles


PERSONAS = _valid_roles()

ALL_LEVELS = list(range(11))

# Routes that are correct to skip: they are not pages, or visiting them has an
# effect. Everything else is audited; the list is deliberately short and each
# entry says why.
SKIP_PREFIXES = (
    "/static/",          # assets, not pages
    "/api/",             # JSON; covered by the contract tests
    "/health",           # returns text, has no chrome
    "/account/logout",   # ends the session mid-audit
    "/admin/impersonate",  # switches identity mid-audit
    "/swagger",          # third-party UI
    "/apidocs",          # third-party Swagger UI: its markup is not ours to fix
    "/apispec",
    "/oauth2-redirect",  # Swagger UI's own file, not our markup
)
SKIP_SUBSTRINGS = (
    "/delete", "/remove", "/purge", "/reset", "/destroy",
    "/export", "/download", "/pdf",   # stream files, not pages
    # Both were recorded as high-severity navigation failures and neither is a
    # page: favicon.ico is an icon (the browser aborts the navigation), and an
    # OpenAPI spec route answers with a file download, which Playwright reports
    # as "Download is starting" rather than a load.
    "/favicon", "/openapi",
)


# --------------------------------------------------------------------------- setup

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def seed_personas():
    """One confirmed user per persona, in one organisation. Returns {role: email}."""
    sys.path.insert(0, str(REPO))
    from app import create_app, db
    from app.models.organization import Organization
    from app.models.user import Role, User

    app = create_app("testing")
    with app.app_context():
        db.create_all()
        Role.insert_roles()
        suffix = uuid.uuid4().hex[:8]
        org = Organization(name=f"Audit {suffix}", slug=f"audit-{suffix}")
        db.session.add(org)
        db.session.flush()
        architect_role = Role.query.filter_by(name="Architect").one()
        administrator_role = Role.query.filter_by(name="Administrator").one()
        emails = {}
        for role in PERSONAS:
            email = f"{role.replace('_', '-')}-{suffix}@example.com"
            user = User(
                email=email, first_name=role.split("_")[0].title(),
                last_name="Auditor", confirmed=True,
                organization_id=org.id, enterprise_role=role,
                role=administrator_role if role == "platform_admin" else architect_role,
                is_platform_admin=role == "platform_admin",
                is_org_admin=role == "platform_admin",
            )
            user.password = PASSWORD
            db.session.add(user)
            emails[role] = email
        db.session.commit()
        return emails


def collect_routes():
    """Every GET rule with no required parameters, plus its endpoint name.

    Rules with parameters are audited separately by substituting ids of rows the
    audit itself created, so a 404 is never mistaken for a broken page.
    """
    sys.path.insert(0, str(REPO))
    from app import create_app

    app = create_app("testing")
    routes = []
    for rule in app.url_map.iter_rules():
        if "GET" not in (rule.methods or set()):
            continue
        path = str(rule)
        if path.startswith(SKIP_PREFIXES) or any(s in path for s in SKIP_SUBSTRINGS):
            continue
        if rule.arguments:
            # Parameterised routes were skipped entirely, which hid a whole class
            # of defect: /architecture/adrs/<id> and /<id>/edit both rendered a
            # template directory that does not exist and 500ed on every request,
            # and the crawl could not see them because it only visited
            # parameterless rules.
            #
            # A substituted id usually addresses no real row, so a 404 here says
            # nothing and is not recorded (see `parameterised` below). A 5xx does:
            # a view that crashes before it can decide the row is missing is
            # broken regardless of which id you hand it.
            filled = _substitute_arguments(rule)
            if filled is None:
                continue
            routes.append({"path": filled, "endpoint": rule.endpoint,
                           "parameterised": True})
            continue
        routes.append({"path": path, "endpoint": rule.endpoint,
                       "parameterised": False})
    routes.sort(key=lambda r: r["path"])
    if _UNSAMPLED_CONVERTERS:
        print(f"note: no sample value for converter types "
              f"{sorted(_UNSAMPLED_CONVERTERS)}; routes using them were not audited")
    return routes


# Werkzeug converter -> a value that is well-formed for it. The row it addresses
# almost certainly does not exist; that is fine, because only 5xx is recorded for
# these routes.
# Keyed on Werkzeug's CLASS name lowercased with "Converter" stripped -- so
# IntegerConverter -> "integer", UnicodeConverter -> "unicode". Keying these on
# the URL spelling ("int", "string") instead silently matched nothing, and 413 of
# the 468 parameterised routes were skipped while the run still reported success.
_CONVERTER_SAMPLES = {
    "integer": "1",
    "float": "1.0",
    "unicode": "1",
    "path": "1",
    "uuid": "00000000-0000-0000-0000-000000000000",
}


_UNSAMPLED_CONVERTERS = set()


def _substitute_arguments(rule):
    """Build a concrete URL for a parameterised rule, or None if it cannot be."""
    import re as _re

    path = str(rule)
    for name, converter in (rule._converters or {}).items():
        kind = type(converter).__name__.replace("Converter", "").lower()
        if kind == "any":
            # An `any` converter only accepts its declared members, so pick one --
            # guessing anything else raises rather than 404ing.
            items = getattr(converter, "items", None)
            if not items:
                return None
            sample = sorted(items)[0]
        else:
            sample = _CONVERTER_SAMPLES.get(kind)
            if sample is None:
                _UNSAMPLED_CONVERTERS.add(kind)
                return None
        path = _re.sub(r"<[^<>:]*:?" + _re.escape(name) + r">", sample, path, count=1)
    if "<" in path:
        return None
    return path


def boot(port, log_path):
    env = dict(os.environ)
    env.setdefault("FLASK_CONFIG", "testing")
    url = env.get("TEST_DATABASE_URL") or env.get("DATABASE_URL")
    if url:
        env["DATABASE_URL"] = env["TEST_DATABASE_URL"] = url
    handle = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "manage", "run", "--no-reload",
         "--port", str(port)],
        cwd=str(REPO), env=env, stdout=handle, stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 300
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"server exited during boot; see {log_path}")
        try:
            urllib.request.urlopen(base + "/health", timeout=3)
            return proc, base
        except urllib.error.HTTPError:
            return proc, base
        except Exception:
            time.sleep(2)
    proc.terminate()
    raise SystemExit("server never became reachable")


# ------------------------------------------------------------------- in-page probes

# L2/L4/L5/L6/L7 all read the same DOM, so they run as one evaluate() per page
# rather than six round-trips. Each returns raw measurements; the decision about
# what counts as a finding is made in Python, where it can be reviewed.
PAGE_PROBE = r"""() => {
  const out = {};
  const vh = window.innerHeight, vw = window.innerWidth;

  // ---- L2 render integrity
  out.h1 = [...document.querySelectorAll('h1')].map(e => e.textContent.trim().slice(0, 80));
  out.title = document.title;
  const bodyText = document.body.innerText || '';
  // Jinja that failed to render leaks as literal delimiters or the word Undefined.
  out.templateLeak = [];
  [/\{\{\s*\w/, /\{%\s*\w/, /\bUndefined\b/, /\bNone\b\s*$/m].forEach((re) => {
    const m = bodyText.match(re);
    if (m) out.templateLeak.push(m[0].slice(0, 40));
  });
  // Three separate macros emit a breadcrumb nav (page_shell, page_header,
  // breadcrumb_nav). A page that calls two of them stacks two trails, so record
  // enough to say which macro produced which.
  const crumbEls = [...document.querySelectorAll(
      '[aria-label="Breadcrumb"], nav.breadcrumb, [data-testid="breadcrumb"]')];
  out.breadcrumbs = crumbEls.length;
  out.breadcrumbDetail = crumbEls.map(el => ({
    cls: (el.className || '').toString().slice(0, 50),
    text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 70),
  }));

  // ---- L4 layout geometry
  const doc = document.documentElement;
  out.geometry = {
    viewportHeight: vh, viewportWidth: vw,
    docScrollHeight: doc.scrollHeight,
    bodyScrollHeight: document.body.scrollHeight,
    docScrollWidth: doc.scrollWidth,
    horizontalOverflow: Math.max(0, doc.scrollWidth - vw),
  };
  // Dead space: for each scroll container, how far past its last painted child
  // it can still be scrolled.
  out.deadSpace = [];
  document.querySelectorAll('*').forEach((el) => {
    const cs = getComputedStyle(el);
    if (!/(auto|scroll)/.test(cs.overflowY)) return;
    if (el.scrollHeight <= el.clientHeight + 4) return;
    const er = el.getBoundingClientRect();
    let last = 0;
    el.querySelectorAll('*').forEach((c) => {
      const r = c.getBoundingClientRect();
      if (r.height > 0 && r.width > 0 && getComputedStyle(c).visibility !== 'hidden') {
        last = Math.max(last, r.bottom - er.top + el.scrollTop);
      }
    });
    const dead = Math.round(el.scrollHeight - last);
    if (dead > 120) {
      out.deadSpace.push({
        tag: el.tagName.toLowerCase(),
        cls: (el.className || '').toString().slice(0, 80),
        clientHeight: el.clientHeight, scrollHeight: el.scrollHeight,
        contentBottom: Math.round(last), dead,
      });
    }
  });
  // Elements painting outside the viewport horizontally: the classic mobile break.
  out.overflowing = [];
  document.querySelectorAll('body *').forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && (r.right > vw + 2 || r.left < -2)) {
      const cs = getComputedStyle(el);
      if (cs.position === 'fixed' || cs.visibility === 'hidden') return;
      out.overflowing.push({
        tag: el.tagName.toLowerCase(),
        cls: (el.className || '').toString().slice(0, 60),
        left: Math.round(r.left), right: Math.round(r.right),
      });
    }
  });
  out.overflowing = out.overflowing.slice(0, 6);

  // Which body-level children actually extend past the viewport? When
  // documentElement outgrows body, one of these is why.
  // Checking only body's direct children misses the usual cause: an absolutely
  // positioned element nested deeper whose containing block is the initial
  // containing block. It extends the document without being a body child.
  // A descendant of a scroll container does not extend the document, so those
  // are excluded -- their overflow is the container's to absorb.
  out.bodyOverflow = [];
  const inScroller = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (/(auto|scroll|hidden)/.test(cs.overflowY)) return true;
    }
    return false;
  };
  document.querySelectorAll('body *').forEach((el) => {
    const cs = getComputedStyle(el);
    if (cs.position === 'fixed' || cs.display === 'none') return;
    const r = el.getBoundingClientRect();
    if (r.height <= 0 || r.bottom <= vh + 4) return;
    if (inScroller(el)) return;
    out.bodyOverflow.push({
      tag: el.tagName.toLowerCase(),
      id: el.id || '',
      cls: (el.className || '').toString().slice(0, 70),
      pos: cs.position,
      top: Math.round(r.top), bottom: Math.round(r.bottom),
      height: Math.round(r.height),
      parent: el.parentElement
        ? el.parentElement.tagName.toLowerCase() + '.'
          + (el.parentElement.className || '').toString().slice(0, 40)
        : '',
    });
  });
  // Deepest-reaching first: the element defining the document's true bottom.
  out.bodyOverflow.sort((a, b) => b.bottom - a.bottom);
  out.bodyOverflow = out.bodyOverflow.slice(0, 5);

  // ---- L5 forms and controls
  const named = (el) => {
    if (el.getAttribute('aria-label')) return true;
    if (el.getAttribute('aria-labelledby')) return true;
    if (el.getAttribute('title')) return true;
    if (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) return true;
    if (el.closest('label')) return true;
    if (el.type === 'hidden' || el.type === 'submit' || el.type === 'button') return true;
    return false;
  };
  out.unlabelledInputs = [];
  document.querySelectorAll('input, select, textarea').forEach((el) => {
    if (!named(el)) {
      out.unlabelledInputs.push({
        tag: el.tagName.toLowerCase(), type: el.type || '',
        name: el.name || '', id: el.id || '',
      });
    }
  });
  out.unlabelledInputs = out.unlabelledInputs.slice(0, 10);
  out.unnamedButtons = [];
  document.querySelectorAll('button, [role="button"]').forEach((el) => {
    const label = (el.textContent || '').trim() || el.getAttribute('aria-label')
                  || el.getAttribute('title') || '';
    if (!label) out.unnamedButtons.push((el.className || '').toString().slice(0, 60));
  });
  out.unnamedButtons = out.unnamedButtons.slice(0, 10);
  // Every POST form needs a CSRF token; a missing one is a 400 the moment a user submits.
  out.formsMissingCsrf = [];
  document.querySelectorAll('form').forEach((f) => {
    const method = (f.getAttribute('method') || 'get').toLowerCase();
    if (method !== 'post') return;
    if (!f.querySelector('input[name="csrf_token"], input[name="_csrf_token"]')) {
      out.formsMissingCsrf.push(f.getAttribute('action') || '(no action)');
    }
  });
  // Checkboxes and radios specifically: the owner called these out.
  out.checkboxes = document.querySelectorAll('input[type=checkbox], input[type=radio]').length;
  out.checkboxesUnlabelled = [...document.querySelectorAll('input[type=checkbox], input[type=radio]')]
      .filter(el => !named(el)).length;

  // Full visible-control inventory. This is evidence, not a claim that the
  // action works: outcome journeys consume the inventory and prove navigation,
  // modal, download, mutation, feedback and persistence separately. Never
  // capture input values; reports may be retained as CI artifacts.
  const controlVisible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (el.hidden || el.getAttribute('aria-hidden') === 'true') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const controlLabel = (el) => {
    const labelledBy = el.getAttribute('aria-labelledby');
    const labelled = labelledBy && document.getElementById(labelledBy);
    const associated = el.labels && el.labels.length
      ? [...el.labels].map(label => label.textContent || '').join(' ')
      : '';
    const editable = el.matches('input, textarea, [contenteditable="true"]');
    return (el.getAttribute('aria-label')
      || (labelled && labelled.textContent)
      || associated
      || (!editable && el.textContent)
      || el.getAttribute('title')
      || '').replace(/\s+/g, ' ').trim().slice(0, 120);
  };
  const safePath = (raw) => {
    if (!raw) return '';
    try {
      const parsed = new URL(raw, document.baseURI);
      return parsed.origin === location.origin
        ? parsed.pathname
        : parsed.origin + parsed.pathname;
    } catch (_) {
      return String(raw).split(/[?#]/, 1)[0];
    }
  };
  out.controls = [];
  const controlNodes = new Set(document.querySelectorAll(
    'a[href], button, input:not([type="hidden"]), select, textarea, summary, '
    + '[role="button"], [role="link"], [contenteditable="true"], '
    + '[tabindex]:not([tabindex="-1"])'));
  let controlOrdinal = 0;
  for (const el of controlNodes) {
    if (!controlVisible(el)) continue;
    const handlers = {};
    for (const attr of el.attributes || []) {
      if (/^(?:@click(?:\.[\w-]+)*|x-on:click(?:\.[\w-]+)*|onclick|data-(?:action|.*-action|modal-.*|confirm|autosubmit|toggle|dismiss.*))$/.test(attr.name)) {
        handlers[attr.name] = String(attr.value || '').slice(0, 160);
      }
    }
    const form = el.closest('form');
    out.controls.push({
      ordinal: controlOrdinal++,
      tag: el.tagName.toLowerCase(),
      editable: el.matches('input, select, textarea, [contenteditable="true"]'),
      type: el.getAttribute('type') || '',
      role: el.getAttribute('role') || '',
      label: controlLabel(el),
      id: el.id || '',
      testid: el.getAttribute('data-testid') || '',
      href: safePath(el.getAttribute('href') || ''),
      disabled: Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true'),
      form_method: form ? (form.getAttribute('method') || 'get').toLowerCase() : '',
      form_action: form ? safePath(form.getAttribute('action') || '') : '',
      handlers,
    });
  }

  // ---- L7 link integrity
  out.deadLinks = [];
  document.querySelectorAll('a').forEach((a) => {
    const href = a.getAttribute('href');
    const text = (a.textContent || '').trim().slice(0, 40);
    if (href === null || href === '' || href === '#') {
      // A '#' href with a click handler or Alpine binding is a real control.
      if (a.hasAttribute('@click') || a.hasAttribute('x-on:click')
          || a.hasAttribute('onclick') || a.hasAttribute('data-bs-toggle')) return;
      out.deadLinks.push({ href: String(href), text });
    }
  });
  out.deadLinks = out.deadLinks.slice(0, 10);
  out.internalLinks = [...new Set([...document.querySelectorAll('a[href^="/"]')]
      .map(a => a.getAttribute('href'))
      .filter(h => h && !h.startsWith('//')))].slice(0, 40);

  // ---- L6 landmark structure
  out.landmarks = {
    main: document.querySelectorAll('main, [role=main]').length,
    nav: document.querySelectorAll('nav, [role=navigation]').length,
  };

  // ---- L9 data honesty: a metric slot still showing its loading placeholder
  // after the page settled means a fetch failed silently.
  out.stuckPlaceholders = [...document.querySelectorAll('[data-metric], [data-testid$="-value"]')]
      .filter(el => /^(\.\.\.|loading|--)$/i.test((el.textContent || '').trim()))
      .map(el => el.getAttribute('data-metric') || el.getAttribute('data-testid'))
      .slice(0, 10);

  return out;
}"""


def evaluate_findings(level_set, ctx, probe, status, console_errors, failed_requests):
    """Turn raw measurements into findings. Kept in Python so each rule is reviewable."""
    f = []

    def add(level, kind, detail, severity="high"):
        f.append({**ctx, "level": level, "kind": kind, "detail": detail,
                  "severity": severity})

    if 1 in level_set:
        if status == 503:
            # A declared, structured "service unavailable" is a designed state --
            # the AI surfaces return it with an actionable admin message when no
            # provider is configured. Flagging it as a crash buries real 500s.
            add(1, "service-unavailable", f"HTTP {status}", severity="info")
        elif status >= 500:
            add(1, "server-error", f"HTTP {status}")
        elif status == 404:
            # Some routes abort(404) deliberately when their feature is not
            # configured -- SAML does this so an unconfigured IdP is not
            # advertised. That is a defensible posture, so this is reported for
            # review rather than treated as a broken page.
            add(1, "not-found",
                f"HTTP {status} on a registered route: either a broken page or a "
                f"feature deliberately hidden while unconfigured",
                severity="medium")
        elif status in (401, 403):
            add(1, "forbidden", f"HTTP {status}", severity="info")

    if 8 in level_set:
        is_admin_surface = (
            ctx.get("route", "").startswith("/admin")
            or ctx.get("endpoint", "").startswith("admin.")
        )
        if is_admin_surface:
            is_platform_admin = ctx.get("persona") == "platform_admin"
            if status in (401, 403) and is_platform_admin:
                add(8, "unexpected-forbidden",
                    "platform administrator was denied an administration surface")
            elif status < 400 and not is_platform_admin:
                add(8, "unauthorized-access",
                    "non-administrator could render an administration surface")
            elif status in (401, 403):
                add(8, "expected-forbidden",
                    "non-administrator was correctly denied", severity="info")

    if 2 in level_set and status < 400:
        n = len(probe.get("h1") or [])
        if n == 0:
            add(2, "no-h1", "page has no <h1>; screen readers get no page name")
        elif n > 1:
            add(2, "multiple-h1", f"{n} <h1> elements: {probe['h1'][:3]}")
        if not (probe.get("title") or "").strip():
            add(2, "no-title", "empty <title>", severity="medium")
        for leak in probe.get("templateLeak") or []:
            add(2, "template-leak", f"unrendered template or placeholder text: {leak!r}")
        if (probe.get("breadcrumbs") or 0) > 1:
            add(2, "duplicate-breadcrumbs",
                f"{probe['breadcrumbs']} breadcrumb navs: "
                f"{probe.get('breadcrumbDetail')}", severity="medium")

    if 3 in level_set and status < 400:
        for msg in console_errors[:5]:
            add(3, "console-error", msg[:200])
        for req in failed_requests[:5]:
            add(3, "failed-request", req)

    if 4 in level_set and status < 400:
        for box in probe.get("deadSpace") or []:
            add(4, "dead-space",
                f"{box['dead']}px of empty scroll below content in "
                f"{box['tag']}.{box['cls']} (content ends {box['contentBottom']}, "
                f"scrolls to {box['scrollHeight']})")
        geo = probe.get("geometry") or {}
        if geo.get("horizontalOverflow", 0) > 2:
            add(4, "horizontal-overflow",
                f"page scrolls {geo['horizontalOverflow']}px sideways; "
                f"offenders: {probe.get('overflowing')[:3]}")
        # documentElement taller than body means something escapes the shell.
        if geo.get("docScrollHeight", 0) > geo.get("bodyScrollHeight", 0) + 40:
            culprits = probe.get("bodyOverflow") or []
            named = "; ".join(
                f"<{c['tag']}{'#' + c['id'] if c['id'] else ''} class={c['cls']!r} "
                f"pos={c['pos']} h={c['height']}>"
                for c in culprits[:3]
            ) or "no body-level child overflows: check margins on the shell itself"
            add(4, "document-overflow",
                f"documentElement scrolls to {geo['docScrollHeight']} but body is "
                f"{geo['bodyScrollHeight']} at viewport {geo['viewportHeight']}; "
                f"escaping the shell: {named}")

    if 5 in level_set and status < 400:
        for el in probe.get("unlabelledInputs") or []:
            add(5, "unlabelled-input",
                f"<{el['tag']} type={el['type']} name={el['name']!r}> has no label")
        for cls in probe.get("unnamedButtons") or []:
            add(5, "unnamed-button", f"button with no accessible name: .{cls}")
        for action in probe.get("formsMissingCsrf") or []:
            add(5, "form-missing-csrf",
                f"POST form to {action} has no csrf_token; submitting it 400s")
        if probe.get("checkboxesUnlabelled"):
            add(5, "unlabelled-checkbox",
                f"{probe['checkboxesUnlabelled']} of {probe['checkboxes']} "
                f"checkboxes/radios have no label")

    if 6 in level_set and status < 400:
        lm = probe.get("landmarks") or {}
        if lm.get("main", 0) == 0:
            add(6, "no-main-landmark", "no <main>; keyboard users cannot skip nav",
                severity="medium")
        elif lm.get("main", 0) > 1:
            add(6, "multiple-main", f"{lm['main']} <main> landmarks", severity="medium")

    if 7 in level_set and status < 400:
        for link in probe.get("deadLinks") or []:
            add(7, "dead-link",
                f"anchor {link['text']!r} has href={link['href']!r} and no handler",
                severity="medium")

    if 9 in level_set and status < 400:
        for slot in probe.get("stuckPlaceholders") or []:
            add(9, "stuck-placeholder",
                f"metric {slot!r} still shows its loading placeholder after settle; "
                f"a fetch failed without telling the user")

    return f


def blocking_findings(findings):
    """Return only actionable defects; retain informational evidence in reports."""
    return [finding for finding in findings if finding.get("severity") != "info"]


# The selector deliberately matches PAGE_PROBE's control inventory. Outcome
# ordinals are therefore stable when a fresh page renders the same state.
CONTROL_SELECTOR = (
    'a[href], button, input:not([type="hidden"]), select, textarea, summary, '
    '[role="button"], [role="link"], [contenteditable="true"], '
    '[tabindex]:not([tabindex="-1"])'
)
_FIELD_TAGS = {"input", "select", "textarea"}
_MUTATION_WORDS = re.compile(
    r"\b(save|submit|delete|remove|purge|destroy|archive|restore|approve|reject|"
    r"create|update|import|upload|synchroni[sz]e|sync|execute|generate|provision|"
    r"publish|send|invite|assign|unassign|revoke|rotate|reset|logout|log\s*out|"
    r"sign\s*out|impersonate|switch\s+(?:user|tenant|organi[sz]ation))\b",
    re.IGNORECASE,
)


def classify_control_for_outcome(control):
    """Return (classification, reason) without pretending unsafe clicks passed."""
    tag = (control.get("tag") or "").lower()
    if tag in _FIELD_TAGS or control.get("editable"):
        return "field", "editable fields require a form-specific seeded journey"
    if control.get("disabled"):
        return "disabled", "control is intentionally unavailable in this state"

    method = (control.get("form_method") or "").lower()
    evidence = " ".join([
        control.get("label") or "",
        control.get("href") or "",
        control.get("form_action") or "",
        " ".join((control.get("handlers") or {}).values()),
    ])
    if method not in ("", "get") or _MUTATION_WORDS.search(evidence):
        return (
            "dedicated-seeded-journey",
            "may mutate data or external state; verify persistence in an isolated fixture",
        )
    return "safe", "read-only navigation or client-side interaction"


def control_outcome_fingerprint(control, path):
    """Reuse identical navigation evidence; keep page-local controls contextual."""
    href = control.get("href") or ""
    if (control.get("tag") or "").lower() == "a" and href:
        return ("navigation", href)
    return (
        "page-control", path, control.get("tag") or "", control.get("id") or "",
        control.get("testid") or "", control.get("label") or "",
        tuple(sorted((control.get("handlers") or {}).items())),
    )


_OUTCOME_SNAPSHOT = r"""() => {
  const visible = (el) => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden'
      && !el.hidden && rect.width > 0 && rect.height > 0;
  };
  const state = [...document.querySelectorAll(
      'dialog, [role="dialog"], [aria-expanded], [aria-selected], details, [open], '
      + '[role="alert"], [role="status"], [aria-live]')]
    .map((el) => [el.tagName, el.id || '', el.getAttribute('role') || '',
      el.getAttribute('aria-expanded') || '', el.getAttribute('aria-selected') || '',
      el.hasAttribute('open'), visible(el), (el.textContent || '').trim().slice(0, 120)]);
  // Do not compare all page text: clocks and background metric refreshes would
  // make a dead button look successful. Structural visibility still captures
  // reveals, collapses, inserted toasts and modal changes without that noise.
  const structure = [...document.querySelectorAll('body *')]
    .map((el) => [el.tagName, el.id || '', el.getAttribute('role') || '',
      (el.className || '').toString().slice(0, 120), el.hidden, visible(el),
      el.getAttribute('aria-expanded') || '', el.getAttribute('aria-selected') || '',
      el.hasAttribute('open')]);
  return {state, structure, scrollX: window.scrollX, scrollY: window.scrollY};
}"""


def _safe_url(raw):
    """Remove query strings and fragments from retained audit evidence."""
    parsed = urllib.parse.urlsplit(raw or "")
    prefix = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    return prefix + parsed.path


def probe_control_outcome(page, visible_ordinal, settle_ms=700):
    """Activate one visible control and report only an observed browser outcome.

    Non-GET requests are aborted before leaving the browser. The caller can then
    route that control into a seeded persistence journey without changing audit
    data merely by discovering what the control does.
    """
    before_url = page.url
    before = page.evaluate(_OUTCOME_SNAPSHOT)
    downloads, popups, requests, blocked = [], [], [], []

    page.on("download", lambda download: downloads.append(download.suggested_filename))
    page.on("popup", lambda popup: popups.append(_safe_url(popup.url)))
    page.on("response", lambda response: requests.append({
        "method": response.request.method,
        "status": response.status,
        "url": _safe_url(response.url),
        "main_navigation": (response.request.is_navigation_request()
                            and response.frame == page.main_frame),
    }))

    def guard(route, request):
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            blocked.append({"method": request.method, "url": _safe_url(request.url)})
            route.abort()
        else:
            route.continue_()

    page.route("**/*", guard)
    try:
        elements = page.query_selector_all(CONTROL_SELECTOR)
        visible = [element for element in elements if element.is_visible()]
        if visible_ordinal >= len(visible):
            return {"status": "not-found", "outcome": "control-not-reproducible"}
        visible[visible_ordinal].click(no_wait_after=True, timeout=5000)
        page.wait_for_timeout(settle_ms)
    except Exception as exc:
        if blocked:
            return {
                "status": "dedicated-seeded-journey",
                "outcome": "blocked-non-get-request",
                "detail": blocked,
            }
        return {"status": "activation-failed", "outcome": "exception", "detail": str(exc)[:200]}
    finally:
        page.unroute("**/*", guard)

    if blocked:
        return {
            "status": "dedicated-seeded-journey",
            "outcome": "blocked-non-get-request",
            "detail": blocked,
        }
    if downloads:
        return {"status": "verified", "outcome": "download", "detail": downloads}
    if popups:
        return {"status": "verified", "outcome": "popup", "detail": popups}
    if _safe_url(page.url) != _safe_url(before_url):
        navigation_responses = [item for item in requests if item["main_navigation"]]
        if not navigation_responses:
            return {"status": "activation-failed", "outcome": "navigation-unconfirmed"}
        destination_status = navigation_responses[-1]["status"]
        if destination_status >= 400:
            return {
                "status": "activation-failed", "outcome": "navigation-http-error",
                "http_status": destination_status, "detail": _safe_url(page.url),
            }
        return {"status": "verified", "outcome": "navigation", "detail": _safe_url(page.url)}

    after = page.evaluate(_OUTCOME_SNAPSHOT)
    successful_get = any(
        request["method"] == "GET" and request["status"] < 400 for request in requests
    )
    if successful_get and after != before:
        return {"status": "verified", "outcome": "request-with-feedback"}
    if after != before:
        return {"status": "verified", "outcome": "visible-state-change"}
    return {"status": "no-observable-outcome", "outcome": "none"}


# ------------------------------------------------------------------------- driving

def run(args):
    level_set = set(args.level or ALL_LEVELS)
    emails = seed_personas()
    routes = collect_routes()
    if args.route:
        wanted = set(args.route)
        routes = [r for r in routes if r["path"] in wanted or
                  any(r["path"].startswith(w) for w in wanted)]
    personas = args.persona or PERSONAS
    viewports = [("desktop", DESKTOP)] + ([] if args.desktop_only else [("mobile", MOBILE)])

    report_path = pathlib.Path(args.report)
    findings, control_inventory, control_outcomes, audited = [], [], [], 0

    def flush():
        report_path.write_text(json.dumps({
            "levels": sorted(level_set),
            "routes_total": len(routes),
            "routes_audited": audited,
            "personas": personas,
            "control_inventory": control_inventory,
            "control_outcomes": control_outcomes,
            "findings": findings,
        }, indent=2), encoding="utf-8")

    def retain_control_outcome(record):
        control_outcomes.append(record)
        # A full route can expose hundreds of controls. Persist inside that
        # route so a timeout retains the completed activations, not merely the
        # inventory captured before they began.
        if len(control_outcomes) % 25 == 0:
            flush()

    port = _free_port()
    proc, base = boot(port, REPO / "audit-server.log")
    print(f"server up on {base}; {len(routes)} routes x {len(personas)} personas "
          f"x {len(viewports)} viewports", flush=True)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for role in personas:
                email = emails[role]
                for vp_name, vp in viewports:
                    context = browser.new_context(viewport=vp)
                    page = context.new_page()
                    tested_outcomes = {}

                    console_errors, failed_requests = [], []
                    page.on("console", lambda m: console_errors.append(m.text)
                            if m.type == "error" else None)
                    page.on("response", lambda r: failed_requests.append(
                        f"{r.status} {r.url[:120]}") if r.status >= 400 else None)

                    # Sign in once per context.
                    page.goto(base + "/account/login", wait_until="domcontentloaded",
                              timeout=60000)
                    page.fill("#email", email)
                    page.fill("#password", PASSWORD)
                    page.locator("#submit").click(force=True, no_wait_after=True)
                    try:
                        page.wait_for_url(lambda u: "/account/login" not in u, timeout=60000)
                    except Exception:
                        pass
                    page.wait_for_timeout(800)
                    if "/account/login" in page.url:
                        findings.append({
                            "level": 0, "kind": "login-failed", "persona": role,
                            "viewport": vp_name, "route": "/account/login",
                            "severity": "high",
                            "detail": "could not sign in; every route below is unaudited",
                        })
                        context.close()
                        flush()
                        continue

                    for route in routes:
                        path = route["path"]
                        ctx = {"route": path, "endpoint": route["endpoint"],
                               "persona": role, "viewport": vp_name}
                        console_errors.clear()
                        failed_requests.clear()
                        try:
                            # Retried once, deliberately. The server is reachable
                            # (boot() waited on /health) but the FIRST real page
                            # load still pays the whole lazy-import cost, so a
                            # cold start was being recorded as a high-severity
                            # navigation failure against whichever route happened
                            # to go first -- /dashboard/health, which loads in
                            # 0.24s and reaches domcontentloaded fine on a second
                            # attempt. An audit whose first three findings are
                            # noise is an audit people learn to ignore
                            # (TESTING_STANDARD.md, rule 8). A genuine hang fails
                            # both times; a cold start does not.
                            try:
                                resp = page.goto(base + path, wait_until="domcontentloaded",
                                                 timeout=45000)
                            except Exception:
                                resp = page.goto(base + path, wait_until="domcontentloaded",
                                                 timeout=45000)
                            status = resp.status if resp else 0
                            ctype = ""
                            if resp:
                                ctype = (resp.headers or {}).get("content-type", "")
                            if route.get("parameterised") and status in (403, 404, 410):
                                # Substituted id addresses no real row. Checked
                                # before the content-type branch, which otherwise
                                # reports JSON 404s the suppression would drop.
                                audited += 1
                                continue
                            if "html" not in ctype.lower():
                                # JSON/text endpoint reachable by GET. Not a page:
                                # only its status is meaningful here, and its body
                                # contract is covered by the API tests.
                                findings.extend(evaluate_findings(
                                    level_set & {1}, ctx, {}, status, [], []))
                                audited += 1
                                continue
                            page.wait_for_timeout(args.settle)
                            # The onboarding overlay covers content and is not the
                            # subject of the audit; dismiss it rather than measure it.
                            page.eval_on_selector_all(
                                "[x-show='showOnboarding'], .onboarding-overlay",
                                "els => els.forEach(e => e.remove())")
                            probe = page.evaluate(PAGE_PROBE)
                            control_inventory.append({
                                **ctx,
                                "status": status,
                                "controls": probe.get("controls") or [],
                            })

                            # L10 never treats handler presence as proof. Each
                            # safe non-field control is activated from a fresh
                            # page; unsafe controls are explicitly assigned to
                            # isolated persistence journeys without clicking.
                            if 10 in level_set and (
                                status < 400 and not route.get("parameterised")
                            ):
                                for control in probe.get("controls") or []:
                                    classification, reason = classify_control_for_outcome(control)
                                    outcome_record = {
                                        **ctx,
                                        "control": control,
                                        "classification": classification,
                                        "reason": reason,
                                    }
                                    if classification != "safe":
                                        retain_control_outcome(outcome_record)
                                        continue

                                    fingerprint = control_outcome_fingerprint(control, path)
                                    if fingerprint in tested_outcomes:
                                        outcome_record.update(tested_outcomes[fingerprint])
                                        outcome_record["evidence_reused"] = True
                                        retain_control_outcome(outcome_record)
                                        continue

                                    outcome_page = context.new_page()
                                    try:
                                        outcome_page.goto(
                                            base + path,
                                            wait_until="domcontentloaded",
                                            timeout=45000,
                                        )
                                        outcome_page.wait_for_timeout(args.settle)
                                        outcome_page.eval_on_selector_all(
                                            "[x-show='showOnboarding'], .onboarding-overlay",
                                            "els => els.forEach(e => e.remove())",
                                        )
                                        result = probe_control_outcome(
                                            outcome_page, control["ordinal"]
                                        )
                                    except Exception as exc:
                                        result = {
                                            "status": "activation-failed",
                                            "outcome": "exception",
                                            "detail": str(exc)[:200],
                                        }
                                    finally:
                                        outcome_page.close()

                                    outcome_record.update(result)
                                    tested_outcomes[fingerprint] = dict(result)
                                    if result["status"] == "dedicated-seeded-journey":
                                        outcome_record["classification"] = result["status"]
                                        outcome_record["reason"] = (
                                            "runtime attempted a non-GET request; verify in an "
                                            "isolated persistence journey"
                                        )
                                    retain_control_outcome(outcome_record)
                                    if result["status"] in {
                                        "no-observable-outcome", "activation-failed", "not-found"
                                    }:
                                        findings.append({
                                            **ctx,
                                            "level": 10,
                                            "kind": "control-no-outcome",
                                            "severity": "high",
                                            "detail": (
                                                f"{control.get('tag')} {control.get('label')!r} "
                                                f"({control.get('id') or control.get('testid') or control['ordinal']}) "
                                                f"produced {result['status']}: "
                                                f"{result.get('detail', result.get('outcome', ''))}"
                                            )[:500],
                                        })
                        except Exception as exc:
                            findings.append({**ctx, "level": 1, "kind": "navigation-failed",
                                             "severity": "high", "detail": str(exc)[:200]})
                            audited += 1
                            continue

                        active_levels = level_set
                        if route.get("parameterised") and status in (403, 404, 410):
                            # The substituted id addresses no real row. Not a defect.
                            active_levels = set()
                        findings.extend(evaluate_findings(
                            active_levels, ctx, probe, status,
                            list(console_errors), list(failed_requests)))
                        audited += 1
                        if audited % 25 == 0:
                            flush()
                            print(f"  {audited} audited, {len(findings)} findings",
                                  flush=True)

                    context.close()
                    flush()
                    print(f"finished {role}/{vp_name}: {len(findings)} findings so far",
                          flush=True)
            browser.close()
    finally:
        flush()
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()

    summarise(findings, audited, len(routes))
    return min(len(blocking_findings(findings)), 250)


def summarise(findings, audited, total):
    print()
    print(f"=== audited {audited} page loads over {total} routes ===")
    by_kind = {}
    for f in findings:
        by_kind.setdefault((f["level"], f["kind"]), []).append(f)
    if not by_kind:
        print("no findings")
        return
    for (level, kind), items in sorted(by_kind.items()):
        print(f"  L{level} {kind}: {len(items)}")
        for it in items[:3]:
            print(f"      {it['route']} [{it['persona']}/{it['viewport']}] "
                  f"{it['detail'][:120]}")
        if len(items) > 3:
            print(f"      ... and {len(items) - 3} more")
    print()
    print(f"TOTAL FINDINGS: {len(findings)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", type=int, action="append", choices=ALL_LEVELS,
                    help="run only these levels (repeatable); default is all")
    ap.add_argument("--persona", action="append", choices=PERSONAS,
                    help="audit as only these personas (repeatable)")
    ap.add_argument("--route", action="append",
                    help="audit only these route paths or prefixes (repeatable)")
    ap.add_argument("--desktop-only", action="store_true",
                    help="skip the 390px viewport pass")
    ap.add_argument("--settle", type=int, default=900,
                    help="ms to wait after load before measuring (default 900)")
    ap.add_argument("--report", default="production_readiness_report.json")
    args = ap.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
