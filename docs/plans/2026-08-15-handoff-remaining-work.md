# Handoff: remaining Archie work (from the AI-enablement/governance session, 15 Aug 2026)

You are picking up a work queue from a closed session. Execute it with cheap subagents:
**haiku for mechanical single-file edits, sonnet for feature implementation AND for every
review, your own judgment for merges/deploys.** The non-negotiable that saved this project
three times in two days: **every implementer's diff gets an adversarial review by a separate
subagent before merge** — reviews caught a cross-tenant LLM data leak, a permanently-blank
dashboard (frontend reading keys the backend never returns), and an approval gate that
returned "pending approval" while queuing nothing. Never skip the review because a diff
"looks simple", and have reviewers cross-check every template/JS field against what the
backend actually returns.

## Ground rules (violating any of these has bitten this repo before)
- Read CLAUDE.md and DESIGN.md first. Baselines live in `verification_baseline.json`.
- **Shared checkout**: another session may edit the main working tree. ALL work happens in
  `git worktree add .worktrees/<name> -b <branch> <base>`. Stage files individually
  (`git add <file>`, never `-A`). Commit messages via `git commit -F-` heredoc.
- Tests: Postgres on **127.0.0.1:5439** (portable install, start via pg_ctl from Downloads
  if down), `TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5439/flask_test`.
  Run the unit suite (`pytest -q --maxfail=20 --ignore=tests/smoke`) and the smoke suite
  (`pytest tests/smoke -q`) **as separate runs** (together they exceed the 10-min command
  cap) and never two suites in parallel (they share the test DB and poison each other).
- Before every deploy: `python scripts/verify.py --tag static` must pass 23/23 (css-build
  skip is expected locally — but then verify no NEW Tailwind classes were introduced).
- **Deploy mechanics**: base all work on the droplet's CURRENT branch — check it first:
  `ssh root@134.122.105.56 "cd /root/archie-ea && git branch --show-current"`. A `prod`
  remote exists locally. Deploy = push a `deploy-YYYYMMDD-<name>` branch to `prod`, then on
  the droplet `git checkout <branch> && docker compose restart server` (`up -d` is a no-op).
  Boot takes up to ~10 min; poll `http://127.0.0.1:5000/account/login` for 200
  (**`/auth/login` 404s — do not poll it**). Public check: https://165-22-125-156.sslip.io
  (login 200, /health 200). After deploy, fast-forward `origin/main` to the deployed tip
  (`git push origin <branch>:main`) — main forked from prod once and it nearly caused a
  20-commit rollback. Prod host is 2 vCPU: never run parallel containers/suites against it.
- Prod has NO LLM keys (`[LLM CONFIG] No LLM providers enabled` in `docker logs
  archie-ea-server-1`). All AI features 503 honestly until the owner adds keys in
  Admin → API Settings. Do not fake this away; do not install any key yourself.
- "Done means deployed": a wave is complete only when verified green AND live on the
  public URL, same session. Never end by offering deployment as an option.

## TASK 0 — FIRST: confirm the union deploy is healthy
At handoff, `deploy-20260815-union` @ `c226b7c` was checked out on the droplet and booting.
It is the merge of BOTH sessions' waves: the solutions-qa2 wave (blueprint console errors to
zero, lifecycle suite, five orphaned JS files deleted) + the governance closing wave
(REQUIRE_AI_APPROVAL defaults on with the /ai-chat/data/* gate queuing REAL executable
approvals — 3 routes queue, 4 explicitly exempted with comments; `generate_blueprint_narrative`
un-broken via extracted `generate_section_narrative`; value-stream derivation partial-failure
honesty; slash-command exemption comments). Gates at handoff: static 23/23, targeted 75/75;
full unit suite was running. Confirm the public URL serves (login 200, /health 200) and that
`origin/main` is fast-forwarded to the deployed tip (`git push origin deploy-20260815-union:main`
if not). If boot never came up or the unit suite failed, diagnose before anything else.

**HARD-LEARNED RULE: re-check the droplet's branch IMMEDIATELY before every checkout** —
another session deploys to the same droplet, and a checkout on a stale assumption rolls
their work back (it happened between two checks ~1h apart on 15 Aug; the union merge above
is the repair). If the branch moved since your last look, fetch it and merge before deploying.
Note: the solutions-qa2 wave already deleted five orphaned solutions JS files — read commit
`64f1db6` before starting TASK 3; part of it may be done.

## TASK 1 — Platform.fetch ratchet (fe-qa backlog's biggest item)
~601 raw mutating `fetch()` sites ride a CSRF-injection safety net (`app/static/js/core/03-fetch.js`).
Add a verify.py ratchet gate (`raw_fetch_sites` or similar) counting raw fetch calls in
templates + static JS (exclude the safety net itself and Platform.fetch's implementation),
baseline at the current count in `verification_baseline.json`, wire into `build_gates` with
tags ["static","ui"], then burn down 2-3 worst modules with haiku subagents (mechanical:
replace `fetch(` with `Platform.fetch(` — read `Platform.fetch`'s contract first in
app/static/js; it adds error toasts + loading states). Lower the baseline after each burn.
Model the gate implementation on `gate_design_tokens_extended` in scripts/verify.py.

## TASK 2 — Contrast swaps (fe-qa P1)
~463 bare `text-destructive` small-text uses (3.76:1 on white) → `text-destructive-emphasis`
where the text is < 18.66px bold; same for bare `text-warning` and `text-success` on tints.
See docs/plans/fe-qa-wave5-findings.md. Mechanical per-file haiku work + one sonnet review
of the combined diff; the design-tokens gates must not regress. Beware: only swap TEXT
classes on light/tinted backgrounds — `text-destructive` on a solid dark fill is correct.

## TASK 3 — Wire-or-delete the orphaned solutions AI suggestions panel
`app/templates/solutions_strategic/partials/_ai_suggestions_panel.html` is included nowhere;
12 of 13 endpoints in `suggestion_api_routes.py` (`/api/solutions/...`) are unreachable
(only `/suggestions/costs` is called, from app/static/js/solutions/detail.js:1431).
Decide by reading both: if the panel fits solutions/detail.html's current layout, wire it in
behind the existing patterns (semantic tokens, x-cloak, if(!resp.ok) throw) and test the
endpoints it calls; if it duplicates what blueprint copilot insights already provide, DELETE
the template + dead endpoints (keeping /suggestions/costs) — a dead panel is debt either way.
Document the decision in the commit message.

## TASK 4 — Rerun the three fe-qa audits that never completed (docs/plans/fe-qa-wave5-findings.md)
(a) Forms audit: per-route server-side-validation pass over the 601 fetch sites' target
endpoints (scan_forms2.py + raw_fetch_results.json existed in a 13 Aug scratchpad — likely
gone; rewrite a scanner). (b) JS logic audit: races, double-submit, envelope bugs — fan out
read-only sonnet auditors per JS directory, verify findings adversarially, fix confirmed ones.
(c) Trigger-aware loading-state scan: find on-load fetches (DOMContentLoaded/init()/Alpine
init) with no loading affordance — only fix what the trigger-aware scan confirms; the naive
"375 missing" count was mostly false positives.

## TASK 5 — Low priority / needs product input (do last, or propose only)
- Composer palette-create orphans: creating an element via the palette writes the repository
  immediately; abandoning the diagram leaves orphans. Options: defer creation to save, or an
  unused-elements cleanup affordance. PROPOSE in a doc/commit message, don't unilaterally
  change creation semantics.
- Chat personas without charters (application_architect, integration_architect,
  systems_architect, business_analyst, product_analyst, capability_architect): extend
  `architect_persona_charters.py` following its existing pattern (see the five added in
  `947d619`) — worthwhile but not urgent.
- Dark mode is dormant by decision (fe-qa findings §"Product decision needed") — do NOT flip on.
- REMIND the owner: AI features stay 503 until LLM keys are set in Admin → API Settings.

## Rulings already made (don't re-litigate without cause)
- AI context must never egress cross-org data even where the in-app UI shows it (tenancy
  fixes fc88948, f416493); UnifiedCapability has NO org column — derive org scope from
  tenant-scoped mapping joins.
- User-typed slash commands are exempt from the LLM write-approval queue (deterministic,
  not LLM-initiated) — comments at the write sites in command_parser_service.py.
- The 4-tier risk RAG legend keeps its documented raw amber/yellow/green hues
  (`design-tokens-ok` markers) — do not "fix" them to semantic tokens.
- Value-stream Apply's 3/50/medium defaults are the platform-wide server defaults (comment
  in grid.js) — a product question, not a bug.
