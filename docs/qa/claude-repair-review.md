# Independent repair-batch review (Claude Code, 5 Sep 2026)

Scope: uncommitted diff on `codex/fortune500-readiness` plus the untracked tests named in
`git status`, excluding `architecture_crud_routes.py` and `tests/test_architecture_export_response.py`
(Codex-owned moving targets). Import/export service not reviewed (budget exhausted).
No tests were executed by this review; no source, test or ledger files were modified.
`AGENTS.md` does not exist in this worktree; `DESIGN.md` was used as the UI contract.

## Verdict

No hard blocker found by source review. Two items must be confirmed by a real browser/CI run
before closure (below). Deployment gates are stricter than before, not looser: the five
unknown error signals that triggered the production rollback would still roll back.

## Blocking until verified (cannot be settled from source)

1. **Dashboard smoke tab selector is unverified** — `tests/smoke/test_dashboard_pipeline_unknown.py:33,50`
   clicks `get_by_role("button", name="Overview", exact=True)`. A grep of `app/templates/dashboard/`
   and `app/modules/dashboard` for an `Overview` button label returned nothing, so the accessible
   name may live in a bundle or be rendered differently. Required: run this smoke test in CI; if it
   fails, confirm the tab's rendered role/name and keep the original intended outcome (pipeline card
   survives reload and navigation, not merely "Overview exists").
2. **Phase gate in the real page** — the partial is only included from
   `_blueprint_governance.html:1780` with `ignore missing`, and now calls `csrf_token()` and
   `url_for('solution_design.view_solution', …)` at render time. If either name is absent from
   that render context the include fails silently and the panel disappears rather than erroring.
   `tests/smoke/test_solution_blueprint_controls.py` now asserts the initial GET `/phase-gate`
   and rendered totals, which covers this — required: that smoke test green in CI on the seeded page.

## Reviewed and acceptable

- **Phase checklist explicit init** (`_phase_gate_checklist.html:137-146`): `init()` on
  `Alpine.data` runs before `x-init`, so `apiBase` is populated before `loadGate()`. The
  `data-api-base` value is the same `url_for` the old ancestor `apiBase` used
  (`detail.html:2178`), so the request URL is unchanged. Removing the recursive getters removes
  the stack-overflow hazard the deleted contract test guarded. Fallback to
  `window.__solutionApiBase` retained at lines 166/227. Cold-load test
  `tests/test_phase_gate_initial_load.py` proves the initial request fires once without a
  Refresh click, with and without a matching ancestor scope. Good.
- **Stacked header** (`page_shell.html`, `stack_actions=`): opt-in, default renders identically.
  `min-w-0 break-words` on the title column is the correct fix for a narrow column inside an
  xl viewport. Nonblocking: `tests/test_blueprint_header_responsive.py:36` registers the font
  route after the CSS tag is added; harmless but the fonts.ready wait may be a no-op.
- **ArchiMate picker limits**: `safe_int_arg('limit', 25, minimum=1, maximum=100)` replaces the
  bare `int()`. `get_elements_by_type` applies `limit` after the type/layer `filter_by`, so the
  tenant filter (ORM event) and type predicates are preserved; `limit=None` keeps other callers
  unchanged. Unit test drives the real route and service; hostile-URL test adds the negative and
  non-numeric cases against PostgreSQL. Good.
- **Deploy disk preflight** (`deploy.sh:49-70`): validates budget, root path and df output,
  fails closed, runs before pull and before the DB dump. Regex rejects leading zeros and empty
  string, matching README. Good.
- **Private candidate logs** (`deploy.sh:134-150`): single capture with `umask 077` + `chmod 600`,
  reused by both the error gate and rollback, so container recreation cannot erase evidence.
  Output prints the path only. The error gate still rolls back on any signal count > 0 and on a
  grep failure other than "no match"; nothing waives the five signals. Good.
- **Watchdog lock** (`archie-watchdog.sh:100-119`): script is `set -u` not `set -e`, so
  `flock -n 8; lock_status=$?` is safe. Lock held on fd 8 through forensics and restart, same
  path as `deploy.sh:28`. Missing release dir fails closed. Non-running container never started.
  Backup/crash-loop checks stay above the lock. Good. Nonblocking: the real-flock test is skipped
  on Windows; Linux CI must run `tests/test_watchdog_deployment_lock.py` for the TOCTOU case.
- **Health card selector** (`tests/smoke/test_dashboard_health_agreement.py:34-36`): now targets
  `a[href="/dashboard/health"] [data-slot="card-title"]`, which `metrics_card.html:61` renders.
  Equivalent intent to the removed regex, stricter element. Good.

## Nonblocking notes

- `docs/qa/fortune-500-findings.json` and the run report were not reviewed (ledger is Codex-owned).
- `tests/test_dashboard_health_agreement.py:47` launches Chromium inside the unit suite; it will
  fail rather than skip on a runner without browsers installed.

## Required CI/browser verification before closure

- Linux CI: `tests/smoke/test_solution_blueprint_controls.py`, `tests/smoke/test_dashboard_pipeline_unknown.py`,
  `tests/smoke/test_blueprint_header_responsive.py`, `tests/smoke/test_archimate_picker_limits.py`,
  `tests/test_watchdog_deployment_lock.py` (real flock), `tests/test_deploy_*.py`.
- A human or Playwright walk of the seeded solution page confirming the Phase Gate panel renders
  populated on first load and the More actions menu opens at 1100px.
- Passing local tests do not establish deployment or whole-product readiness.
