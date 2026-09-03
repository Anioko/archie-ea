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

# The PostgreSQL-backed suite currently takes about 26 minutes on the supported
# Windows development environment.  Keep a bounded subprocess, but do not let
# the generic 15-minute command timeout turn a fully progressing suite into a
# false release failure.
TEST_SUITE_TIMEOUT_SECONDS = 3600


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
    ``-p scripts.route_verification_audit``. Stale or missing data reports the
    full nav set as unverified, which fails loudly rather than passing on
    absent evidence.
    """
    proc = _run([sys.executable, "scripts/route_verification_audit.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
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
    proc = _run([sys.executable, "scripts/check_fabricated_data.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("fabricated-data", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count == 0 else "run scripts/check_fabricated_data.py to list them"
    return Result("fabricated-data", PASS if count == 0 else FAIL, detail, count, 0)


def gate_stale_models() -> Result:
    """No RETIRED LLM model id may appear in shipped code — a retired id 404s in
    production. The single source of truth is model_defaults.py; this keeps a
    retired id from creeping back anywhere else. Escape hatch: 'stale-model-ok'.
    """
    proc = _run([sys.executable, "scripts/check_stale_models.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("stale-models", FAIL, f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count == 0 else "run scripts/check_stale_models.py to list them"
    return Result("stale-models", PASS if count == 0 else FAIL, detail, count, 0)


def gate_breadcrumb_coverage() -> Result:
    """Every routed page with a header must carry a breadcrumb (Fortune-500 UI
    baseline). Partials are excluded; escape hatch is 'breadcrumb-ok:'."""
    proc = _run([sys.executable, "scripts/check_breadcrumb_coverage.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("breadcrumb-coverage", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count == 0 else "run scripts/check_breadcrumb_coverage.py to list them"
    return Result("breadcrumb-coverage", PASS if count == 0 else FAIL, detail, count, 0)


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


def gate_llm_boundary(baseline: int) -> Result:
    """Deterministic codegen emitters must never call the LLM directly — ratchet @ 0.

    The genome→artifact emitters (`genome_to_bundle` and any
    `genome_to_<domain>_bundle`/`emit_*`) are the reproducible, testable core of
    the codegen re-architecture. The LLM may only propose schema-validated genome
    edits, never emit a final artifact (ADR 0010; 03_integration.md §2). This
    counts direct `_call_llm`/`LLMService` references inside those files and fails
    if the count rises above the recorded baseline, so the boundary cannot erode.
    """
    proc = _run([sys.executable, "scripts/check_llm_boundary.py", "--count"])
    try:
        count = int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Result("llm-boundary", FAIL,
                      f"could not parse count: {proc.stdout!r} {proc.stderr[:300]}")
    detail = "" if count <= baseline else "run scripts/check_llm_boundary.py to list them"
    return Result("llm-boundary", PASS if count <= baseline else FAIL,
                  detail, count, baseline)


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
        Gate("llm-boundary", "codegen emitters make no direct LLM calls (deterministic boundary)",
             "ratchet", lambda: gate_llm_boundary(baseline.get("llm_boundary", 0)),
             remediation="move the LLM call out of the emitter; the LLM may only propose "
                         "schema-validated genome edits, never emit artifacts "
                         "(03_integration.md §2). Or append 'llm-boundary-ok: <reason>'",
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
        Gate("breadcrumb-coverage", "every routed page with a header carries a breadcrumb", "zero",
             gate_breadcrumb_coverage,
             remediation="add breadcrumb=[('Home','/'), (<title>, none)] to page_shell "
                         "(or breadcrumbs=[{'label':'Home','href':'/'}, {'label': <title>}] "
                         "for page_header); partials are exempt; else mark 'breadcrumb-ok:'",
             tags=["static", "ui"]),
        Gate("stale-models", "no retired LLM model id (404s in prod) in shipped code", "zero",
             gate_stale_models,
             remediation="use a current id from DEFAULT_MODELS (model_defaults.py); "
                         "if the line legitimately documents a retirement, append 'stale-model-ok'",
             tags=["static"]),
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
             remediation="add a test that loads the route, or remove it from the sidebar",
             tags=[]),
    ]


DEFAULT_BASELINE = {
    "undefined_names": 296,
    "redefinitions": 73,
    "lint_core": 4482,
    "design_tokens": 1255,
    "design_tokens_extended": 4552,
    "air_gap": 78,
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

    if args.gate:
        wanted = set(args.gate)
        unknown = wanted - {g.name for g in gates}
        if unknown:
            parser.error(f"unknown gate(s): {', '.join(sorted(unknown))}")
        gates = [g for g in gates if g.name in wanted]
    if args.tag:
        gates = [g for g in gates if set(args.tag) & set(g.tags)]

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
            result = Result(gate.name, FAIL, "timed out")
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
                        "fail": len(failed), "skip": len(skipped)},
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

    print(f"\n{len(results) - len(failed) - len(skipped)} passed, {len(failed)} failed, {len(skipped)} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
