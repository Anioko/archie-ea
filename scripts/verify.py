#!/usr/bin/env python
"""Archie verification runner — one command, every gate.

    python scripts/verify.py                # run every gate that can run here
    python scripts/verify.py --json         # machine-readable result
    python scripts/verify.py --gate compile # run one gate
    python scripts/verify.py --require-db   # turn DB-dependent SKIPs into failures (CI)
    python scripts/verify.py --update-baseline   # re-measure ratchets (see below)

Why this exists
---------------
``app/templates/macros/ZERO_TOLERANCE_PROTOCOL.md`` asks every agent to verify its
work against a mandatory protocol. A protocol document cannot enforce itself: at
the time this runner was written the repository had 8 test files and a CI lint step
reading ``ruff check . || true`` inside ``continue-on-error: true``. This script is
the executable form of that protocol — the thing you can actually run, and that CI
can actually fail on.

Gate kinds
----------
``zero``     the measurement must be exactly 0. Used only where the tree is
             already clean, so the gate can never be satisfied by regression.
``ratchet``  the measurement must not exceed a recorded baseline. This is how a
             tree with 4482 known lint findings and 1255 known token violations
             gets a meaningful gate today instead of after a multi-month cleanup:
             the number is allowed to fall, never to rise.
``command``  a subprocess that must exit 0.

Ratchets are stored in ``verification_baseline.json``. Lowering a baseline is
routine — run ``--update-baseline`` after a cleanup. *Raising* one is a deliberate
act that shows up in review as a changed number, which is the point.

Skips are loud
--------------
A gate that cannot run reports SKIP with a reason and is listed in the summary. It
never counts as a pass. CI passes ``--require-db`` so that a missing database
fails the build rather than quietly shrinking the gate set.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

def _force_utf8_console() -> None:
    """Make this script's own output survive a non-UTF-8 Windows console.

    On Windows ``sys.stdout.encoding`` follows the ANSI code page (cp1252 here)
    even when the terminal is set to UTF-8, so printing a gate's evidence text
    raises UnicodeEncodeError for anything outside cp1252 -- a check mark, a box
    rule -- and an em dash silently degrades to a mojibake byte. Either way the
    *reporting* of a result breaks the run, which is precisely backwards: a gate
    must never fail because of how its message is spelled. Reconfiguring to
    utf-8 with errors="replace" makes output lossy at worst, never fatal.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                # Redirected to something that cannot be reconfigured; the
                # caller still gets output, just in the original encoding.
                pass


REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / "verification_baseline.json"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

# The PostgreSQL-backed suite takes just over 30 minutes on the supported Windows
# development environment as of August 2026, and ~59 minutes on slower hardware.
#
# Two fixes for one defect met here and both are kept. Default 3600, so normal
# load variance does not report a progressing suite as a release failure. And
# overridable, because on a machine where the suite exceeds the ceiling the gate
# reported "timed out -> fix the failing test" on a tree with no failing test --
# which reads as a red release and is not one.
TEST_SUITE_TIMEOUT_SECONDS = int(os.environ.get("ARCHIE_TEST_SUITE_TIMEOUT", "3600"))


@dataclass
class Result:
    name: str
    status: str
    detail: str = ""
    measured: int | None = None
    baseline: int | None = None
    duration_s: float = 0.0
    remediation: str = ""


@dataclass
class Gate:
    name: str
    description: str
    kind: str                      # zero | ratchet | command
    runner: object
    needs_db: bool = False
    remediation: str = ""
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- helpers


def _run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    """Run *cmd* capturing output, decoding defensively.

    ``text=True`` alone decodes the child's output with the *parent's* locale
    encoding — cp1252 on a default Windows console — regardless of the child's
    PYTHONIOENCODING. Several commands here print non-cp1252 characters (the check
    marks in ``manage.py init_db``, for one), which raised UnicodeDecodeError inside
    subprocess's reader thread and left ``proc.stdout`` as None. Pinning utf-8 with
    errors="replace" makes a gate's *output* incapable of breaking the gate.
    """
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    # Normalise so callers can concatenate without a None check.
    proc.stdout = proc.stdout or ""
    proc.stderr = proc.stderr or ""
    return proc


def _ruff_count(select: str | None = None) -> tuple[int, str]:
    """Count ruff findings under the repo's pinned ruff.toml."""
    cmd = [sys.executable, "-m", "ruff", "check", ".", "--output-format", "concise"]
    if select:
        cmd += ["--select", select]
    proc = _run(cmd)
    if "error:" in proc.stderr.lower() and "Rule" in proc.stderr:
        raise RuntimeError(f"ruff rejected the selection: {proc.stderr.strip()[:200]}")
    lines = [ln for ln in proc.stdout.splitlines() if re.search(r":\d+:\d+:", ln)]
    sample = "\n".join(f"    {ln}" for ln in lines[:5])
    return len(lines), sample


def database_available() -> tuple[bool, str]:
    """TCP-probe the configured database. Cheap and dependency-free."""
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    if not url:
        return False, "neither TEST_DATABASE_URL nor DATABASE_URL is set"
    try:
        parsed = urlparse(url)
        host, port = parsed.hostname or "127.0.0.1", parsed.port or 5432
    except Exception as exc:  # noqa: BLE001
        return False, f"could not parse database URL: {exc}"
    sock = socket.socket()
    sock.settimeout(2.0)
    try:
        sock.connect((host, port))
        return True, f"{host}:{port} reachable"
    except OSError as exc:
        return False, f"{host}:{port} unreachable ({exc.__class__.__name__})"
    finally:
        sock.close()


# ---------------------------------------------------------------- gate runners


def gate_compile() -> Result:
    """The honest Python equivalent of a compile step: bytecode-compile everything.

    This is the strongest *ahead-of-time* guarantee the language offers. It proves
    every module is syntactically valid; it cannot prove a name exists (see the
    undefined-names gate) or that a template endpoint resolves (see boot-health).
    """
    proc = _run([sys.executable, "-m", "compileall", "-q", "app", "config.py", "manage.py", "create_admin.py"])
    if proc.returncode == 0:
        return Result("compile", PASS, "all modules compile")
    return Result("compile", FAIL, (proc.stdout + proc.stderr).strip()[:2000])


def gate_undefined_names(baseline: int) -> Result:
    """Ruff F821 — compiler-grade name resolution. Gated at ZERO.

    This is the closest thing to a compiler's symbol check available for Python,
    and it found real defects: 296 findings across 68 files when introduced,
    including entire route handlers that raised NameError on every request.

    All 296 are now resolved, so the gate is a hard zero rather than a ratchet —
    there is no remaining debt for a ratchet to protect. The `baseline` argument is
    kept for signature symmetry with the other gates but is deliberately ignored;
    any new undefined name fails the build.
    """
    count, sample = _ruff_count("F821")
    return Result("undefined-names", PASS if count == 0 else FAIL, sample, count, 0)


def gate_redefinitions(baseline: int) -> Result:
    """Ruff F811 — a name bound twice, where Python silently keeps the last one.

    Gated at ZERO. All 73 findings are resolved, and they were not cosmetic: they
    included two different implementations of analyze_file_data_for_preview (the
    older one dead), two OverviewForm classes with different base classes, a
    duplicated __repr__ that referenced fields its class did not have, and a `db`
    loop variable shadowing the SQLAlchemy session. `baseline` is retained for
    signature symmetry and deliberately ignored.
    """
    count, sample = _ruff_count("F811")
    return Result("redefinitions", PASS if count == 0 else FAIL, sample, count, 0)


def gate_undefined_exports() -> Result:
    """F822 — names in __all__ that do not exist. Already 0; locked at 0."""
    count, sample = _ruff_count("F822")
    return Result("undefined-exports", PASS if count == 0 else FAIL, sample, count, 0)


def gate_lint_core(baseline: int) -> Result:
    """Full pinned correctness set (F, E4, E7, E9). Gated at ZERO.

    Went from 4482 findings to zero. Four rules are disabled in ruff.toml with
    recorded evidence — E711/E712 because rewriting SQLAlchemy `== None` / `== True`
    silently deletes the predicate from the query, and E402 because reordering
    imports reintroduced a circular import and stopped the app booting. Everything
    else was fixed rather than suppressed. `baseline` is kept for signature symmetry
    and ignored.
    """
    count, sample = _ruff_count(None)
    return Result("lint-core", PASS if count == 0 else FAIL, sample, count, 0)


def gate_raw_fetch_sites(baseline: int) -> Result:
    """Raw fetch() call sites that bypass Platform.fetch - ratchet."""
    proc = _run([sys.executable, "scripts/check_raw_fetch.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("raw-fetch-sites", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    return Result("raw-fetch-sites", PASS if count <= baseline else FAIL,
                  "", count, baseline)


def gate_design_tokens_extended(baseline: int) -> Result:
    """Non-banned colour families (emerald/orange/teal/...) - their own ratchet."""
    proc = _run([sys.executable, "scripts/check_design_tokens.py", "--extended", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("design-tokens-extended", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    return Result("design-tokens-extended", PASS if count <= baseline else FAIL,
                  "", count, baseline)


def gate_design_tokens(baseline: int) -> Result:
    """DESIGN.md's colour-token rule, which nothing enforced before this."""
    proc = _run([sys.executable, "scripts/check_design_tokens.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("design-tokens", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    return Result("design-tokens", PASS if count <= baseline else FAIL, "", count, baseline)


def gate_shell_conformance(baseline: int) -> Result:
    """Pages hand-rolling their own header or page width.

    The 14 Aug 2026 UX audit found three competing header systems and two page
    widths shipping at once — the root cause of "every module looks different".
    Counted by scripts/check_shell_conformance.py; the escape hatch is a
    file-level `shell-ok: <reason>` comment.
    """
    proc = _run([sys.executable, "scripts/check_shell_conformance.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("shell-conformance", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    return Result("shell-conformance", PASS if count <= baseline else FAIL, "", count, baseline)


def gate_nav_verified(baseline: int) -> Result:
    """Routes a user can click that no test has ever exercised.

    Line coverage measures lines; this measures the unit a user actually
    touches. A route reachable from the sidebar that no test has ever loaded is
    unverified by definition — and it is the combination that hurts, because
    someone will find it by clicking.

    Counts from route_verification.json, written by running the suite with
    ``-p scripts.route_verification_audit``.

    Missing data fails, but says so rather than inventing a score. That file is
    untracked and exists in exactly one working copy, so on the same commit the
    repository root reported ``[18 > 0]`` while a fresh worktree reported
    ``[57 > 0]`` -- 57 being the entire navigation set, printed as though 57
    routes had been found wanting. No clean clone could ever pass. A gate is held
    to the rule it enforces: a number that means "not measured" is
    indistinguishable from one that was.
    """
    proc = _run([sys.executable, "scripts/route_verification_audit.py", "--count"])
    last = proc.stdout.strip().splitlines()[-1].strip() if proc.stdout.strip() else ""
    if last == "unmeasured":
        return Result(
            "nav-verified",
            FAIL,
            "no audit data in this checkout, so nothing was measured -- this is "
            "not a count of unverified routes.\n"
            "route_verification.json is untracked and exists only where the suite "
            "has been run.\n"
            "Produce it with:  pytest -p scripts.route_verification_audit",
        )
    try:
        count = int(last)
    except (ValueError, IndexError):
        return Result("nav-verified", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    if count > baseline:
        report = _run([sys.executable, "scripts/route_verification_audit.py"])
        details = report.stdout.strip() or report.stderr.strip()
        return Result("nav-verified", FAIL, details, count, baseline)
    return Result("nav-verified", PASS, "", count, baseline)


def gate_nav_coverage(baseline: int) -> Result:
    """Business-architecture outputs that have routes but no sidebar link.

    An evaluating business architect concluded capability maturity, gap
    analysis and strategy-to-execution "did not exist" in this product. All
    three ship — 350 routes serve them — but his persona's sidebar had four
    links, so nothing he could reach said so. A feature nobody can navigate to
    is, to the person evaluating the product, an absent feature; and the defect
    is invisible to every other gate, because the routes are registered, the
    templates parse and the endpoints resolve.

    Counted by scripts/ba_output_audit.py --count, which reads SIDEBAR_ZONES
    from app/utils/role_access.py (the real shell mechanism, imported rather
    than grepped, since the zones are built at import time) and checks each of
    the 12 outputs against every persona's links, labels and URL paths.
    """
    proc = _run([sys.executable, "scripts/ba_output_audit.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("nav-coverage", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/ba_output_audit.py to list them"
    return Result("nav-coverage", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_air_gap(baseline: int) -> Result:
    """No UI assets loaded from the public internet.

    Archie is being prepared for deployment inside an enterprise network, where
    public CDNs are blocked or proxied. Every external script is a page that breaks
    on a managed workstation. Also a privacy control: each request leaks the
    referring URL and client IP to a third party.
    """
    proc = _run([sys.executable, "scripts/check_external_origins.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("air-gap", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    return Result("air-gap", PASS if count <= baseline else FAIL, "", count, baseline)


def gate_control_labels(baseline: int) -> Result:
    """No button a screen reader announces as just "button".

    An icon-only button contributes no text, so without an aria-label the only
    way to learn what it does is to press it. A live browser audit of every
    route (Aug 2026) found 50, on close buttons, delete buttons and send
    buttons across the whole app.

    The gate exists rather than the cleanup alone because of the shape it also
    catches: /account/manage's notification toggles carried an
    `aria-labelledby` pointing at the `sr-only` checkbox rather than the visible
    <label>. It read like a deliberate, filed label and resolved to an empty
    name. Counted by scripts/check_control_labels.py, which follows the id.
    """
    proc = _run([sys.executable, "scripts/check_control_labels.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("control-labels", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_control_labels.py to list them"
    return Result("control-labels", PASS if count <= baseline else FAIL, detail, count, baseline)

def gate_alpine_await(baseline: int) -> Result:
    """No `await` / `async` inside an Alpine attribute expression.

    Pages are served under a CSP with no 'unsafe-eval', so Alpine expressions
    written in HTML attributes are executed by our own synchronous interpreter
    (app/static/js/csp/csp-evaluator.js), not by the browser. It cannot await:
    `await p` used to return the Promise object unchanged, so
    `this.total = await api.count()` left `total` holding a Promise and the
    template rendered the seeded initialiser. The strategic-roadmap and sprint
    statistic tiles sat on a fabricated `0` for months -- indistinguishable
    from a measured zero on a page that looked perfectly healthy. `async` is a
    parse error in that grammar, which kills the whole component.

    The evaluator now throws on `await` rather than fabricating, and this gate
    keeps the templates at zero so that throw stays unreachable. Counted by
    scripts/check_alpine_await.py, which ignores <script> bodies, string
    literals and comments.
    """
    proc = _run([sys.executable, "scripts/check_alpine_await.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("alpine-await", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_alpine_await.py to list them"
    return Result("alpine-await", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_attr_quoting(baseline: int) -> Result:
    """No `| tojson` inside a DOUBLE-quoted HTML attribute.

    Jinja's tojson emits HTML-safe JSON: it escapes `<`, `>`, `&` and `'`
    (to \u0027) but deliberately leaves `"` literal, because JSON without
    double quotes is not JSON. So `x-data="foo({{ report | tojson }})"`
    renders as `x-data="foo({"score": 3, ...})"` and the payload's own first
    `"` closes the attribute early. Alpine's CSP-safe parser then receives a
    truncated expression and throws `Uncaught SyntaxError: expected } got ""`,
    which aborts x-data init and kills the whole component -- every x-show,
    x-text and @click inside it silently stops working. Measured live in a
    browser on /solutions/1/completeness and /modules/.

    A single-quoted attribute is safe precisely because tojson escapes `'`,
    so the fix is normally a delimiter swap; where the expression carries its
    own single-quoted JS strings those become double-quoted, or the value
    moves to a data-* attribute. Counted by scripts/check_attr_quoting.py,
    which masks Jinja comment regions and flags every tojson in a
    double-quoted attribute -- "this value can never contain a quote" is a
    property of today's data, not of the template.
    """
    proc = _run([sys.executable, "scripts/check_attr_quoting.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("attr-quoting", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_attr_quoting.py to list them"
    return Result("attr-quoting", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_input_labels(baseline: int) -> Result:
    """No form control a screen reader cannot name.

    An unlabelled <input>/<select>/<textarea> is announced as its type and
    nothing else, so the only way to learn what a field holds is to fill it in.
    The same audit found 34 in rendered pages alone -- toolbar filter selects,
    every table's select-all checkbox, and a "Paste CSV Data" textarea whose
    visible <label> simply had no `for`, so the association was never made.

    A placeholder does not count: it is not reliably exposed as an accessible
    name, and it disappears the moment the user types.
    """
    proc = _run([sys.executable, "scripts/check_input_labels.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("input-labels", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_input_labels.py to list them"
    return Result("input-labels", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_macro_kwargs(baseline: int) -> Result:
    """No Jinja macro call passing a keyword the macro does not accept.

    Jinja resolves a macro signature only when the call executes, so this is
    invisible to `template-syntax` (the file parses) and to `boot-health` (the
    url_for resolves). The page raises `TypeError: macro 'x' takes no keyword
    argument 'y'` the first time a request renders that branch.

    Found by the Aug 2026 route audit: capability_maturity/heatmap.html called
    components/empty_state.html's `empty_state` with `cta_label=`, which is the
    correct parameter of a *different, identically named* macro in
    macros/page_shell.html. It rendered only for an organisation with zero
    capabilities, so every seeded database hid it and only a brand-new customer
    could reach the 500 -- which is why counting the class beats fixing the one
    instance.
    """
    proc = _run([sys.executable, "scripts/check_macro_kwargs.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("macro-kwargs", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_macro_kwargs.py to list them"
    return Result("macro-kwargs", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_journey_coverage(baseline: int) -> Result:
    """Every persona has a journey test that writes and asserts the outcome.

    Levels 0-8 all ask "does this break?". None of them asks "can a person
    achieve their goal?" -- and a screen can compile, render, label its controls
    correctly, leak nothing, and still be a workflow nobody can complete.
    /capability-analysis/unmapped returned 200 for months while never querying
    the rows it exists to show, because the view's own name shadowed the query
    result; a status assertion could not have caught it and a journey would
    have.

    Writing the four missing journeys this gate demanded found, in one pass: a
    portfolio manager's core action rejected with 400 by its own endpoint, a
    governed retire disposition approvable with no ARB decision, a 500 on every
    successful bulk approval (a dict written to a TEXT column, raised at commit
    outside the caller's try/except), and an ARB decision that was recorded
    correctly and then displayed nowhere on the review page.

    See docs/TESTING_STANDARD.md, Level 9.
    """
    proc = _run([sys.executable, "scripts/check_journey_coverage.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("journey-coverage", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_journey_coverage.py to list them"
    return Result("journey-coverage", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_unreachable_actions(baseline: int) -> Result:
    """No handler branch behind a whitelist that already rejected its value.

    POST /applications/rationalization/api/bulk-review validated
    valid_actions = {"approve", "defer", "request_data"} and then implemented
    `elif action == "set_disposition":` -- the portfolio_manager persona's core
    action, rejected with 400 before it could reach its own implementation.
    The module compiles, ruff sees a reachable elif, and the endpoint returns a
    well-formed 400, so nothing in levels 0-8 could see it; a journey test
    could, and did.
    """
    proc = _run([sys.executable, "scripts/check_unreachable_actions.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("unreachable-actions", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_unreachable_actions.py to list them"
    return Result("unreachable-actions", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_inline_handlers(baseline: int) -> Result:
    """No inline event handler attribute -- this app's CSP refuses to run them.

    script-src carries no 'unsafe-inline' and no 'unsafe-hashes', and a nonce
    does not cover attributes, so onclick=/onchange=/onsubmit= render fine and
    never fire. Sixteen were live when this gate was written, including six
    destructive forms whose confirmation dialog never appeared -- Delete
    submitted straight through -- and the admin role select, which silently
    stopped changing anyone's role. Every template parsed, every route returned
    200, and every gate was green.
    """
    proc = _run([sys.executable, "scripts/check_inline_handlers.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("inline-handlers", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_inline_handlers.py to list them"
    return Result("inline-handlers", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_persona_vocabularies(baseline: int) -> Result:
    """The product's four persona lists must reconcile with VALID_ROLES.

    All four disagreed: the admin SSO screen's list is both its dropdown and
    its validator, and it had drifted three roles behind -- so an administrator
    at an SSO-only customer could not map an IdP group to a CTO, a procurement
    user or an application manager at all. Three of nine shipped personas,
    each with a sidebar zone, permissions and a governed AI charter,
    unprovisionable. Every page returned 200 throughout.
    """
    proc = _run([sys.executable, "scripts/check_persona_vocabularies.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("persona-vocabularies", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_persona_vocabularies.py to list them"
    return Result("persona-vocabularies", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_evidence_contract(baseline: int) -> Result:
    """No unevidenced claim ships, and no gate is trusted until it has failed.

    Two rules, both binding on any agent working this repository:

    A behavioural change under app/ must land with a test or an `Evidence:`
    trailer naming the command and its result -- because on 30 Aug 2026 the
    model running this repo announced three conclusions it had not measured
    (a harness "broken" that had just measured 1,700 page loads; a page
    "hanging" that answers in 0.04s). None reached production, because the
    artifacts were measured even when the narration was not. This makes the
    measurement the deliverable.

    And every checker registered here must carry a `Proven-against:` line
    naming the input it was watched to fail on. TESTING_STANDARD.md rule 7 has
    always required it and nothing enforced it -- which is precisely the hole
    an agent walks through by writing a checker that has never once gone red
    and reporting it as coverage.
    """
    proc = _run([sys.executable, "scripts/check_evidence_contract.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("evidence-contract", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_evidence_contract.py to list them"
    return Result("evidence-contract", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_ai_evidence_rules(baseline: int) -> Result:
    """Every AI persona charter carries the no-fabrication rules.

    A persona charter is a large f-string; adding one means copying one, and a copy that drops the rules block still produces a working, plausible, entirely ungoverned persona that may state numbers it was never given.
    """
    proc = _run([sys.executable, "scripts/check_ai_evidence_rules.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("ai-evidence-rules", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_ai_evidence_rules.py to list them"
    return Result("ai-evidence-rules", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_ai_tool_guard(baseline: int) -> Result:
    """The AI write path keeps its single permission choke point.

    ToolExecutor.execute's docstring states there is no other path from a tool name to a handler. One direct call and 27 write tools lose their permission check with nothing going red -- the docstring would still say it.
    """
    proc = _run([sys.executable, "scripts/check_ai_tool_guard.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("ai-tool-guard", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_ai_tool_guard.py to list them"
    return Result("ai-tool-guard", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_ai_untrusted_content(baseline: int) -> Result:
    """Retrieved content enters the system prompt fenced, after the charter.

    Organisation RAG chunks and vector hits were PREPENDED to the system prompt unfenced, so uploaded document text outranked the governance charter by position -- a planted instruction sat above the rules meant to govern it.
    """
    proc = _run([sys.executable, "scripts/check_ai_untrusted_content.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("ai-untrusted-content", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_ai_untrusted_content.py to list them"
    return Result("ai-untrusted-content", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_authz_widening(baseline: int) -> Result:
    """No role is granted from a field the user's own record carries.

    A read-only Viewer could create and delete ArchiMate elements: require_roles credited any '*_architect' enterprise_role with the 'architect' tier without consulting what the account was permitted to do.
    """
    proc = _run([sys.executable, "scripts/check_authz_widening.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("authz-widening", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_authz_widening.py to list them"
    return Result("authz-widening", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_nullable_columns(baseline: int) -> Result:
    """A NOT NULL column carries a default reconcile-schema can apply.

    Deploys do not run Alembic. reconcile-schema adds nullable columns only, so a new NOT NULL column without a default cannot be applied to a populated table -- and one missing column 500s every page via InFailedSqlTransaction.
    """
    proc = _run([sys.executable, "scripts/check_nullable_columns.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("nullable-columns", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_nullable_columns.py to list them"
    return Result("nullable-columns", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_page_cost(baseline: int) -> Result:
    """No query loads every row only to count them.

    Nothing in 53 gates measured query cost, so an N+1 that only bites at 100,000 rows had no way of being caught before a customer found it.
    """
    proc = _run([sys.executable, "scripts/check_page_cost.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("page-cost", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_page_cost.py to list them"
    return Result("page-cost", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_credential_autofill(baseline: int) -> Result:
    """Every credential field declares an autocomplete value.

    Chrome pattern-matches a text input followed by a password input as a login
    form and offers a saved credential -- it does not care that the label says
    "API Key". The 30 Aug 2026 QA audit watched it populate the Anthropic API
    key and Salesforce Consumer Secret fields with a real saved email and
    password. The audit reached two instances; a full-tree scan found five
    unprotected password inputs and nineteen PasswordField definitions.
    """
    proc = _run([sys.executable, "scripts/check_credential_autofill.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("credential-autofill", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_credential_autofill.py to list them"
    return Result("credential-autofill", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_nested_jinja(baseline: int) -> Result:
    """No Jinja expression opened inside another -- it renders as literal text.

    `{{ page_header(title='{{ framework.industry_name }}') }}` put the inner
    expression inside a string literal, so the Industry APQC framework page
    rendered the seven words of the placeholder as its <h1> while the breadcrumb
    one line above showed the resolved name. The template parses, the route
    returns 200, and no other gate can see it.
    """
    proc = _run([sys.executable, "scripts/check_nested_jinja.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("nested-jinja", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_nested_jinja.py to list them"
    return Result("nested-jinja", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_cache_tenancy(baseline: int) -> Result:
    """A module-level cache over tenant data must be keyed by the tenant.

    Two were found unkeyed on 30 Aug 2026 and both were cross-tenant data leaks:
    the capability health cache served one tenant's capability names and scores
    to every other tenant for 60 seconds, and the AI's RAG context cache put one
    tenant's prior ARB decision titles into another tenant's system prompt for
    five minutes. Neither needed any action by the receiving user.

    tenant-scoping and raw-sql-tenancy read QUERIES; these are dictionaries. And
    do_orm_execute cannot help, because a cache hit emits no SQL to filter --
    the same blind spot CLAUDE.md records for Query.get() on an identity-map hit.
    """
    proc = _run([sys.executable, "scripts/check_cache_tenancy.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("cache-tenancy", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_cache_tenancy.py to list them"
    return Result("cache-tenancy", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_ai_approval_honoured(baseline: int) -> Result:
    """The agent honours the operator's AI approval control.

    config.py said REQUIRE_AI_APPROVAL gated the LLM-agent mutating-tool queue.
    The agent loop never read it: the decision came from a per-session user
    preference any authenticated account could flip in one request, after which
    every tier auto mutating tool wrote to the system of record with no approval
    row. The /ai-chat/data/* routes were gated correctly throughout, which is
    why it went unnoticed.
    """
    proc = _run([sys.executable, "scripts/check_ai_approval_honoured.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("ai-approval-honoured", FAIL, f"could not parse count: {proc.stdout!r}")
    detail = "" if count <= baseline else "run scripts/check_ai_approval_honoured.py to list them"
    return Result("ai-approval-honoured", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_business_layer_backbone(baseline: int) -> Result:
    """The business architect's layer, which no gate read until now.

    check_archimate_backbone covers motivation entities. Capabilities, value
    streams and business processes -- the layer the product's headline feature
    models -- had nothing. A BusinessCapability with no element is invisible to
    every capability lens that walks the model rather than the table.
    """
    proc = _run([sys.executable, "scripts/check_business_layer_backbone.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("business-layer-backbone", FAIL, f"could not parse count: {proc.stdout!r}")
    detail = "" if count <= baseline else "run scripts/check_business_layer_backbone.py to list them"
    return Result("business-layer-backbone", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_api_envelope(baseline: int) -> Result:
    """One API, one response shape.

    850 of 2,668 jsonify handlers commit to no envelope, so every caller carries
    `json.data ?? json` -- which returns the wrong object whenever a bare
    payload has its own data key. Ratcheted: choosing the canonical shape and
    moving the callers in step is a migration, not a lint fix.
    """
    proc = _run([sys.executable, "scripts/check_api_envelope.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("api-envelope", FAIL, f"could not parse count: {proc.stdout!r}")
    detail = "" if count <= baseline else "run scripts/check_api_envelope.py to list them"
    return Result("api-envelope", PASS if count <= baseline else FAIL, detail, count, baseline)


def _simple_ratchet(script: str, name: str, baseline: int) -> Result:
    """Run a --count checker and compare against its baseline."""
    proc = _run([sys.executable, script, "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result(name, FAIL, f"could not parse count: {proc.stdout!r}")
    detail = "" if count <= baseline else f"run {script} to list them"
    return Result(name, PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_collapsed_nav_affordance(baseline: int) -> Result:
    """The collapsed rail must stay navigable.

    Collapsing is a width change with no label hiding and no tooltips, so the
    sidebar clips to "All mo..." beside icons that say nothing. Seventy gates
    were green over it, because they all read source for structure.
    """
    return _simple_ratchet(
        "scripts/check_collapsed_nav_affordance.py", "collapsed-nav-affordance", baseline)


def gate_nav_icon_ambiguity(baseline: int) -> Result:
    """Two destinations behind one icon in one persona's own sidebar."""
    return _simple_ratchet(
        "scripts/check_nav_icon_ambiguity.py", "nav-icon-ambiguity", baseline)


def gate_nav_label_clarity(baseline: int) -> Result:
    """One label naming two destinations, or a label too long to survive."""
    return _simple_ratchet(
        "scripts/check_nav_label_clarity.py", "nav-label-clarity", baseline)


def gate_handoff_continuity(baseline: int) -> Result:
    """Work moved into a state no reachable persona surface reads back.

    The service designer's gate. Archie is a governance workflow product, so
    the handoff between personas IS the product -- and a state written into a
    queue nobody can open fails silently on both sides: the sender believes it
    was sent, the reviewer never sees it. Must stay clean at 0.
    """
    return _simple_ratchet(
        "scripts/check_handoff_continuity.py", "handoff-continuity", baseline)


def gate_metric_provenance(baseline: int) -> Result:
    """A proportion shown to the user that is a literal, not a measurement.

    The data / evidence analyst's gate. "Total Capabilities 191" above a table
    reading "Showing 1-10 of 0 results" is the class; the tractable half is a
    percentage or score written in the source, which no user can distinguish
    from a real reading.
    """
    return _simple_ratchet(
        "scripts/check_metric_provenance.py", "metric-provenance", baseline)


def gate_raw_sql_columns(baseline: int) -> Result:
    """Raw SQL naming a column the table does not have.

    reconcile-schema and the schema-drift gate compare ORM MODELS to the
    database; raw SQL is invisible to both. Four statements were selecting
    columns that do not exist -- including the solution narrative's risk
    register, which meant every SAD rendered "no risks" regardless of the
    register, and a vendor enrichment whose failure cost the AI its Gartner
    position too. All four are fixed, so this is must-stay-clean at 0.
    """
    return _simple_ratchet(
        "scripts/check_raw_sql_columns.py", "raw-sql-columns", baseline)


def gate_actionable_rows(baseline: int) -> Result:
    """A row you cannot act on is a report, and this is not a report.

    /archimate-roadmap listed three gaps -- name, type, severity, status -- with
    no link, no button and no route to the work package they should become. 112
    of 158 record tables are the same shape. Ratcheted, because a status
    breakdown is legitimately read-only and each exemption must say why.
    """
    return _simple_ratchet(
        "scripts/check_actionable_rows.py", "actionable-rows", baseline)


def gate_placeholder_copy(baseline: int) -> Result:
    """Copy that satisfies every rule and tells the user nothing.

    The owner found `<label for="application-search">Field</label>` in the
    capability map's mapping dialog on the deployed site. 59 such labels exist.
    axe passes them -- "Field" IS a valid accessible name, and axe checks that a
    control HAS a label, never that the label means anything. Nothing else in
    the estate opens a form and reads it. Gates check presence, not meaning.
    """
    return _simple_ratchet(
        "scripts/check_placeholder_copy.py", "placeholder-copy", baseline)


def gate_ai_layer_coverage(baseline: int) -> Result:
    """How much of ArchiMate 3.2 the AI can model for someone who cannot hire
    an architect.

    54 of the 58 element types the product declares have no dedicated AI
    creation path. The assistant can reason about motivation and design
    solutions; it cannot model the business, technology, strategy or migration
    layers. A generic create_archimate_element does not count -- emitting a
    typed node hands the modelling judgement back to the user, which is the
    thing this product exists to remove. Ratcheted so it falls as the gap
    closes.
    """
    return _simple_ratchet(
        "scripts/check_ai_layer_coverage.py", "ai-layer-coverage", baseline)


def gate_canonical_store(baseline: int) -> Result:
    """One concept, one store.

    Ten tables are mapped by two model classes each. They select different columns,
    apply different defaults and feed different screens the same record -- which
    is how /capability-map/ shows 'Total Capabilities 191' above a table reading
    'Showing 1-10 of 0 results'. A ratchet cannot pay the debt down; it stops it
    growing while that migration is outstanding.
    """
    proc = _run([sys.executable, "scripts/check_canonical_store.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("canonical-store", FAIL, f"could not parse count: {proc.stdout!r}")
    detail = "" if count <= baseline else "run scripts/check_canonical_store.py to list them"
    return Result("canonical-store", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_role_gate_coverage(baseline: int) -> Result:
    """A role declared in the delivery contract with no gate enforcing it.

    CLAUDE.md tells every agent to act as CTO, architect and QA lead at once,
    and agents act as developers only because nothing measures the difference.
    docs/DELIVERY_CONTRACT.md defines a role as its family of gate tags; this
    counts the roles whose tags resolve to nothing in the registry above.
    """
    proc = _run([sys.executable, "scripts/check_role_gate_coverage.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("role-gate-coverage", FAIL, f"could not parse count: {proc.stdout!r}")
    detail = "" if count <= baseline else "run scripts/check_role_gate_coverage.py to list them"
    return Result("role-gate-coverage", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_empty_state_cta(baseline: int) -> Result:
    """A new tenant's first hour is empty states. They must offer a way forward.

    21 of 40 tell the user there is nothing here and stop -- including the
    applications list, whose entire purpose is getting applications into it.
    The macro already supports a CTA in both variants, so each of these is a
    call-site omission. A ratchet: writing 21 pieces of product copy is a
    per-screen product decision, but the number must not grow meanwhile.
    """
    proc = _run([sys.executable, "scripts/check_empty_state_cta.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("empty-state-cta", FAIL, f"could not parse count: {proc.stdout!r}")
    detail = "" if count <= baseline else "run scripts/check_empty_state_cta.py to list them"
    return Result("empty-state-cta", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_archimate_backbone(baseline: int) -> Result:
    """Every motivation create syncs an archimate element.

    CLAUDE.md calls ArchiMate the backbone, not a view: the field IS the element.
    53 creation paths never call the sync, including four of the AI agent's own
    write tools -- so entities a human approved have been landing outside the
    model every capability lens reads from. The runtime audit finds the
    consequence; this finds the cause, before the rows exist.
    """
    proc = _run([sys.executable, "scripts/check_archimate_backbone.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("archimate-backbone", FAIL, f"could not parse count: {proc.stdout!r}")
    detail = "" if count <= baseline else "run scripts/check_archimate_backbone.py to list them"
    return Result("archimate-backbone", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_template_syntax() -> Result:
    """Every Jinja template parses. Gated at ZERO.

    A template that does not parse is not a degraded page — it is a 500 on every
    route that renders it, and on every route that renders a macro it defines.
    Nothing else catches it: `compile` covers Python only, and boot-health
    resolves endpoints without rendering bodies.

    Added after `{# … #}` was inserted inside an existing `{# … #}` block in
    components/dropdown_menu.html. Jinja has no nested comments, so the inner
    `#}` closed the outer block early and 17 lines became live template code.
    """
    proc = _run([sys.executable, "scripts/check_template_syntax.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("template-syntax", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count == 0 else "run scripts/check_template_syntax.py to list them"
    return Result("template-syntax", PASS if count == 0 else FAIL, detail, count, 0)


def gate_fetch_guards(baseline: int) -> Result:
    """A raw fetch() whose body is parsed without checking the response. RATCHET.

    The client half of `error-signalling`. That gate made ~64 endpoints answer a
    failure with an honest 4xx/5xx instead of 200 - and a caller that never
    looks at the response throws that away: `fetch` does not reject on 4xx/5xx,
    so the error body parses cleanly, `data.items || []` yields an empty list,
    and the user sees "no results" exactly as before. Both halves are required.

    A ratchet at first because 107 call sites carry it and triage is judgement
    work - some are genuinely best-effort. It tightens to zero once the tail is
    cleared. Hatch: `fetch-guard-ok: <reason>`.
    """
    proc = _run([sys.executable, "scripts/check_fetch_guards.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("fetch-guards", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_fetch_guards.py to list them"
    return Result("fetch-guards", PASS if count <= baseline else FAIL,
                  detail, count, baseline)


def gate_ui_contract(baseline: int) -> Result:
    """The UI/UX audit's finish-level rules, ratcheted so they cannot regress.

    Counts native alert/confirm/prompt, inline onclick= handlers, <button>s with
    no type=, and arbitrary text-[Npx] sizes across templates and JS. A ratchet:
    the number may only fall, so a fix lowers the bar and a new violation fails
    the build. Escape hatch: `ui-contract-ok: <reason>`.
    """
    proc = _run([sys.executable, "scripts/check_ui_contract.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("ui-contract", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_ui_contract.py to list them"
    return Result("ui-contract", PASS if count <= baseline else FAIL,
                  detail, count, baseline)


def gate_error_signalling() -> Result:
    """API error paths that answer a failure with HTTP 200. MUST BE ZERO.

    This is the defect that quietly undoes the rest of the audit. Client code
    now correctly does `if (!response.ok) throw`, and that check is worth
    nothing when the server catches the exception and returns 200 - which Flask
    does by default for any bare `jsonify(...)`. The front end cannot detect it,
    however carefully it is written, which is what earns this its own gate.

    64 were found on the first run. The AI usage-analytics endpoint returned
    `{"success": true, "analytics": {…all zeros…}}` at 200, rendering a
    confident analytics panel indistinguishable from an organisation that had
    never used the assistant. A system-settings endpoint answered
    `{"settings": {}, "status": "ok"}`, and its caller merged that into a
    24-key defaults object - presenting hard-coded defaults as the admin's saved
    configuration. `/rationalization/api/executive-summary` returned zeroed
    score buckets and zeroed projected savings at an explicitly written 200.

    Proof that the layers are not redundant: a front-end fix from earlier in the
    same audit had added the message "Import history could not be loaded. This
    is not an empty history." It was unreachable until the matching endpoint
    stopped returning 200.

    Escape hatch: `error-signalling-ok: <reason>` on the return or the line
    above. The legitimate case is a fail-closed gate - a policy check that
    denies on error is answering honestly - or a fallback that did real work and
    discloses what it could not do.
    """
    proc = _run([sys.executable, "scripts/check_error_signalling.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("error-signalling", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count == 0 else "run scripts/check_error_signalling.py to list them"
    return Result("error-signalling", PASS if count == 0 else FAIL, detail, count, 0)


def gate_silent_data() -> Result:
    """A server-side failure returned to the caller as data. MUST BE ZERO.

    `broken-surfaces --kind silent-empty` covers this shape in the front end.
    This is the same defect one layer down, where no amount of front-end care
    can detect it: a broad `except Exception:` in a route or service that
    answers a failed query with `[]`, `{}` or `0`.

    CLAUDE.md's rule is that fabricating a plausible value is worse than showing
    nothing, because the user cannot tell the difference and acts on it. The
    first run found 56, including a phase gate reporting "0 drivers defined"
    from a database error, a regulatory compliance percentage divided by a
    failed count, a total cost of ownership of zero, and - worst - the AI
    assistant's grounding context answering an exception with "0% complete",
    which the model then asserted to the user in fluent prose.

    Removing the swallows also exposed three imports of modules that have never
    existed in this repo, each dead and silent since it was written: one of
    them made phase F's "Work packages defined" gate unpassable for every
    solution ever created.

    Zero rather than a ratchet: unlike raw-SQL tenancy or design tokens, there
    is no legacy tail here to work through - the 56 were fixed in one pass, so
    any new one is a regression. Per-line escape hatch: `silent-data-ok:
    <reason>`.
    """
    proc = _run([sys.executable, "scripts/check_silent_data.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("silent-data", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count == 0 else "run scripts/check_silent_data.py to list them"
    return Result("silent-data", PASS if count == 0 else FAIL, detail, count, 0)


def gate_broken_surfaces(baseline: int) -> Result:
    """Front-end surfaces resolved against the real route table. RATCHET.

    Boots the app, takes its url_map, and resolves what the templates and
    scripts actually point at. Nothing else does this: every other gate proves a
    page renders, none proves the things ON it go anywhere.

      dead-link      href to a path no route serves
      dead-fetch     fetch() to a path no route serves — the whole Market
                     Intelligence page called four endpoints that do not exist
      swallowed      catch blocks that tell neither the user nor the logs
      form-no-action <form> with no action and no submit handler: Enter reloads
                     the page and discards everything typed
      forbidden-ui   alert()/confirm(), which DESIGN.md forbids

    A ratchet rather than zero because `swallowed` carries several hundred
    pre-existing cases and some are legitimate. Triage is real work; letting the
    number grow while it happens is not acceptable, so this is "no worse".

    The count is only trustworthy because the checker was corrected five times
    against sampled findings: <path:> converters match slashes, Platform.fetch
    already handles !ok, chains branching on data.success already report
    failure, comments describing the pattern are not instances of it, and a
    concatenated URL's first literal is a prefix, not the whole path. That last
    one alone accounted for 163 phantom findings.
    """
    # The checker sets FLASK_CONFIG=testing itself (it has to boot the app to
    # read url_map), so no env plumbing is needed here.
    proc = _run([sys.executable, "scripts/check_broken_surfaces.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("broken-surfaces", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_broken_surfaces.py to list them"
    return Result("broken-surfaces", PASS if count <= baseline else FAIL,
                  detail, count, baseline)


def gate_dynamic_link_prefixes(baseline: int) -> Result:
    """ARCH-043: concatenated href/fetch links whose literal prefix is dead. RATCHET.

    check_broken_surfaces.py's dead-link/dead-fetch classes intentionally skip
    any URL built by string concatenation (`'/x/' + id`) — guessing the
    interpolated id is a worse trade than the false positives it would cause.
    That correctly-scoped skip let a whole class of real 404s through: a route
    migration (/dashboard/application/<id> -> /applications/<id>,
    /vendors/view/<id> -> /applications/vendors/<id>) left concatenated Alpine
    `:href` bindings pointing at the dead prefix, invisible to CI, only found
    by manually clicking through the rendered DOM.

    This does not guess the id. It checks only the literal prefix before the
    `+` — not a guess, since it is exactly the string the browser is about to
    receive — against the app's real url_map, so it only rules on the part
    that is unconditionally true for every possible id substituted in.
    """
    proc = _run([sys.executable, "scripts/check_dynamic_link_prefixes.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("dynamic-link-prefixes", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_dynamic_link_prefixes.py to list them"
    return Result("dynamic-link-prefixes", PASS if count <= baseline else FAIL,
                  detail, count, baseline)


def gate_dead_interactions() -> Result:
    """No control that looks like it works and does nothing. Gated at ZERO.

    Four classes, none visible to any other gate — the template compiles, the
    route returns 200, and the button is present and correctly styled:

      silent-fetch  `if (r.ok) {...}` with no else. fetch does not reject on
                    4xx/5xx, so a 500, a 403 or a rejected CSRF token falls
                    through and the handler returns having done nothing. The
                    user clicks, the button spins, and nothing happens.
      silent-then   fetch().then() that never inspects status, so the error body
                    is parsed as a result and the success path runs anyway.
      dead-handler  @click="foo()" where foo is defined nowhere the page loads.
      dead-action   data-action="x" with no consumer; the click is dropped.

    Added after a user reported clicking a button on /solutions/briefings/2 and
    nothing happening. It was one of 97 instances of the same pattern. Three of
    them were worse than dead: addCapability() pushed a fabricated record into
    the list when its POST failed, saveContext() reported success before five
    later saves whose failures were invisible, and a failed team-member DELETE
    still reloaded the page so the member appeared gone.

    Platform.fetch (app/static/js/core/03-fetch.js) is deliberately EXCLUDED:
    it already checks !response.ok, extracts the server's message and toasts it.
    The bug is bypassing that wrapper, not using it.
    """
    proc = _run([sys.executable, "scripts/check_dead_interactions.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("dead-interactions", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count == 0 else "run scripts/check_dead_interactions.py to list them"
    return Result("dead-interactions", PASS if count == 0 else FAIL, detail, count, 0)


def gate_macro_import_context() -> Result:
    """A macro holding a <script> is imported `with context`. Gated at ZERO.

    Jinja's `from x import m` / `import x as m` do not pass the caller's context.
    CspNonceExtension rewrites every template-authored <script> to carry
    nonce="{{ csp_nonce }}", and csp_nonce comes from a context processor - so in a
    context-less import it is undefined, renders as nonce="", and the CSP
    (script-src 'self' 'nonce-...' 'strict-dynamic') refuses the script outright.
    strict-dynamic means there is no origin fallback.

    Nothing else sees it. The template compiles, the route returns 200, and the
    JavaScript never runs. One sweep found 14 live sites shipping dead JS - the AI
    chat's document-upload panel, the page-guide drawer included by
    layouts/admin_base.html (so every admin page), the roadmap and gantt widgets,
    the LLM recommendation panels on four strategic pages, and the
    password-strength meter on every account form.

    It was found by loading a page in a browser. This gate is so the next one is
    found in 3 seconds instead.
    """
    proc = _run([sys.executable, "scripts/check_macro_import_context.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("macro-import-context", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count == 0 else "run scripts/check_macro_import_context.py to list them"
    return Result("macro-import-context", PASS if count == 0 else FAIL, detail, count, 0)


def gate_template_references() -> Result:
    """Every `{% include %}` / `{% extends %}` target exists. Gated at ZERO.

    `template-syntax` proves a template parses; it cannot see whether the files
    that template pulls in are present, because Jinja resolves include/extends
    at render time. A missing partial is therefore invisible until someone opens
    the page, and then it is a TemplateNotFound 500 rather than a gap in the
    layout.

    Found three cases in one sweep. `auth/register.html` and
    `admin/security.html` both extended `base.html`, which does not exist — the
    base lives at `layouts/base.html`; each survived only because the blueprint
    rendering it is not currently registered. `applications/detail.html`
    included nine partials of which one existed, and was rendered by no route at
    all, so the per-application ArchiMate layer UI inside it had never worked.
    """
    proc = _run([sys.executable, "scripts/check_template_references.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("template-references", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count == 0 else "run scripts/check_template_references.py to list them"
    return Result("template-references", PASS if count == 0 else FAIL, detail, count, 0)


def gate_alpine_data_binding() -> Result:
    """Every `x-data` names something the CSP evaluator can resolve. Gated at ZERO.

    Alpine expressions run through the hand-written interpreter in
    `app/static/js/csp/csp-evaluator.js` (so script-src can drop
    'unsafe-eval'). It resolves a bare identifier against the component scope
    and then `window` -- it never reads Alpine's `Alpine.data()` registry. A
    template that registers `Alpine.data('foo', ...)` and then writes a bare
    `foo` in the attribute therefore mounts an EMPTY component, and nothing
    goes red: no console error, no failed request, no 5xx.

    Measured on Impact Analysis, the enterprise architect's "if I retire this,
    what breaks?" page. Typing in the element picker fired no request and
    Analyze Impact did nothing. Worse, the surviving expressions fell through
    to globals of the same name, so `x-text="'(' + history.length + ')'"`
    rendered `window.history.length` -- the page showed a badge reading
    "Recent Analyses (4)", counting the browser's navigation entries, above an
    empty table. Three other templates carried the same binding.
    """
    proc = _run([sys.executable, "scripts/check_alpine_data_binding.py", "--json"])
    try:
        count = int(json.loads(proc.stdout)["count"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return Result("alpine-data-binding", FAIL,
                      f"could not parse output: {proc.stdout[:200]!r} {proc.stderr[:200]}")
    detail = "" if count == 0 else "run scripts/check_alpine_data_binding.py to list them"
    return Result("alpine-data-binding", PASS if count == 0 else FAIL, detail, count, 0)


def gate_asset_urls() -> Result:
    """No doubled '?' asset URL, no stylesheet/script included twice per template.

    ARCH-060: the global `url_for` override already appends `?v=<build id>` to
    every static URL (see build_info.get_build_id()); a template that then
    hand-appends its own `?v=2` produces a second '?', and everything after it
    becomes part of the first query value rather than a real parameter — cache-
    busting silently stops working for exactly that file. ARCH-061: the same
    stylesheet/script included twice in one template at two different version
    stamps is a non-determinism bug (whichever tag loads second wins), found live
    with app/static/css/accessibility.css loaded from both
    app/templates/layouts/admin_base.html and the shared partials/_head.html it
    also includes.
    """
    proc = _run([sys.executable, "scripts/check_asset_urls.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("asset-urls", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = ""
    if count:
        detail = _run([sys.executable, "scripts/check_asset_urls.py"]).stdout[-1500:]
    return Result("asset-urls", PASS if count == 0 else FAIL, detail, count, 0)


def gate_qa_register() -> Result:
    """Every finding in the 17 Aug 2026 QA remediation register is closed.

    The register is the outstanding remediation backlog (97 active findings across
    the master register and its three source documents). CLAUDE.md's rule for
    unfinished work is to prefer a gate that COUNTS it over prose that describes
    it, because a written-down-and-left defect becomes a defect plus a note, and
    the note reads later as a deliberate decision.

    This gate is that count, and it is deliberately a hard zero rather than a
    ratchet: while any finding is open, verify.py cannot go green, so the branch
    cannot legitimately deploy. Finishing the register stops being a promise and
    becomes something the build asserts. Ledger: qa_findings_status.json — a
    finding is closed only once its fix is committed and its tests pass, and a
    partially-fixed finding stays open with a note.
    """
    proc = _run([sys.executable, "scripts/check_qa_register.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("qa-register", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = ""
    if count:
        detail = _run([sys.executable, "scripts/check_qa_register.py"]).stdout[-1800:]
    return Result("qa-register", PASS if count == 0 else FAIL, detail, count, 0)


def gate_null_filters() -> Result:
    """No `|default(...)` feeds a filter that calls len(). Gated at ZERO.

    Jinja's `default` replaces an *undefined* value, not a `None` one, and every
    nullable column arrives as None. So `description|default('-')|truncate(100)`
    passes None to `truncate`, which raises "object of type 'NoneType' has no
    len()" and aborts the entire render, not just that field.

    Found in production: one capability with a NULL description blanked
    /enterprise/capability-map/capabilities. The route's own `except` re-rendered
    the same template with an empty list, so it returned 200 showing "Error
    loading capabilities" and no rows while the capabilities existed - a reader
    cannot tell that from an empty portfolio. Nine templates carried the pattern,
    including capability health, plateaus, gap analysis and technology roadmap.

    Fix is the boolean second argument: default('x', true).
    """
    proc = _run([sys.executable, "scripts/check_null_filters.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("null-filters", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count == 0 else "run scripts/check_null_filters.py to list them"
    return Result("null-filters", PASS if count == 0 else FAIL, detail, count, 0)


def gate_test_data_in_queries() -> Result:
    """Test fixture names filtered out of production queries. Gated at ZERO.

    Found in the Architecture Journey hub, then in seven more places once there was
    something to look with: production queries excluding rows named 'J1-AutoTest-%',
    'J7-E2E-Test%' and '%-AutoTest-%'.

    Wrong twice over. A customer who names a solution "Migration-AutoTest-Rig"
    watches it disappear from their own screen with no explanation and no way to get
    it back. And the exclusion makes leaked test rows invisible, so the leak is never
    fixed and the workaround becomes permanent -- one site even documented the
    reasoning as "the weekly AutoTest purge can lag", which is an argument for fixing
    the purge, not for hiding its backlog from the screen most likely to prompt
    someone to fix it.

    Zero rather than a ratchet: unlike the fabricated-data backlog, this population
    was small enough to clear in one pass, and every instance is the same defect with
    the same fix. Escape hatch is 'test-filter-ok: <reason>' for the genuine case --
    a cleanup CLI, a seeder.
    """
    proc = _run([sys.executable, "scripts/check_test_data_in_queries.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("test-data-in-queries", FAIL,
                      "could not read a count from the checker:\n" + proc.stdout[-400:])
    detail = "" if count == 0 else _run(
        [sys.executable, "scripts/check_test_data_in_queries.py"]
    ).stdout.strip()
    return Result("test-data-in-queries", PASS if count == 0 else FAIL, detail, count, 0)


def gate_fabricated_data_server(baseline: int) -> Result:
    """Server-side fabrication, and escape hatches that never worked. RATCHET.

    The sibling gate has been green at zero for a long time, and that was true of
    what it could see. Every one of its rules was written JavaScript-first: it
    matches a `catch` assigning an array-of-objects, "// mock data", displayed
    randomness, and fictional company names in markup. The identical defect
    written in Python -- an `except` returning ``{"pending": 0, "approval_rate":
    0}`` -- was invisible to all four, and that is precisely the shape the ARB
    legacy dashboard uses to render "Pending 0" after a database failure. A
    reader seeing 0 concludes the queue is clear.

    The second rule is about the escape hatch itself. ``ALLOW`` matches
    ``fabricated-ok:``; the string ``fabricated-values-ok`` does not contain it,
    so it suppressed nothing -- while reading, to every subsequent author,
    exactly like a filed and accepted exception. 152 of them accumulated. A
    silent non-exception is worse than no exception, because it stops the next
    reader looking.

    Ratcheted, not gated at zero, and deliberately so. The population is real
    debt that predates the rules finding it, and 209 findings cannot be triaged
    honestly in one pass -- each dead marker is a claim that an exception was
    warranted, and converting them wholesale to the working spelling would
    legitimise 152 fabrications nobody ever reviewed. The ratchet stops the
    number growing while that review happens.
    """
    proc = _run([
        sys.executable, "scripts/check_fabricated_data.py", "--count",
        "--select", "python-zero-fill",
        "--select", "unknown-ok-marker",
    ])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("fabricated-data-server", FAIL,
                      "could not read a count from the checker:\n" + proc.stdout[-400:])
    return Result("fabricated-data-server", PASS if count <= baseline else FAIL,
                  "", count, baseline)


def gate_fabricated_data() -> Result:
    """No invented data can reach the UI. Gated at ZERO.

    Archie is a system of record, so a screen that fabricates a plausible value
    when the real one is missing is worse than one that shows nothing — the user
    cannot tell the two apart, and acts on it. This caught a governance dashboard
    that invented the customer's architecture principles on API failure, a Gantt
    chart that rendered ~$855k of imaginary work packages, and a settings page
    that reported a backup as created when none was written.

    Escape hatch is 'fabricated-ok: <reason>' on or above the flagged line.
    """
    # Explicitly the four rules this gate has been green on. Two more rules were
    # added later and surface a population that was always present but invisible
    # to a JS-shaped checker; those ratchet separately in
    # gate_fabricated_data_server. Folding them in here would have meant relaxing
    # a zero guarantee to accommodate newly-found debt -- the wrong direction for
    # a gate to move, and the reason this call names its rules.
    proc = _run([
        sys.executable, "scripts/check_fabricated_data.py", "--count",
        "--select", "catch-returns-fake",
        "--select", "self-admitted-fake",
        "--select", "random-data",
        "--select", "fictional-entity",
    ])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("fabricated-data", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count == 0 else "run scripts/check_fabricated_data.py to list them"
    return Result("fabricated-data", PASS if count == 0 else FAIL, detail, count, 0)


def gate_sri() -> Result:
    """Every same-origin integrity= hash matches the file it guards. Gated at ZERO.

    A stale SRI hash does not degrade — the browser REFUSES to execute the asset.
    The failure is a dead page with a console error, invisible to any server-side
    test. This repository has already shipped that bug twice.

    Vendoring makes it easy: repointing a src from a CDN to a local copy is safe
    only if the bytes are identical, and consolidating a version (alpinejs@3 to
    @3.14.3) silently invalidates the hash. Neither vendor-integrity (files vs the
    manifest) nor air-gap (external origins) relates a template's declared hash to
    the file its src resolves to, which is why both passed while two hashes on this
    branch were wrong.
    """
    proc = _run([sys.executable, "scripts/check_sri.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("sri", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = ""
    if count:
        detail = _run([sys.executable, "scripts/check_sri.py"]).stdout[-1200:]
    return Result("sri", PASS if count == 0 else FAIL, detail, count, 0)


def gate_raw_sql_tenancy(baseline: int) -> Result:
    """Raw SQL reading a tenant-scoped table with no organization predicate.

    A ratchet, not a hard zero. do_orm_execute rewrites ORM statements only, so
    raw text() goes to the database as written, and the convention that grew up
    instead was a `# tenant-filtered` comment. That comment has been wrong twice:
    ten queries in business_capability_management_routes.py returned every
    organisation's rows, and the dashboard's capability-coverage metric counted
    every organisation's mappings before dividing by one organisation's total.

    A clean run does NOT prove tenancy. It proves the one mechanically detectable
    failure — no predicate at all — is absent. The common "scoped via parent FK"
    case needs the value followed back through the caller, which no regex can do.
    """
    proc = _run([sys.executable, "scripts/check_raw_sql_tenancy.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("raw-sql-tenancy", FAIL, f"could not parse: {proc.stdout!r}")
    detail = ""
    if count > baseline:
        detail = _run([sys.executable, "scripts/check_raw_sql_tenancy.py"]).stdout[-1500:]
    return Result("raw-sql-tenancy", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_tenant_scoping(baseline: int) -> Result:
    """ORM queries over a tenant-owned-but-unmixed model with no org predicate.

    A ratchet, not a hard zero, and the ORM-side twin of raw-sql-tenancy.
    do_orm_execute auto-filters TenantMixin models; several models carry an
    organization_id column without the mixin, so they get none of that
    filtering. shell-overhaul Wave 3 Task 2 triaged all 153 findings the gate
    produced at the time (plus 4 more surfaced by adding the then-invisible
    app/application_mgmt to SCAN_DIRS): real cross-org leaks were fixed —
    an org-admin IDOR letting one org's admin list/edit/role-escalate another
    org's users (admin_routes.py, user_role_routes.py, admin_user_service.py
    and the v2 equivalents), global User counts feeding dashboards, several
    global ApplicationCapabilityMapping aggregates/reads (capability-coverage
    metrics, portfolio-wide traceability), a governance-notification email
    audience built from every org's platform_admin/enterprise_architect
    users, several cross-org user-picker/@mention-search endpoints, and one
    document-update IDOR in app/application_mgmt with no ownership check at
    all. The remainder were deliberately left unscoped and hatched with
    `tenant-scoping-ok: <reason>` — FK ids already scoped through a
    TenantMixin-loaded parent, self-lookups by the acting user's own id,
    globally-unique keys (email, Stripe subscription id), vendor reference/
    catalog data, pre-auth SSO/invite flows with no org context yet, and one
    finding (gdpr_service.py) where the real defect is a missing
    authentication check on the calling route, not tenant scoping — flagged
    for human decision in the Wave 3 Task 2 report, not fixed here.

    A clean run does NOT prove tenancy — see check_tenant_scoping.py's
    docstring for the same caveat raw-sql-tenancy carries.
    """
    proc = _run([sys.executable, "scripts/check_tenant_scoping.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("tenant-scoping", FAIL, f"could not parse: {proc.stdout!r}")
    detail = ""
    if count > baseline:
        detail = _run([sys.executable, "scripts/check_tenant_scoping.py"]).stdout[-1500:]
    return Result("tenant-scoping", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_sidebar_links(baseline: int) -> Result:
    """Persona sidebar link-count budget (shell-overhaul Wave 1, Task 3).

    Renders components/admin_sidebar.html once per role (see
    scripts/check_sidebar_links.py) and measures the worst-case rendered
    `<a ` count. SIDEBAR_LINK_BUDGET in app/utils/role_access.py is 25; this
    gate is the thing that actually renders the template and catches a future
    edit — to role_access.py's zones, or to the template's guard logic —
    that would push a role over budget, rather than trusting the data alone.
    """
    proc = _run([sys.executable, "scripts/check_sidebar_links.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("sidebar-links", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = ""
    if count > baseline:
        detail = _run([sys.executable, "scripts/check_sidebar_links.py"]).stdout[-1500:]
    return Result("sidebar-links", PASS if count <= baseline else FAIL, detail, count, baseline)


def gate_deployed_deps() -> Result:
    """Installed packages satisfy the floors requirements.txt pins. Gated at ZERO.

    dependency-cves reads requirements.txt, which measures intent. It reported 62
    advisories resolved and stayed green for weeks while production ran every one
    of them: deploy.sh recreated the container from an existing image and never
    rebuilt, so the running image was six weeks older than the pins. Nothing
    compared the two, so nothing could notice.

    This checks the environment this runs in. Locally that is the dev virtualenv;
    `--remote` points it at the production container, which is what CI or a
    post-deploy step should use.
    """
    proc = _run([sys.executable, "scripts/check_deployed_deps.py"])
    output = (proc.stdout + proc.stderr).strip()
    match = re.search(r"^(\d+) of (\d+) pinned", output, re.M)
    count = int(match.group(1)) if match else (0 if proc.returncode == 0 else -1)
    if count < 0:
        return Result("deployed-deps", FAIL, output[-800:])
    return Result("deployed-deps", PASS if count == 0 else FAIL, output[-800:], count, 0)


def _vendored_tailwind_cli() -> Path | None:
    """The pinned standalone CLI, or None. scripts/build_css.py falls back to
    `npx tailwindcss@3`; this deliberately does not, because the point here is
    reproducibility against the committed file, not merely producing CSS."""
    for name in ("tailwindcss.exe", "tailwindcss"):
        candidate = REPO_ROOT / "scripts" / "bin" / name
        if candidate.exists():
            return candidate
    return None


def gate_css_build() -> Result:
    """The committed tailwind-output.css matches what a rebuild produces.

    CSS ships pre-built so a fresh clone renders without a Node toolchain. The
    cost is that editing a template's classes and not rebuilding leaves the two
    out of sync, and the failure is silent and one-directional: a class that is
    not in the built CSS renders as NOTHING. No request fails, no test notices.

    This gate exists because that is exactly what happened while migrating the
    red status badges to the destructive token — the classes involved already
    existed, so nothing broke, but the committed CSS still carried dead rules for
    the removed ones and no gate could see the drift.

    SKIPs when the Tailwind CLI is absent, which is the common case on a fresh
    clone: the binary is gitignored at scripts/bin/tailwindcss[.exe]. A SKIP is
    printed in the summary and never counts as a pass.

    Also SKIPs when only the npm fallback (`npx tailwindcss@3`) is available,
    because that comparison is not reproducible and its failures are false.
    Autoprefixer's output depends on caniuse-lite, which the standalone binary
    bundles and npm resolves fresh - CI proved it by emitting "Browserslist:
    caniuse-lite is outdated" and then producing a byte-different file of the
    same size. A byte-comparison gate across two toolchains that legitimately
    disagree can only ever be red, and a permanently-red gate is one people
    learn to ignore. Enforced where the toolchain is fixed (developer machines
    and pre-commit); loudly skipped where it is not.
    """
    if not _vendored_tailwind_cli():
        return Result("css-build", SKIP,
                      "no vendored Tailwind CLI at scripts/bin/tailwindcss[.exe]; "
                      "an npm-resolved Tailwind is not byte-reproducible against "
                      "the committed build (caniuse-lite floats), so this cannot "
                      "be verified here")

    proc = _run([sys.executable, "scripts/build_css.py", "--check"])
    output = proc.stdout + proc.stderr
    if "Tailwind CLI unavailable" in output or "SKIP" in output:
        return Result("css-build", SKIP,
                      "Tailwind CLI not installed (scripts/bin/tailwindcss[.exe]); "
                      "cannot verify the committed CSS")
    if proc.returncode == 0:
        return Result("css-build", PASS, "committed CSS matches a rebuild")
    return Result("css-build", FAIL, output.strip()[-800:])


def gate_js_build() -> Result:
    """The committed js/bundles/*.js match what scripts/build_js.py produces.

    Mirrors gate_css_build's rationale for JS: the platform core sequence
    (js/core/00-namespace.js .. 07-dialog.js) is bundled and the bundle is
    committed, same pattern as tailwind-output.css, so the Docker image stays
    Python-only. Unlike the CSS build this needs no external CLI — the
    bundler is pure-stdlib string concatenation — so there is no SKIP path.
    """
    proc = _run([sys.executable, "scripts/build_js.py", "--check"])
    output = proc.stdout + proc.stderr
    if proc.returncode == 0:
        return Result("js-build", PASS, "committed JS bundles match a rebuild")
    return Result("js-build", FAIL, output.strip()[-800:])


def gate_js_syntax() -> Result:
    """Every shipped JS file parses in a real JavaScript engine.

    A SyntaxError is not a style problem: the browser discards the WHOLE file,
    so one bad character silently removes every function it defines and the
    page keeps rendering as though nothing is wrong.

    Added 26 Aug 2026, after a bulk refactor left `await` in a non-async
    function in two files. Every other gate passed -- ruff does not read JS and
    the grep gates match patterns rather than parsing -- and the capability map
    lost all its handlers. Only one smoke assertion caught it, and only because
    that page happened to be covered.
    """
    proc = _run([sys.executable, "scripts/check_js_syntax.py"])
    output = proc.stdout + proc.stderr
    if proc.returncode == 0:
        return Result("js-syntax", PASS, output.strip().splitlines()[-1] if output.strip() else "all JS parses")
    return Result("js-syntax", FAIL, output.strip()[-800:])


def gate_console_reporting(baseline: int) -> Result:
    """Ratchet on console.* calls in shipped JS and templates.

    A console.error is a failure reported to NOBODY: the user sees a control
    that did nothing, or a panel that stayed empty, and cannot tell a failure
    from an empty result. That is the same harm as fabricated data, reached
    from the other side. Each one is either a failure that belongs in
    Platform.toast or an inline error state, or a diagnostic that should not
    ship. console.log is already at zero; this freezes the rest.
    """
    proc = _run([sys.executable, "scripts/check_console_reporting.py", "--count"])
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0:
        return Result("console-reporting", FAIL, output[-400:])
    try:
        count = int(output.splitlines()[-1])
    except (ValueError, IndexError):
        return Result("console-reporting", FAIL, f"unparseable count: {output[-200:]}")
    return Result("console-reporting", PASS if count <= baseline else FAIL,
                  f"[{count} <= {baseline}]", count, baseline)


def gate_vendor_integrity() -> Result:
    """Vendored assets match their recorded provenance.

    The air-gap gate proves nothing external is *referenced*; this proves the local
    copies are the upstream bytes we recorded and not something modified in place.
    Also catches the manifest drifting out of step with the pinned URL list, which
    is easy to do when refreshing one library by hand.
    """
    proc = _run([sys.executable, "scripts/vendor_assets.py", "--verify"])
    output = (proc.stdout + proc.stderr).strip()
    return Result("vendor-integrity", PASS if proc.returncode == 0 else FAIL,
                  output[-1500:])


DEPENDENCY_AUDIT = os.path.join("scripts", "ci", "dependency_audit.py")
DEPENDENCY_BASELINE = os.path.join("scripts", "ci", "dependency_baseline.json")


def gate_dependency_cves() -> Result:
    """No NEW known CVEs in the production dependency set.

    This is the scan an enterprise security review runs before granting network
    admission, so it is better to run it ourselves first. Scoped to
    requirements.txt deliberately: test tooling is not shipped, so a CVE in pytest
    is not part of the deployed attack surface.

    Delegates to scripts/ci/dependency_audit.py rather than calling pip-audit
    itself, so this gate and the CI `dependency-audit` job cannot reach different
    verdicts on the same tree. They did, and it mattered: this gate was
    zero-tolerance while that job ratchets against dependency_baseline.json, so the
    two WeasyPrint advisories requirements.txt accepts *on purpose* (WeasyPrint 68
    needs pydyf>=0.11, which 500'd PDF export) failed here and passed there. The
    effect was that `python scripts/verify.py` could never go green — and a gate
    that is red on every run is a gate everyone learns to ignore, which is exactly
    the failure mode the ratchets elsewhere in this file exist to avoid.

    Accepted risk now lives in one reviewable file. Anything not recorded there
    still fails, and the accepted count is reported on success so a green run
    never reads as "no vulnerabilities".
    """
    proc = _run([sys.executable, DEPENDENCY_AUDIT], timeout=600)
    output = (proc.stdout + proc.stderr).strip()

    if "urlopen error" in output or "Temporary failure in name resolution" in output:
        return Result("dependency-cves", SKIP, "no network access to the advisory database")
    if proc.returncode == 2:
        # pip-audit could not resolve requirements.txt. That is a real problem, not
        # a scanner hiccup: it means the file cannot be installed as written.
        return Result("dependency-cves", FAIL,
                      "pip-audit could not run:\n" + output[-1200:],
                      remediation="fix the conflicting pins in requirements.txt")
    if proc.returncode != 0:
        _, marker, detail = output.partition("NEW advisories not in the baseline:")
        return Result("dependency-cves", FAIL, (detail if marker else output).strip()[:1200],
                      remediation="bump the affected package (watch for a blocking upper "
                                  "bound), or accept it deliberately with "
                                  "scripts/ci/dependency_audit.py --update-baseline "
                                  "and say why in the pull request")

    accepted = 0
    try:
        with open(DEPENDENCY_BASELINE, encoding="utf-8") as fh:
            accepted = sum(len(v) for v in json.load(fh).get("accepted", {}).values())
    except (OSError, ValueError):
        pass

    # Report what was actually FOUND against requirements.txt, not the size of the
    # baseline file. They differ: the baseline also records pytest, which ADR 0005
    # moved out of requirements.txt, so it is no longer in the audited set at all.
    # Showing the baseline size as the measurement would overstate live debt and
    # hide the fact that an entry is ready to be dropped.
    found = accepted
    match = re.search(r"dependency audit: \d+ package\(s\), (\d+) advisories total", output)
    if match:
        found = int(match.group(1))

    detail = "no new vulnerabilities"
    if found:
        detail += (f"; {found} accepted in the baseline — real, unremediated risk a "
                   f"security review will ask about (scripts/ci/dependency_baseline.json)")
    if found < accepted:
        detail += (f"; {accepted - found} baselined advisor"
                   f"{'y is' if accepted - found == 1 else 'ies are'} no longer present — "
                   f"run scripts/ci/dependency_audit.py --update-baseline to lock that in")
    return Result("dependency-cves", PASS, detail, found, accepted)


def gate_boot_health() -> Result:
    """Boot + wiring. Database-free by design — see tests/test_boot_health.py."""
    proc = _run([sys.executable, "-m", "pytest", "tests/test_boot_health.py", "-q", "-p", "no:cacheprovider"])
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-15:]
    return Result("boot-health", PASS if proc.returncode == 0 else FAIL, "\n".join(tail))


def gate_csrf_coverage() -> Result:
    """Every state-changing route is CSRF-protected or on the explicit,
    justified opt-out list in app/_bootstrap/csrf_coverage.py (P-04).
    Database-free, same reasoning as boot-health: create_app() boots fine
    with connection errors caught and logged."""
    proc = _run([sys.executable, "scripts/check_csrf_coverage.py"])
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-25:]
    return Result("csrf-coverage", PASS if proc.returncode == 0 else FAIL, "\n".join(tail))


def gate_schema_drift() -> Result:
    """No column or table drift between the ORM models and the live database.

    ``reconcile-schema`` reports drift in its output, not its exit code, and always
    prints the summary line ``reconcile-schema: N column(s) would add.`` — so the
    count has to be parsed. Matching the phrase alone is a false positive, because
    the summary contains it even when N is 0.
    """
    proc = _run([sys.executable, "-m", "flask", "--app", "manage", "reconcile-schema", "--dry-run"])
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0:
        return Result("schema-drift", FAIL, output[-2000:])

    summary = re.search(r"reconcile-schema:\s+(\d+)\s+column\(s\)", output)
    if not summary:
        # No parseable summary means the check did not actually run to completion.
        # Report that rather than inferring success from the absence of bad news.
        return Result("schema-drift", FAIL,
                      "could not find the 'reconcile-schema: N column(s)' summary line:\n"
                      + output[-1500:])

    drifted_columns = int(summary.group(1))
    absent_tables = 0
    tables = re.search(r"(\d+)\s+table\(s\)\s+absent", output)
    if tables:
        absent_tables = int(tables.group(1))

    # Reverse drift: columns the DATABASE has that the models do not, NOT NULL and
    # undefaulted. This gate previously reported clean against a database whose
    # value_streams.organization_id was NOT NULL while the model omitted the column
    # entirely, so every INSERT failed — the check only ever ran model -> database.
    blocking = 0
    rev = re.search(r"(\d+)\s+column\(s\) present in the DATABASE", output)
    if rev:
        blocking = int(rev.group(1))

    if drifted_columns or absent_tables or blocking:
        detail_lines = [
            ln for ln in output.splitlines()
            if ln.startswith(("  + ", "  ! ")) or "table(s) absent" in ln
            or "present in the DATABASE" in ln
        ][:20]
        return Result(
            "schema-drift", FAIL,
            f"{drifted_columns} drifted column(s), {absent_tables} absent table(s), "
            f"{blocking} model-missing NOT NULL column(s):\n" + "\n".join(detail_lines),
            measured=drifted_columns + absent_tables + blocking, baseline=0,
            remediation=(
                "run: flask --app manage init-db && flask --app manage reconcile-schema; "
                "for model-missing columns, declare them on the model instead"
            ),
        )
    return Result("schema-drift", PASS, "no drift detected", measured=0, baseline=0)


def gate_tests() -> Result:
    """Behavioural regression. Runs smoke in its own process, as CI does.

    tests/ and tests/smoke/ cannot share a pytest process. Both conftest trees
    build a Flask app, and the second registration is rejected -

        The setup method 'route' can no longer be called on the blueprint
        'codegen'. It has already been registered at least once

    - which leaves the smoke live_server on a degraded app whose login POST
    never responds. Every archetype sign-in then times out after 90s: 31
    failures and 9 errors, reproducible in BOTH collection orders, while each
    suite passes cleanly on its own.

    CI does not hit this, by accident rather than design: its `tests` job never
    runs `playwright install`, so the browser fixture skips and takes the smoke
    tests with it. Only the `smoke` job has a browser, and it runs
    `pytest tests/smoke` on its own. Locally a browser IS present, so the
    collision is real here and invisible there.

    Two invocations rather than --ignore, so a local run still covers smoke
    instead of quietly dropping the only browser tests in the repo.
    """
    parts = [
        ("unit+integration", ["-p", "no:cacheprovider",
                              "-p", "scripts.route_verification_audit",
                              "--ignore=tests/test_boot_health.py",
                              "--ignore=tests/smoke"]),
        ("smoke", ["-p", "no:cacheprovider", "tests/smoke"]),
    ]
    summaries, failed = [], []
    for label, args in parts:
        proc = _run(
            [sys.executable, "-m", "pytest", "-q"] + args,
            timeout=TEST_SUITE_TIMEOUT_SECONDS,
        )
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-12:]
        summaries.append("[%s] %s" % (label, tail[-1] if tail else "no output"))
        if proc.returncode != 0:
            failed.append(label)
            summaries.extend("    " + line for line in tail)
    return Result("tests", PASS if not failed else FAIL, "\n".join(summaries))


# ---------------------------------------------------------------- registry


def build_gates(baseline: dict) -> list[Gate]:
    return [
        Gate("compile", "Every module bytecode-compiles", "command", gate_compile,
             remediation="fix the reported SyntaxError", tags=["static", "fast"]),
        Gate("undefined-exports", "No __all__ entry names a missing symbol", "zero",
             gate_undefined_exports, remediation="remove the stale __all__ entry",
             tags=["static", "fast"]),
        Gate("undefined-names", "No new undefined names (ruff F821)", "ratchet",
             lambda: gate_undefined_names(baseline["undefined_names"]),
             remediation="add the missing import, or fix the typo", tags=["static", "fast"]),
        Gate("redefinitions", "No new redefinitions (ruff F811)", "ratchet",
             lambda: gate_redefinitions(baseline["redefinitions"]),
             remediation="delete the shadowed definition", tags=["static", "fast"]),
        Gate("lint-core", "No new correctness lint findings", "ratchet",
             lambda: gate_lint_core(baseline["lint_core"]),
             remediation="run: python -m ruff check . --fix", tags=["static", "fast"]),
        Gate("design-tokens", "No new raw Tailwind colours (DESIGN.md)", "ratchet",
             lambda: gate_design_tokens(baseline["design_tokens"]),
             remediation="use semantic tokens; see the table in DESIGN.md",
             tags=["static", "ui"]),
        Gate("raw-fetch-sites",
             "No new raw fetch() sites bypassing Platform.fetch",
             "ratchet",
             lambda: gate_raw_fetch_sites(baseline["raw_fetch_sites"]),
             remediation="use Platform.fetch, or mark 'raw-fetch-ok: <reason>'",
             tags=["static", "ui"]),
        Gate("design-tokens-extended",
             "No new raw colours in the remaining families (emerald/orange/...)",
             "ratchet",
             lambda: gate_design_tokens_extended(baseline["design_tokens_extended"]),
             remediation="use success/warning/info/destructive or layer tokens",
             tags=["static", "ui"]),
        Gate("shell-conformance", "No new pages off the platform shell (header macro + page width)",
             "ratchet", lambda: gate_shell_conformance(baseline["shell_conformance"]),
             remediation="use page_header/page_shell and p-6 space-y-6; see DESIGN.md, or add 'shell-ok: <reason>'",
             tags=["static", "ui"]),
        Gate("nav-coverage",
             "No business-architecture output with routes is missing from every sidebar",
             "ratchet", lambda: gate_nav_coverage(baseline["nav_coverage"]),
             remediation="add a link to the owning persona's zone in app/utils/role_access.py",
             tags=["static"]),
        Gate("control-labels", "every button has an accessible name", "ratchet",
             lambda: gate_control_labels(baseline["control_labels"]),
             remediation="add an aria-label naming the ACTION ('Delete board', not "
                         "'trash icon'), or append 'control-label-ok: <reason>'",
             tags=["static", "ui", "a11y"]),
        Gate("alpine-await", "no await/async in an Alpine attribute expression",
             "ratchet", lambda: gate_alpine_await(baseline["alpine_await"]),
             remediation="rewrite as a promise chain (.then/.catch) and set unmeasured "
                         "values to null (never 0) on the error path, or append "
                         "'alpine-await-ok: <reason>'",
             tags=["static", "ui"]),
        Gate("attr-quoting", "no tojson inside a double-quoted HTML attribute",
             "ratchet", lambda: gate_attr_quoting(baseline["attr_quoting"]),
             remediation="switch the attribute delimiter to single quotes (tojson "
                         "escapes ' but not \"); if the expression already contains "
                         "single-quoted JS strings, double-quote those or move the "
                         "payload to a data-* attribute, or append "
                         "'attr-quoting-ok: <reason>'",
             tags=["static", "ui"]),
        Gate("input-labels", "every form control has a label", "ratchet",
             lambda: gate_input_labels(baseline["input_labels"]),
             remediation="add a <label for=...> or an aria-label (a placeholder is not "
                         "a label), or append 'input-label-ok: <reason>'",
             tags=["static", "ui", "a11y"]),
        Gate("macro-kwargs", "every macro call uses that macro's parameter names",
             "ratchet", lambda: gate_macro_kwargs(baseline["macro_kwargs"]),
             remediation="open the macro named in the message and use ITS parameter "
                         "names (a same-named macro in another file is the usual "
                         "cause), or append 'macro-kwargs-ok: <reason>'",
             tags=["static", "ui"]),
        Gate("nested-jinja", "no Jinja expression opens inside another",
             "ratchet", lambda: gate_nested_jinja(baseline["nested_jinja"]),
             remediation="pass the value itself instead of a quoted placeholder, "
                         "or append 'nested-jinja-ok: <reason>'",
             tags=["static", "ui"]),
        Gate("credential-autofill", "every credential field declares an autocomplete value",
             "ratchet", lambda: gate_credential_autofill(baseline["credential_autofill"]),
             remediation="autocomplete=\"current-password\" where the user's own password belongs, \"new-password\" on any third-party secret; or append 'autofill-ok: <reason>'",
             tags=["static", "security"]),
        Gate("ai-approval-honoured", "the agent honours the operator's ai approval control",
             "ratchet", lambda k='ai_approval_honoured': gate_ai_approval_honoured(baseline[k]),
             tags=["static", "architecture", "ai"]),
        Gate("archimate-backbone", "every motivation create syncs an ArchiMate element",
             "ratchet", lambda: gate_archimate_backbone(baseline["archimate_backbone"]),
             tags=["static", "architecture"]),
        Gate("empty-state-cta", "an empty state offers the user a way forward",
             "ratchet", lambda k='empty_state_cta': gate_empty_state_cta(baseline[k]),
             remediation="give the empty state its cta_text/cta_label + cta_href, or append 'empty-state-ok: <reason>'",
             tags=["static", "product"]),
        Gate("role-gate-coverage", "every role in the delivery contract has gates enforcing it",
             "ratchet", lambda k='role_gate_coverage': gate_role_gate_coverage(baseline[k]),
             remediation="build a gate for the role and tag it, or append "
                         "'role-gate-ok: <reason>' to that row of "
                         "docs/DELIVERY_CONTRACT.md's role table",
             tags=["static", "governance"]),
        Gate("business-layer-backbone", "capabilities and value streams are in the ArchiMate model",
             "ratchet", lambda k='business_layer_backbone': gate_business_layer_backbone(baseline[k]),
             remediation="call sync_archimate_element() after the create, or append 'business-backbone-ok: <reason>'",
             tags=["static", "business", "architecture"]),
        Gate("api-envelope", "one API, one response shape",
             "ratchet", lambda k='api_envelope': gate_api_envelope(baseline[k]),
             remediation="return through success_response()/error_response(), or append 'envelope-ok: <reason>'",
             tags=["static", "integration"]),
        Gate("collapsed-nav-affordance", "the collapsed sidebar is still navigable",
             "ratchet", lambda k='collapsed_nav_affordance': gate_collapsed_nav_affordance(baseline[k]),
             remediation="add a title naming the destination, or append 'collapsed-nav-ok: <reason>'",
             tags=["static", "rendered", "ui"]),
        Gate("nav-icon-ambiguity", "one icon, one destination within a persona's menu",
             "ratchet", lambda k='nav_icon_ambiguity': gate_nav_icon_ambiguity(baseline[k]),
             remediation="give each destination its own icon, or append 'nav-icon-ok: <reason>'",
             tags=["static", "wayfinding", "ui"]),
        Gate("nav-label-clarity", "one name, one destination, and it fits",
             "ratchet", lambda k='nav_label_clarity': gate_nav_label_clarity(baseline[k]),
             remediation="rename the destination or shorten the label, or append 'nav-label-ok: <reason>'",
             tags=["static", "content", "ui"]),
        Gate("handoff-continuity", "every handoff reaches a reachable next actor",
             "ratchet", lambda k='handoff_continuity': gate_handoff_continuity(baseline[k]),
             remediation="surface the state on a screen a persona can reach, or append 'handoff-ok: <reason>'",
             tags=["static", "handoff", "journey"]),
        Gate("metric-provenance", "every number shown came from a query",
             "ratchet", lambda k='metric_provenance': gate_metric_provenance(baseline[k]),
             remediation="compute it or send None, or append 'metric-provenance-ok: <reason>'",
             tags=["static", "evidence", "correctness"]),
        Gate("raw-sql-columns", "raw SQL only names columns that exist",
             "ratchet", lambda k='raw_sql_columns': gate_raw_sql_columns(baseline[k]),
             remediation="fix the column name, or append 'raw-sql-columns-ok: <reason>'",
             tags=["static", "schema", "db"]),
        Gate("actionable-rows", "a table of records offers a way to act on them",
             "ratchet", lambda k='actionable_rows': gate_actionable_rows(baseline[k]),
             remediation="link the row to its record or give it the control that moves it on, or append 'actionable-rows-ok: <reason>'",
             tags=["static", "handoff", "rendered", "product"]),
        Gate("placeholder-copy", "labels say what the thing is",
             "ratchet", lambda k='placeholder_copy': gate_placeholder_copy(baseline[k]),
             remediation="name the input, or append 'placeholder-copy-ok: <reason>' saying who supplies the word",
             tags=["static", "content", "rendered"]),
        Gate("ai-layer-coverage", "the AI can model ArchiMate, not just discuss it",
             "ratchet", lambda k='ai_layer_coverage': gate_ai_layer_coverage(baseline[k]),
             remediation="give the AI a tool that knows the element's semantics, or append 'ai-layer-ok: <reason>'",
             tags=["static", "ai", "architecture"]),
        Gate("canonical-store", "one concept, one store",
             "ratchet", lambda k='canonical_store': gate_canonical_store(baseline[k]),
             tags=["static", "architecture"]),
        Gate("ai-evidence-rules", "every AI persona charter carries the no-fabrication rules",
             "ratchet", lambda k='ai_evidence_rules': gate_ai_evidence_rules(baseline[k]),
             remediation="interpolate {_EVIDENCE_RULES} into the charter, or append 'evidence-rules-ok: <reason>'",
             tags=["static", "ai"]),
        Gate("ai-tool-guard", "the AI write path keeps its single permission choke point",
             "ratchet", lambda k='ai_tool_guard': gate_ai_tool_guard(baseline[k]),
             remediation="route the call through ToolExecutor.execute, declare the tool's \"mutates\" flag honestly, or append 'ai-tool-guard-ok: <reason>'",
             tags=["static", "ai", "security"]),
        Gate("ai-untrusted-content", "retrieved content enters the system prompt fenced, after the charter",
             "ratchet", lambda k='ai_untrusted_content': gate_ai_untrusted_content(baseline[k]),
             remediation="wrap it in fence_untrusted(\"<LABEL>\", value) and append it after the charter, or append 'untrusted-ok: <reason>'",
             tags=["static", "ai", "security"]),
        Gate("cache-tenancy", "a cache over tenant data is keyed by the tenant",
             "ratchet", lambda: gate_cache_tenancy(baseline["cache_tenancy"]),
             remediation="include g.current_org_id in the key, cache nothing without "
                         "a tenant context, and bound the map; or append "
                         "'cache-tenancy-ok: <reason>' saying why the contents are "
                         "tenant-independent",
             tags=["static", "security"]),
        Gate("authz-widening", "no role is granted from a field the user's own record carries",
             "ratchet", lambda k='authz_widening': gate_authz_widening(baseline[k]),
             remediation="gate the contribution on user.can(Permission.GENERAL) / ADMINISTER, or append 'authz-widening-ok: <reason>'",
             tags=["static", "security"]),
        Gate("nullable-columns", "a NOT NULL column carries a default reconcile-schema can apply",
             "ratchet", lambda k='nullable_columns': gate_nullable_columns(baseline[k]),
             remediation="give the column a default= or server_default=, make it nullable, or append 'nullable-ok: <reason>'",
             tags=["static", "schema"]),
        Gate("page-cost", "no query loads every row only to count them",
             "ratchet", lambda k='page_cost': gate_page_cost(baseline[k]),
             remediation="replace len(q.all()) with q.count(), or append 'page-cost-ok: <reason>'",
             tags=["static", "performance"]),
        Gate("evidence-contract", "every behavioural change carries its measurement, "
             "every gate carries its proof",
             "ratchet", lambda: gate_evidence_contract(baseline["evidence_contract"]),
             remediation="land the test with the change, or add an 'Evidence: <command> "
                         "-> <result>' trailer to the commit; for a gate, add a "
                         "'Proven-against:' line naming the input you watched it fail "
                         "on (docs/DELIVERY_CONTRACT.md)",
             tags=["static", "process"]),
        Gate("persona-vocabularies", "every persona list reconciles with VALID_ROLES",
             "ratchet", lambda: gate_persona_vocabularies(baseline["persona_vocabularies"]),
             remediation="add the role to app/auth/sso.py's DEFAULT_GROUP_ROLE_MAP so it "
                         "can be provisioned, or list the charter in ASPIRATIONAL in "
                         "scripts/check_persona_vocabularies.py with the reason it has "
                         "no role yet",
             tags=["static", "correctness"]),
        Gate("inline-handlers", "no inline event handler the CSP refuses to run",
             "ratchet", lambda: gate_inline_handlers(baseline["inline_handlers"]),
             remediation="use data-confirm / data-autosubmit (wired in "
                         "app/static/js/ui/modal.js), bind the listener in a "
                         "nonce'd <script> block, or use Alpine's @click/@submit; "
                         "or append 'inline-handler-ok: <reason>'",
             tags=["static", "ui", "security"]),
        Gate("unreachable-actions", "no handler branch its own validator rejects first",
             "ratchet", lambda: gate_unreachable_actions(baseline["unreachable_actions"]),
             remediation="either delete the branch (the product does not have that "
                         "feature) or add the value to the whitelist; if it is "
                         "unreachable on purpose append 'unreachable-action-ok: <reason>'",
             tags=["static", "correctness"]),
        Gate("journey-coverage", "every persona has a journey proving they can do their job",
             "ratchet", lambda: gate_journey_coverage(baseline["journey_coverage"]),
             remediation="add a test under tests/journeys/ that signs in as the persona, "
                         "performs its write, and asserts the result BOTH persisted and is "
                         "visible on the page they look at next (docs/TESTING_STANDARD.md, "
                         "Level 9); or append 'journey-coverage-ok: <reason>' naming a "
                         "persona that genuinely cannot act",
             tags=["static", "journey"]),
        Gate("air-gap", "No UI assets loaded from public CDNs", "ratchet",
             lambda: gate_air_gap(baseline["air_gap"]),
             remediation="vendor the asset into app/static/ and use url_for('static', ...)",
             tags=["static", "ui", "airgap"]),
        Gate("raw-sql-tenancy", "raw SQL on tenant tables without an org predicate",
             "ratchet", lambda: gate_raw_sql_tenancy(baseline["raw_sql_tenancy"]),
             remediation="scope the query, or append 'tenancy-ok: <reason>'",
             tags=["static", "security"]),
        Gate("tenant-scoping", "ORM queries on tenant-owned-but-unmixed models without an org predicate",
             "ratchet", lambda: gate_tenant_scoping(baseline["tenant_scoping"]),
             remediation="scope the query, or append 'tenant-scoping-ok: <reason>'",
             tags=["static", "security"]),
        Gate("sidebar-links", "no persona sidebar exceeds its link budget", "ratchet",
             lambda: gate_sidebar_links(baseline.get("sidebar_links", 25)),
             remediation="run scripts/check_sidebar_links.py; trim the offending "
                         "role's zones in app/utils/role_access.py",
             tags=["static", "ui"]),
        Gate("template-syntax", "every Jinja template parses", "zero",
             gate_template_syntax,
             remediation="see the reported line; Jinja does not nest {# #} comments",
             tags=["static", "ui"]),
        Gate("template-references", "every include/extends target exists", "zero",
             gate_template_references,
             remediation="create the missing partial, correct the path, or delete the "
                         "dead reference; run scripts/check_template_references.py",
             tags=["static", "ui"]),
        Gate("alpine-data-binding", "every x-data resolves under the CSP evaluator", "zero",
             gate_alpine_data_binding,
             remediation='use x-data="component()" with a top-level '
                         "`function component()` assigned to window; Alpine.data() "
                         "plus a bare name mounts an empty component silently",
             tags=["static", "ui"]),
        Gate("broken-surfaces", "front-end targets resolve to real routes", "ratchet",
             lambda: gate_broken_surfaces(baseline.get("broken_surfaces", 479)),
             remediation="run scripts/check_broken_surfaces.py; repoint the URL, "
                         "remove the dead control, or report the failure to the user",
             # NOT "static". This gate boots the Flask app to read its real
             # url_map, and CI's static-gates job installs only ruff/pip-audit/
             # jinja2 and says so in its own header: "No database, no app boot."
             # Tagged static, it crashed there on every run for a week - and
             # because it crashed rather than reported findings, the failure
             # read as a gate failure rather than as "this gate cannot run
             # here". It belongs with boot-health, which installs requirements
             # and already boots the app for the same reason.
             tags=["boot", "ui"]),
        Gate("dynamic-link-prefixes",
             "concatenated href/fetch links whose literal prefix is a dead route (ARCH-043)",
             "ratchet",
             lambda: gate_dynamic_link_prefixes(baseline.get("dynamic_link_prefixes", 0)),
             remediation="run scripts/check_dynamic_link_prefixes.py; repoint the "
                         "literal prefix at the current route",
             # NOT "static" - same reason as broken-surfaces: boots the app to
             # read the real url_map.
             tags=["boot", "ui"]),
        Gate("fetch-guards", "no fetch parsed without checking the response", "ratchet",
             lambda: gate_fetch_guards(baseline.get("fetch_guards", 107)),
             remediation="run scripts/check_fetch_guards.py; add if (!resp.ok) throw, "
                         "and make the catch tell the user",
             tags=["static", "ui"]),
        Gate("ui-contract", "no new native dialogs / onclick= / typeless buttons / arbitrary px-type (DESIGN.md)",
             "ratchet", lambda: gate_ui_contract(baseline.get("ui_contract", 1969)),
             remediation="run scripts/check_ui_contract.py; use Platform modals, Alpine @click, "
                         "add type= to buttons, and text-xs instead of text-[Npx]",
             tags=["static", "ui"]),
        Gate("error-signalling", "no API error path that answers 200", "zero",
             gate_error_signalling,
             remediation="run scripts/check_error_signalling.py; return an explicit "
                         "4xx/5xx so the client's !response.ok can see the failure",
             tags=["static", "correctness"]),
        Gate("silent-data", "no server failure returned to the caller as data", "zero",
             gate_silent_data,
             remediation="run scripts/check_silent_data.py; let it propagate, or log "
                         "and return None - never [] or 0, which read as measured data",
             tags=["static", "correctness"]),
        Gate("dead-interactions", "no control that silently does nothing", "zero",
             gate_dead_interactions,
             remediation="run scripts/check_dead_interactions.py; use `if (!r.ok) throw` "
                         "and report the failure to the user, or switch to Platform.fetch",
             tags=["static", "ui"]),
        Gate("macro-import-context", "script-bearing macros imported with context", "zero",
             gate_macro_import_context,
             remediation="append ` with context` to the import; run "
                         "scripts/check_macro_import_context.py",
             tags=["static", "ui"]),
        Gate("asset-urls", "no doubled '?' asset URL; no stylesheet/script included twice per template",
             "zero", gate_asset_urls,
             remediation="run scripts/check_asset_urls.py; url_for/asset_url already "
                         "version static assets — never hand-append '?v=' in a template, "
                         "and include a shared stylesheet/script from one place only",
             tags=["static", "ui"]),
        Gate("qa-register", "every QA remediation register finding is closed", "zero",
             gate_qa_register,
             remediation="run scripts/check_qa_register.py to list what is still open; "
                         "close the finding and record its commit in "
                         "qa_findings_status.json - do not relax this gate to enable a deploy",
             tags=["static", "qa"]),
        Gate("null-filters", "default() never feeds a len()-calling filter", "zero",
             gate_null_filters,
             remediation="add the boolean argument: default('x', true) - plain "
                         "default() replaces undefined, not None",
             tags=["static", "ui"]),
        Gate("fabricated-data", "no invented data can reach the UI", "zero",
             gate_fabricated_data,
             remediation="render an explicit empty/error state instead of inventing data; "
                         "if genuinely fine, append 'fabricated-ok: <reason>'",
             tags=["static", "ui"]),
        Gate("test-data-in-queries",
             "no production query hides rows named like test fixtures",
             "zero", gate_test_data_in_queries,
             remediation="purge the test rows instead of filtering them out of the "
                         "product; a customer whose data matches the pattern loses it "
                         "with no explanation",
             tags=["static"]),
        Gate("fabricated-data-server",
             "server-side fabrication and dead escape-hatch markers",
             "ratchet",
             lambda: gate_fabricated_data_server(baseline["fabricated_data_server"]),
             remediation="return None (rendered as an em dash) rather than 0 or a "
                         "severity word from an except; and use the exact spelling "
                         "'fabricated-ok: <reason>' -- any other 'fabricated-*-ok' "
                         "variant suppresses nothing",
             tags=["static", "ui"]),
        # NOT tagged "static": it compares requirements.txt against what is
        # actually importable, so it needs the app's dependencies installed. The
        # static-gates CI job deliberately installs only ruff and pip-audit, where
        # this reported 81 of 85 pins "not installed" - a true statement about an
        # environment the gate was never meant to judge. It runs in the
        # boot-health job, which does install requirements.txt.
        Gate("deployed-deps", "installed packages satisfy the pinned floors", "zero",
             gate_deployed_deps,
             remediation="rebuild the image (deploy.sh builds) or pip install -r requirements.txt",
             tags=["deps", "security"]),
        Gate("js-build", "committed js/bundles/*.js match a rebuild", "command",
             gate_js_build,
             remediation="python scripts/build_js.py   and commit the result",
             tags=["static"]),
        Gate("console-reporting", "console.* calls in shipped JS and templates", "ratchet",
             lambda: gate_console_reporting(baseline["console_reporting"]),
             remediation="surface the failure via Platform.toast or an inline error state, or delete the diagnostic",
             tags=["static", "ui"]),
        Gate("js-syntax", "every shipped JS file parses in a real engine", "command",
             gate_js_syntax,
             remediation="fix the reported SyntaxError; the browser discards the whole file",
             tags=["static", "ui"]),
        Gate("css-build", "committed tailwind-output.css matches a rebuild", "command",
             gate_css_build,
             remediation="python scripts/build_css.py   and commit the result",
             tags=["static", "ui"]),
        Gate("sri", "Subresource Integrity hashes match their files", "zero",
             gate_sri,
             remediation="recompute the hash for the file the tag actually loads",
             tags=["static", "ui", "airgap", "security"]),
        Gate("vendor-integrity", "Vendored assets match their manifest", "command",
             gate_vendor_integrity,
             remediation="run: python scripts/vendor_assets.py",
             tags=["static", "ui", "airgap", "security"]),
        Gate("dependency-cves", "No NEW known CVEs in shipped dependencies", "ratchet",
             gate_dependency_cves,
             remediation="bump the affected package (watch for blocking upper bounds)",
             tags=["deps", "security"]),
        Gate("boot-health", "App boots; every url_for endpoint resolves", "command",
             gate_boot_health,
             remediation="see the failure message in tests/test_boot_health.py",
             tags=["runtime"]),
        Gate("csrf-coverage", "Every write route is CSRF-protected or a justified opt-out", "command",
             gate_csrf_coverage,
             remediation="run scripts/check_csrf_coverage.py; justify the exemption in "
                         "app/_bootstrap/csrf_coverage.py or remove it",
             tags=["static", "security", "runtime"]),
        Gate("schema-drift", "Live DB matches the ORM models", "command",
             gate_schema_drift, needs_db=True,
             remediation="run: flask --app manage reconcile-schema", tags=["runtime", "db"]),
        Gate("tests", "Test suite passes", "command", gate_tests, needs_db=True,
             remediation="fix the failing test", tags=["runtime", "db"]),
        # Keep this after ``tests``: the unit phase writes fresh ignored
        # route_verification.json evidence via the audit plugin.  CI runs this
        # gate separately after its own audited pytest command.
        Gate("nav-verified",
             "No new sidebar route goes untested",
             "ratchet", lambda: gate_nav_verified(baseline["nav_verified"]),
             remediation="if routes are listed above: add a test that loads each, or "
                         "remove it from the sidebar. If it says NO AUDIT DATA, nothing "
                         "was measured -- run 'pytest -p scripts.route_verification_audit' "
                         "first; the two failures need opposite responses",
             # Deliberately untagged, and that is a trap worth knowing about: an
             # untagged gate is unreachable from EVERY --tag invocation, so only a
             # bare `python scripts/verify.py` ever runs it.
             tags=[]),
    ]


DEFAULT_BASELINE = {
    "undefined_names": 296,
    "redefinitions": 73,
    "lint_core": 4482,
    "design_tokens": 1255,
    "design_tokens_extended": 4552,
    "air_gap": 78,
    "control_labels": 0,
    "input_labels": 0,
    "macro_kwargs": 0,
    "alpine_await": 0,
    "attr_quoting": 0,
    "journey_coverage": 0,
    "unreachable_actions": 0,
    "inline_handlers": 0,
    "persona_vocabularies": 0,
    "evidence_contract": 34,
    "ai_evidence_rules": 0,
    "ai_tool_guard": 0,
    "ai_untrusted_content": 0,
    "authz_widening": 0,
    "nullable_columns": 1208,
    "page_cost": 0,
    "credential_autofill": 0,
    "nested_jinja": 0,
    "cache_tenancy": 0,
    "ai_approval_honoured": 0,
    "canonical_store": 0,
    "ai_layer_coverage": 54,
    "placeholder_copy": 59,
    "actionable_rows": 0,
    "raw_sql_columns": 0,
    "handoff_continuity": 0,
    "metric_provenance": 0,
    "collapsed_nav_affordance": 0,
    "nav_icon_ambiguity": 0,
    "nav_label_clarity": 0,
    "business_layer_backbone": 18,
    "api_envelope": 850,
    "role_gate_coverage": 0,
    "empty_state_cta": 0,
    "archimate_backbone": 0,
}


def load_baseline() -> dict:
    if BASELINE_PATH.exists():
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        return {**DEFAULT_BASELINE, **data.get("ratchets", {})}
    return dict(DEFAULT_BASELINE)


def save_baseline(ratchets: dict, note: str) -> None:
    BASELINE_PATH.write_text(
        json.dumps(
            {
                "_comment": (
                    "Ratchet baselines for scripts/verify.py. Lowering a number is routine "
                    "(run --update-baseline after a cleanup). Raising one is a deliberate "
                    "regression and must be justified in review."
                ),
                "_note": note,
                "ratchets": ratchets,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--gate", action="append", help="run only this gate (repeatable)")
    parser.add_argument("--tag", action="append", help="run only gates with this tag")
    parser.add_argument("--require-db", action="store_true",
                        help="fail DB-dependent gates instead of skipping (use in CI)")
    parser.add_argument("--update-baseline", action="store_true",
                        help="re-measure ratchets and write verification_baseline.json")
    args = parser.parse_args(argv)

    _force_utf8_console()
    os.chdir(REPO_ROOT)
    baseline = load_baseline()
    gates = build_gates(baseline)

    all_gate_names = [g.name for g in gates]
    if args.gate:
        wanted = set(args.gate)
        unknown = wanted - {g.name for g in gates}
        if unknown:
            parser.error(f"unknown gate(s): {', '.join(sorted(unknown))}")
        gates = [g for g in gates if g.name in wanted]
    if args.tag:
        gates = [g for g in gates if set(args.tag) & set(g.tags)]
    # Everything the filter removed. A filtered run has to say so: `--tag static`
    # reads as a full run and is not one - it excludes broken-surfaces,
    # and dynamic-link-prefixes, both of which boot the app
    # and so is deliberately untagged `static`, plus nav-verified, which carries
    # no tags at all and is therefore unreachable from EVERY --tag invocation.
    # A red broken-surfaces sat unnoticed on deployed main for exactly this
    # reason: the pre-deploy command everyone ran could not see it, and its
    # "31 passed, 0 failed" line looked like proof the tree was clean.
    not_run = [n for n in all_gate_names if n not in {g.name for g in gates}]

    db_ok, db_reason = database_available()
    results: list[Result] = []

    for gate in gates:
        if gate.needs_db and not db_ok:
            if args.require_db:
                results.append(Result(gate.name, FAIL,
                                      f"database required but unavailable: {db_reason}",
                                      remediation="start PostgreSQL and set TEST_DATABASE_URL"))
            else:
                results.append(Result(gate.name, SKIP, f"no database: {db_reason}",
                                      remediation="start PostgreSQL and set TEST_DATABASE_URL"))
            continue
        started = time.time()
        try:
            result = gate.runner()
        except subprocess.TimeoutExpired:
            # Say it timed out and how to give it longer. The old message ended
            # "-> fix the failing test", which sends the reader hunting a failure
            # that may not exist. A slow gate and a red gate are different findings
            # and must not read the same.
            result = Result(
                gate.name,
                FAIL,
                "timed out -- the gate ran out of time, which is not the same as a "
                "failing test. Raise ARCHIE_TEST_SUITE_TIMEOUT (seconds) if this "
                "hardware is simply slower than the default allows.",
            )
        except Exception as exc:  # noqa: BLE001 — a broken gate must report, not crash the run
            result = Result(gate.name, FAIL, f"{exc.__class__.__name__}: {exc}")
        result.duration_s = round(time.time() - started, 1)
        if result.status == FAIL and not result.remediation:
            result.remediation = gate.remediation
        results.append(result)

    if args.update_baseline:
        measured = {r.name.replace("-", "_"): r.measured for r in results if r.measured is not None}
        new = {**baseline, **{k: v for k, v in measured.items() if k in baseline}}
        lowered = {k: (baseline[k], new[k]) for k in new if new[k] < baseline.get(k, new[k])}
        save_baseline(new, f"updated {time.strftime('%Y-%m-%d')}")
        print(f"baseline written to {BASELINE_PATH.name}")
        for key, (old, cur) in lowered.items():
            print(f"  lowered {key}: {old} -> {cur}")
        return 0

    failed = [r for r in results if r.status == FAIL]
    skipped = [r for r in results if r.status == SKIP]

    if args.json:
        print(json.dumps({
            "ok": not failed,
            "database_available": db_ok,
            "database_detail": db_reason,
            "summary": {"pass": len(results) - len(failed) - len(skipped),
                        "fail": len(failed), "skip": len(skipped),
                        "not_run": len(not_run)},
            "partial_run": bool(not_run),
            "not_run": not_run,
            "gates": [r.__dict__ for r in results],
        }, indent=2))
        return 1 if failed else 0

    width = max(len(r.name) for r in results) if results else 10
    print("\nArchie verification")
    print("-" * (width + 46))
    for r in results:
        mark = {PASS: "ok  ", FAIL: "FAIL", SKIP: "skip"}[r.status]
        measure = ""
        if r.measured is not None:
            arrow = "<=" if r.status == PASS else ">"
            measure = f"  [{r.measured} {arrow} {r.baseline}]"
        print(f"  {mark}  {r.name:<{width}}  {r.duration_s:>5.1f}s{measure}")
    print("-" * (width + 46))

    for r in failed:
        print(f"\nFAIL: {r.name}")
        if r.detail:
            print("\n".join(f"    {ln}" for ln in r.detail.splitlines()[:20]))
        if r.remediation:
            print(f"    -> {r.remediation}")

    if skipped:
        print(f"\n{len(skipped)} gate(s) skipped and therefore NOT verified:")
        for r in skipped:
            print(f"    {r.name}: {r.detail}")
        print("    CI runs with --require-db so these cannot be silently skipped there.")

    if not_run:
        print(f"\n{len(not_run)} gate(s) EXCLUDED BY THE FILTER and therefore NOT verified:")
        for name in not_run:
            print(f"    {name}")
        print("    This is a PARTIAL run. It is not evidence the tree is clean.")
        print("    Before a deploy run the full set:  python scripts/verify.py")

    summary = (f"\n{len(results) - len(failed) - len(skipped)} passed, "
               f"{len(failed)} failed, {len(skipped)} skipped")
    if not_run:
        summary += f", {len(not_run)} not run (PARTIAL RUN)"
    print(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
