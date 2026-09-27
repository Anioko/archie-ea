# Evidence-Gated ARB Submission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all solution ARB submissions tenant-safe, evidence-backed, atomic, idempotent, and consistent across chat, workbench, and HTTP entry points.

**Architecture:** A focused domain service owns evaluation and submission. An append-only evidence snapshot preserves the exact decision packet, while existing entry points become thin adapters.

**Tech Stack:** Flask, SQLAlchemy/PostgreSQL, Jinja/Alpine, pytest/Playwright.

**Spec:** `docs/superpowers/specs/2026-08-21-evidence-gated-arb-submission-design.md`

## Global Constraints

- Use `ARBReviewItem`, never the legacy `SolutionARBReview`, for new submissions.
- Derive organization, solution, actor, and workflow identity from persisted server state.
- Fail closed on missing evidence, exceptions, and ambiguous identity.
- New schema is additive and nullable-compatible with `reconcile-schema`.
- Every behavior follows red-green TDD and preserves the untracked `AGENTS.md`.

---

### Task 1: Canonical evaluation and evidence snapshot

**Files:**
- Create: `app/modules/solutions_strategic/v2/services/arb_submission_service.py`
- Create: `app/models/arb_submission_evidence.py`
- Modify: `app/models/__init__.py`
- Test: `tests/test_arb_submission_service.py`

**Interfaces:**
- Produces: `ARBSubmissionService.evaluate(solution_id, actor_id, workspace_id=None, assertions=None) -> ARBReadinessResult`
- Produces: `ARBSubmissionService.submit(solution_id, actor_id, workspace_id=None, assertions=None) -> ARBSubmissionResult`

- [ ] Write failing PostgreSQL tests for tenant/actor/workspace binding, persisted named artifacts, direct-route evidence, fail-closed evaluator exceptions, idempotency, rollback, and snapshot immutability.
- [ ] Run the focused tests and confirm each new behavior fails for the expected missing-service/model reason.
- [ ] Add the nullable-compatible append-only snapshot model and central evaluator.
- [ ] Add transactional submission with a locked solution, active-review idempotency, canonical review creation, solution mutation, snapshot, notification, and audit.
- [ ] Run focused tests, schema safety, tenant-scoping, and lint; commit only Task 1 files.

### Task 2: AI tool and workbench convergence

**Files:**
- Modify: `app/modules/ai_chat/tools/registry.py`
- Modify: `app/modules/ai_chat/tools/executor.py`
- Modify: `app/modules/ai_chat/services/agent_runner.py`
- Modify: `app/modules/ai_chat/services/workbench_kernel.py`
- Test: `tests/test_ai_arb_submission_convergence.py`

**Interfaces:**
- Consumes: `ARBSubmissionService.evaluate/submit`
- Produces: trusted `workspace_id` propagation and truthful result/error payloads.

- [ ] Write failing tests proving LLM arguments cannot select workspace/workflow, missing trusted workspace blocks workbench submission, and no path uses `test_client` or direct status mutation.
- [ ] Run tests and record the expected failures.
- [ ] Inject trusted workspace context into queued tool arguments and delegate executor/workbench operations to the central service.
- [ ] Persist `arb_submission` workbench artifact only after canonical success and include review/snapshot identifiers.
- [ ] Run focused tests and existing approval suites; commit only Task 2 files.

### Task 3: HTTP and legacy-chat convergence

**Files:**
- Modify: `app/modules/solutions_strategic/v2/routes/solution_design_routes.py`
- Modify: `app/modules/solutions_strategic/v2/routes/governance_api_routes.py`
- Modify: `app/modules/solutions_strategic/v2/routes/journey_v2_routes.py`
- Modify: `app/modules/ai_chat/services/multi_domain_chat_service.py`
- Modify: `app/modules/architecture/routes/arb_routes.py`
- Test: `tests/test_arb_submission_entrypoints.py`

**Interfaces:**
- Consumes: central submission service.
- Produces: consistent HTTP/chat success and stable fail-closed errors.

- [ ] Write failing contract tests for all five entry points, cross-tenant/unauthorized calls, duplicate retries, and absence of independent `ARBReviewItem` creation/status mutation.
- [ ] Run tests and confirm red for bypass behavior.
- [ ] Replace each implementation with a thin central-service adapter; derive actor from authentication and never accept `submitted_by_id` from JSON.
- [ ] Run route/chat tests, template syntax, and broken-surface gates; commit only Task 3 files.

### Task 4: Honest workflow UX and release evidence

**Files:**
- Modify: `app/templates/solutions/partials/_blueprint_governance.html`
- Modify: `app/templates/architecture_assistant/journey_v2_steps/_step6_review.html`
- Modify: `docs/plans/2026-08-21-best-in-class-tasklog.md`
- Test: `tests/smoke/test_arb_submission_journey.py`

**Interfaces:**
- Consumes: stable missing-evidence and success payloads.
- Produces: visible evidence checklist, retry state, and canonical review link.

- [ ] Read `DESIGN.md`, then write a failing browser journey for blocked evidence, actionable recovery, one successful retry, and no false success.
- [ ] Run it red and capture the user-visible blocker.
- [ ] Render the service readiness result with honest unavailable/loading/blocked/success states using existing platform components.
- [ ] Rebuild/check committed CSS, run focused browser and template gates, update the task log, and commit.

### Task 5: Independent review, full verification, and deployment

**Files:**
- Review all commits from the plan base through branch head.

**Interfaces:**
- Produces: reviewed, deployed release evidence.

- [ ] Generate per-task and final review packages; resolve every Critical/Important finding with scoped re-review.
- [ ] Run `python scripts/verify.py --json` with both database URLs on PostgreSQL port 5439 and require 0 failures/0 skips.
- [ ] Push `main`, deploy the exact SHA using `deploy/deploy.sh`, and retain backup/rollback evidence.
- [ ] Run `deploy/verify_production.py`, confirm exact production SHA and container health, and record results in the task log.
