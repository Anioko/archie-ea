# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Archie is an AGPL-3.0 enterprise architecture platform (TOGAF 9.2 / ArchiMate 3.2): application
portfolio, capability/value-stream modelling, an AI-assisted solution-design journey, and an
Architecture Review Board (ARB) governance workflow. Flask + Jinja2 + PostgreSQL, server-rendered,
with Tailwind/shadcn tokens and Alpine.js on the front end.

**Read `DESIGN.md` before editing any template, CSS, or front-end JS file.** It is the authoritative
UI contract (color tokens, base templates, component macros, Alpine rules) and is not repeated here.

## Done means deployed — standing instruction from the owner (14 Aug 2026)

The owner is non-technical and has delegated technical judgement entirely. **A wave of work is
not complete until it is verified green AND running in production** — merge, push, deploy, and
confirm the live site serves, in the same session. Do not end a session by offering deployment
as a menu option or asking "shall I deploy?"; that is the failure mode this rule exists to stop
(one-strike rule, per the owner). The only legitimate reasons to stop short: verification is
red, or the next action is destructive/irreversible (`recreate-db --force`, data deletion,
history rewrites) — those still require explicit approval. Everything else: execute end-to-end.

## Verification — run this before claiming anything works

```bash
python scripts/verify.py          # every gate that can run here
python scripts/verify.py --json   # machine-readable
python scripts/verify.py --gate boot-health     # one gate
python scripts/verify.py --tag static           # fast static gates only (~5s)
```

This is the executable form of `app/templates/macros/ZERO_TOLERANCE_PROTOCOL.md`.
**Do not report work as complete without a green run**, and do not treat a `SKIP` as a
pass — a skipped gate is printed in the summary precisely so it cannot be mistaken for
one. CI runs with `--require-db`, so gates needing PostgreSQL fail there rather than
skipping.

Several gates are **ratchets**: they compare a measurement against
`verification_baseline.json` and fail when it gets worse, so the gate is "no worse",
not "clean". Only two carry real debt now — **88** raw-Tailwind-colour uses
(`design_tokens`) and **98** raw-SQL statements on tenant tables with no org predicate
(`raw_sql_tenancy`). `undefined_names`, `redefinitions`, `lint_core` and `air_gap` are
all at **0**: treat those four as must-be-clean gates that happen to be implemented as
ratchets. Lowering a baseline is routine — `python scripts/verify.py --update-baseline`
after a cleanup. Raising one is a regression that must be justified in review.

**Read the numbers from `verification_baseline.json`, not from here.** This file is
prose and drifts; the JSON is what the gate enforces. Note also that `design_tokens`
counts only the families in `BANNED_FAMILIES` (`scripts/check_design_tokens.py`) —
`gray/grey/slate/zinc/neutral/stone/blue/red`. Removing an `emerald`, `purple`,
`orange` or `cyan` class is right per DESIGN.md but moves this number by zero, and a
line carrying a `token-migration-ok` marker is already excluded from the count.

All 19 gates, in registry order (`scripts/verify.py`, `build_gates`):

| Gate | Catches | Kind |
|---|---|---|
| `compile` | syntax errors (bytecode-compiles every module) | must pass |
| `undefined-exports` | `__all__` naming a missing symbol | must be 0 |
| `undefined-names` | runtime `NameError` (ruff F821) | ratchet @ 0 |
| `redefinitions` | shadowed definitions (ruff F811) | ratchet @ 0 |
| `lint-core` | correctness lint (ruff `F,E4,E7,E9`) | ratchet @ 0 |
| `design-tokens` | raw Tailwind colours (DESIGN.md rule) | ratchet @ 88 |
| `air-gap` | a UI asset loaded from a public CDN | ratchet @ 0 |
| `raw-sql-tenancy` | raw SQL on a tenant table with no `organization_id` predicate | ratchet @ 98 |
| `template-syntax` | a Jinja template that does not parse (500s every page using it) | must be 0 |
| `template-references` | an `include`/`extends` target that does not exist (TemplateNotFound at render) | must be 0 |
| `fabricated-data` | invented data reaching the UI (see below) | must be 0 |
| `deployed-deps` | installed packages below the pinned floors | must be 0 |
| `css-build` | committed `tailwind-output.css` stale vs a rebuild | must pass (needs Tailwind CLI) |
| `sri` | `integrity=` hash not matching the file it guards | must be 0 |
| `vendor-integrity` | a vendored asset not matching `VENDOR_MANIFEST.txt` | must pass |
| `dependency-cves` | known CVEs in shipped dependencies (`pip-audit`) | must be 0 |
| `boot-health` | unregistered blueprints; unresolved `url_for` | must pass |
| `schema-drift` | ORM/database column drift | must pass (needs DB) |
| `tests` | behavioural regression | must pass (needs DB) |

Per-line escape hatches, each of which makes the exception reviewable rather than
silent: `fabricated-ok: <reason>`, `air-gap-ok`, `tenancy-ok: <reason>`.

`pre-commit install` gives the same feedback at commit time on changed files only.
Rationale for the whole design — and why compiler/type-checker enforcement was
rejected — is in [ADR 0001](docs/adr/0001-verification-strategy.md). The air-gap,
CSP, telemetry and CVE posture is [ADR 0005](docs/adr/0005-enterprise-network-readiness.md);
the GPL-in-the-dependency-tree question is [ADR 0006](docs/adr/0006-dependency-licensing.md).

### CI enforces more than `verify.py` can

`.github/workflows/ci.yml` adds five gates with no local `verify.py` equivalent — do
not assume a green local run means a green CI run:

| CI job | Enforces |
|---|---|
| `secret-scan` | gitleaks over **full history** (so a bad commit is expensive to undo — stage files individually) |
| `security-sast` | bandit, ratcheted via `scripts/ci/bandit_gate.py` against `.bandit-baseline.json` |
| `smoke` | Playwright browser journeys, one per archetype (`tests/smoke/`), a WCAG 2.1 AA axe-core audit ratcheted against `tests/smoke/a11y_baseline.json`, and an authorisation matrix |
| `dependency-audit` | `pip-audit` ratcheted against `scripts/ci/dependency_baseline.json` |
| `db-gates` | also emits a CycloneDX SBOM from the *installed* environment |

Line coverage is measured and printed by the `tests` job but **deliberately not
gated** — it can regress silently, so do not read a green CI as coverage holding.

## Commands

```bash
# Setup (PostgreSQL required; `CREATE EXTENSION IF NOT EXISTS vector;` for AI/embedding features)
pip install -r requirements.txt
cp .env.example .env                          # SECRET_KEY, DATABASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD
flask --app manage init-db                    # create missing TABLES (create_all) — non-destructive
flask --app manage reconcile-schema           # add missing COLUMNS to existing tables — see Schema below
python create_admin.py

# Run
flask --app manage run                        # dev, :5000
python manage.py                              # dev, but kills any process already on :5000 first
gunicorn -c gunicorn.conf.py "manage:app"     # production
docker compose up                             # app + Postgres + Redis; boots init-db → reconcile-schema → gunicorn

# Tests — pytest reads TEST_DATABASE_URL (NOT DATABASE_URL); PostgreSQL is enforced, SQLite raises
export TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/archie_test
pytest -q                                     # what CI runs (with --maxfail=20)
pytest tests/test_business_case.py            # single file
pytest tests/test_business_case.py::test_name # single test
pytest -m journey                             # by marker — see pytest.ini for the full marker list
ruff check .                                  # advisory, non-blocking in CI

# CLI (dozens of commands; `flask --app manage --help` to list)
flask --app manage reconcile-schema --dry-run # report column drift without applying
flask --app manage bridge-motivation          # promote journey Solution* motivation → enterprise layer
flask --app manage data-profile --table application_components --fields lifecycle_status
flask --app manage db-query "SELECT ..."      # read-only SQL
flask --app manage seed-capabilities --dry-run
flask --app manage acm stats
```

`flask --app manage recreate-db` is destructive and requires `--force`. Don't run it without explicit
human approval — `init-db` + `reconcile-schema` covers every non-destructive case.

## Schema management — read this before touching a model

There are **three** overlapping mechanisms, and Alembic is *not* the source of truth:

1. **`create_all()`** via `flask init-db` — creates missing tables only. It **cannot** add a column to
   a table that already exists.
2. **`flask reconcile-schema`** (`app/commands/reconcile_schema.py`) — the actual answer to drift.
   Diffs every mapped model against the live table and emits `ALTER TABLE ... ADD COLUMN IF NOT
   EXISTS`. ADD-only, all nullable, never drops or retypes; idempotent. Runs on container boot.
3. **`migrations/`** — Flask-Migrate/Alembic exists with 130+ revisions and multiple merge heads, but
   deploys do **not** run `flask db upgrade`. Treat it as historical.

Consequence: **adding a non-nullable column, or one with a backfill requirement, will break existing
databases** — `reconcile-schema` only adds nullable columns. New columns should be nullable (or carry
a server default) and be tolerated by code when NULL. See
`docs/known-issues/schema-drift-on-existing-databases.md` for the full failure mode: one missing
column raises `UndefinedColumn`, which aborts the transaction and cascades into
`InFailedSqlTransaction` for every later query, 500-ing the whole page.

`manage.py init_db` also contains a long tail of hand-written idempotent `ALTER TABLE` statements for
pre-Alembic columns. **Do not add to it** — it is legacy.

The agreed target state (Alembic baseline + `db upgrade` on deploy, `reconcile-schema`
demoted to a drift detector) and the maintenance-window migration plan are in
[ADR 0002](docs/adr/0002-schema-management.md). The detector half is already wired as
the `schema-drift` gate.

## Architecture

**App factory** — `app/__init__.py` is a slim orchestrator; each step delegates to
`app/_bootstrap/*.py` (`extensions`, `security`, `routes`, `context_processors`, `assets`, `services`,
`blueprints`, `swagger`, `cli`). **Order matters** — extensions and tenant middleware must be
installed before blueprints. Add new wiring to the relevant `_bootstrap` module, not to
`create_app()`.

**Blueprints register non-fatally.** `init_blueprints` logs and continues on import failure rather
than raising, so a broken module degrades one feature instead of the whole app. The cost: any
`url_for()` to such an endpoint can `BuildError` and 500 *every* page that renders the sidebar.
Guard cross-module links:

```jinja
{% if 'value_stream.index' in flask.current_app.view_functions %}
<a href="{{ url_for('value_stream.index') }}">…</a>
{% endif %}
```

`_validate_critical_endpoints()` warns at boot when a core endpoint is missing; add to
`REQUIRED_ENDPOINTS` when a template starts depending on a new one.

**Multi-tenancy is implicit and enforced by ORM events**, not by query code
(`app/middleware/tenant_isolation.py`, `tenant_context.py`). Models inheriting `TenantMixin` get a
`WHERE organization_id = g.current_org_id` filter injected via `do_orm_execute`, and
`organization_id` auto-set on flush. So:
- Don't hand-write `organization_id` filters on `TenantMixin` models — you'll double-filter.
- Anything running outside a request context (CLI, scheduler, tests) has no `g.current_org_id` and is
  therefore **unfiltered**. Scope explicitly in those paths.
- A new tenant-scoped model needs `TenantMixin` — omitting it silently leaks rows across orgs.
- **Bulk `UPDATE`/`DELETE` ARE tenant-filtered as of ADR-0003's closure** —
  `do_orm_execute` now applies `with_loader_criteria` to ORM-enabled UPDATE and
  DELETE, not just SELECT, so `Model.query.filter(...).update()/.delete()` inside a
  request carries the tenant predicate mechanically. The two strict xfails that
  encoded this gap in `tests/test_tenant_isolation.py` are now plain passing tests.
  Still put `organization_id` in bulk-write predicates as defence-in-depth: raw-SQL
  writes and anything outside a request context remain unfiltered.
  `Query.get()` / `Session.get()` are scoped **only on an identity-map miss** —
  correcting an earlier "is scoped (verified)" note here, which was measured with a
  cold session and so only ever tested the miss. On a hit they return the cached
  object without emitting SQL, so `do_orm_execute` never runs and no tenant filter
  is applied. Demonstrated: load a row as org A, switch `g.current_org_id` to org B
  in the same session, and `.get()` hands back org A's row; `expunge_all()` first and
  it is correctly blocked.
  Per-request code is unaffected — one request is one tenant and one session. The
  exposure is anything that **loops over tenants inside a single session**: CLI
  commands, the scheduler, importers, and tests. Call `db.session.remove()` (or
  `expunge_all()`) between tenants there, and put `organization_id` in the predicate
  rather than trusting `.get()`.
  The same caching bit flask_login: its `g._login_user` survives when a context is
  reused, which made four cross-org tests exercise the wrong user and report a leak
  that does not exist — see the note in `tests/test_ba_tenant_and_authz.py::_login`.
  [ADR 0003](docs/adr/0003-tenant-isolation-gaps.md);
  invariants pinned in `tests/test_tenant_isolation.py`.

**Two parallel code layouts** — both live; `app/modules/` is canonical for new work:
- `app/<domain>/` — older flat blueprints. 10 domains are legacy-only, including
  `api/` (28 files), `application_mgmt/` (31), `main/` (25), `routes/` (18).
- `app/modules/<domain>/` — self-contained (`routes/`, `services/`, `models/`, a
  `register(app)` entrypoint). 19 domains live only here.
- **7 domains exist in both** — `account`, `admin`, `ai_chat`, `auth`, `dashboard`,
  `integrations`, `monitoring` — selected at boot by the `USE_*_GUARDRAILS` flags,
  which `blueprints.py` now defaults **on** (with them off, a fresh clone fell back to
  legacy and ~66 template `url_for()` calls raised `BuildError`). Don't flip them off
  casually. Retiring these duplicates is the migration's next step — see
  [ADR 0004](docs/adr/0004-module-layout-consolidation.md).

`app/models/` (~200 modules) and `app/services/` (~340 modules) are shared by both. Several tables are
mapped by two model classes via `extend_existing` — a known legacy hazard `init-db` works around by
de-duplicating same-named indexes before `create_all()`.

**Personas / access control** — `enterprise_role` on `User` drives sidebar sections and dashboard
cards (`app/utils/role_access.py`, `_bootstrap/context_processors.py`), and the AI assistant's
governed charters live in `app/modules/ai_chat/services/architect_persona_charters.py`
(`ARCHITECT_PERSONAS`). Adding a persona means touching all three plus `components/admin_sidebar.html`.

**ArchiMate is the backbone, not a view.** Every backend CREATE for a motivation entity (Driver,
Goal, Constraint, Requirement, Risk, Metric, Plateau, WorkPackage) must call
`_sync_archimate_element()` so a matching `ArchiMateElement` row exists. The domain→ArchiMate type
map is in `DESIGN.md`. A plain textarea is not an acceptable substitute — the field *is* the element.

## Conventions

- **SQLAlchemy 2.0:** raw strings in `db.session.execute("…")` raise. Always wrap: `db.text(...)`.
- **Impact scoring:** use `POST /api/v1/impact/analyze`; don't add parallel scoring logic. Responses
  may be wrapped by `success_response()` — unwrap with `json.data ?? json`.
- **No `console.log` in shipped templates/JS**, no stray `print()` in request handlers. User-facing
  notifications go through `Platform.toast`, never native `alert()`/`confirm()`.
- **Null display:** em dash (`—`), never `0` or blank. Currency via `window.currencyManager.format()`.
- **Never invent data.** Archie is a system of record: a screen that fabricates a plausible
  value when the real one is missing is worse than one showing nothing, because the user
  cannot tell the difference and acts on it. Concretely — no fake fallback in a `catch`
  (render the error), no literal metric passed to `render_template` that looks computed
  (pass `None`), no label describing a different field than the one plotted. A `0` that
  means "not computed" is indistinguishable from a measured zero; use `None` → `—`.
  Remember `fetch` does **not** reject on 404: `if (response.ok)` with no `else` silently
  leaves metrics at their `0` initialiser. Use `if (!response.ok) throw`.
  Enforced by the `fabricated-data` gate; escape hatch is `fabricated-ok: <reason>`.
- **Entity fields** for user / application / vendor / ArchiMate element must use a debounced
  live-search picker against the documented endpoint, not a free-text input (see `DESIGN.md`).
- **Staging:** `git add <file>` — never `git add -A`. Untracked scratch scripts are common at the repo
  root, and CI runs `gitleaks` over full history, so an accidental commit is expensive to undo.
- **Commit messages:** write multi-line messages with `git commit -F <file>`, or a heredoc
  (`git commit -F- <<'MSG' … MSG`). Do **not** use a PowerShell here-string (`@'…'@`): the Bash tool
  is Git Bash, which does not parse it, and the result is a commit whose *subject line is a bare
  `@`* with the real subject on line two. That has happened three times in this repo. Backticks in a
  `-m` message are worse — the shell runs them as command substitution and silently deletes the
  quoted term, leaving sentences with holes.
  Repairing a subject line needs `--amend`, which is unsafe in a shared worktree because it sweeps in
  whatever another agent has staged. `git commit-tree` + `git update-ref HEAD` rewrites the message
  while touching neither the index nor the working tree, and is the safe repair.
- New behaviour needs a test. There are **three** conftest files: `tests/conftest.py` (shared
  fixtures), `tests/smoke/conftest.py` (Playwright live-server harness) and
  `tests/journeys/conftest.py`.
  **Write new tests against the shared fixtures** in `tests/conftest.py` — `db_session` runs the
  test inside a transaction that is always rolled back, so it cannot leave residue in the shared,
  persistent test database even if it fails partway; `app` is session-scoped; `make_org` and
  `tenant_ctx` cover multi-tenant setup. Follow `tests/test_tenant_isolation.py`, currently the
  only adopter.
  Most older modules (including `tests/test_business_case.py`) still hand-roll a module-scoped
  `app` fixture and delete their own rows. pytest resolves the closest fixture so they keep
  working, but **do not copy that pattern** — it is flaky by construction, which is why the
  shared fixtures exist.

## `docs/known-issues/` is a decision record, not a backlog

A file here documents something that **cannot be fixed in code** — a product
decision about whether a feature is wanted, an external constraint, a schema
change that needs a maintenance window. If a defect can be fixed, fix it;
writing it down instead converts a bug into a bug *plus* a note, and the note
gets read by the next person as a decision someone made deliberately.

This is not hypothetical. Every one of these was documented and left, and every
one was a live defect the whole time:

- 73 catch blocks that told nobody, recorded as "the next slice"
- `conversation_threads` / `conversation_messages` have no model, so chat
  history is broken on every fresh install
- five blueprint name collisions, one of which makes `/admin/security`
  unreachable
- ~107 `fetch()` calls whose response is never checked

Each was fixed only when someone asked why the list still existed.

If you must record something unfixed, say what would fix it and why it is not
being done *now* — and prefer a gate that counts it (see `verify.py`) over prose
that does not. A ratchet keeps the number from growing while the work is
outstanding; a paragraph does not.

## Documentation accuracy

The repo is an extract of a larger private codebase, so some docs reference files that aren't here.
Trust in this order: **`DESIGN.md` → `README.md` / `CONTRIBUTING.md` → `docs/` → everything else.**

- **`QUICK_START.md`** — obsolete. Every file it points at (`DOMAIN.md`, `DATA_REALITY.md`,
  `docs/design_system/*.json`, `scripts/guardrails/*`) is absent, so the claim/release task workflow
  it describes cannot be run. `DESIGN.md`'s own "canonical source of truth" pointers to
  `pattern_registry.json` / `token_map.json` are dangling for the same reason — `DESIGN.md` itself is
  the source of truth, alongside `app/static/css/shadcn_tokens.css` and `tailwind.config.js`.
- **`ARCHITECT_QUICK_START.md`** — legacy internal doc. It describes `flask db upgrade`,
  `python manage.py recreate_db|setup_dev|runserver`, and port 5439; the current setup is
  `init-db` + `reconcile-schema` on 5432/whatever `DATABASE_URL` says. It also refers to
  `SECURITY_REMEDIATION.md` and `KNOWN_ISSUES.md`, which don't exist.
- **CSS is committed pre-built** (`app/static/css/tailwind-output.css`) so a fresh clone and
  `docker compose up` render without a Node toolchain — the Docker image is Python-only.
  `scripts/build_css.py` (restored; `package.json`'s `build:css*` scripts point at it) drives
  the **standalone Tailwind CLI**, which `.gitignore` expects at `scripts/bin/tailwindcss[.exe]`
  — download it from the Tailwind releases page (v3.x; the config is v3 format). **Editing
  template classes requires a rebuild**, or the new class won't exist at runtime;
  `python scripts/build_css.py --check` fails when the committed CSS is stale.
  The `npm run test:*` Playwright scripts still expect `tests/e2e/`, which is not in this repo.
