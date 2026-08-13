# Wave 4 — ARB / EA-Workflow Tenant Partitioning (phased migration)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

**Goal:** Partition the ARB and EA-workflow tables by organization so governance data stops being global across every tenant. Phased and reversible: add nullable org columns → backfill each row's org deterministically from its FK parent → only THEN enable TenantMixin filtering. Extend the tenant-isolation test suite and the tenant-scoping gate to cover these tables.

**Why phased:** enabling the tenant filter (TenantMixin) before the backfill runs would make every existing NULL-org row invisible to every org (`WHERE organization_id = :org` excludes NULL) — a governance-data outage. So Phase A (columns + backfill) and Phase B (filtering) are SEPARATE production deploys with the backfill run in between.

**Reversibility:** all new columns are nullable (reconcile-schema adds them on boot per CLAUDE.md); the backfill only sets NULL→derived-org (idempotent, recomputable); nothing is dropped or deleted. NO recreate-db, NO column drops, NO row deletes.

**Tech Stack:** Flask/SQLAlchemy 2.0, PostgreSQL, pytest. Migration via the repo's `reconcile-schema` (nullable ADD COLUMN on boot) + a backfill CLI command — NOT Alembic (deploys don't run `db upgrade`).

## Global Constraints

Same as Wave 3's (docs/superpowers/plans/2026-08-12-shell-wave-3.md Global Constraints — binding verbatim), plus:
- **New columns MUST be nullable** (`nullable=True`, FK to organizations.id). reconcile-schema only adds nullable columns; a NOT NULL / backfilled column breaks existing DBs. Code must tolerate NULL org on these rows until backfill completes.
- **Full `python scripts/verify.py --tag static` (22/22, 0 failed) before ANY deploy** — hard rule.
- The models needing org (all `db.Model`, no TenantMixin currently): ARB — `ARBReviewItem`, `ARBException`, `ARBWorkflowStage`, `ARBBoardMember`, `ARBReviewComment`, `ARBCapabilityImpact`, `ARBGovernanceStandard`, `ARBAuditLog`, `ARBDocument`; EA — `EAWorkflowDefinition`, `EAWorkflowInstance`, `EAWorkflowStepExecution`, `EAWorkflowSchedule`, `EAWorkflowNotification`. (`ArchitectureReviewBoard` and `SolutionWorkflow` are ALREADY TenantMixin — leave them.)
- Org-derivation FK paths (deterministic): `ARBReviewItem.submitter_id`→User.org (NOT NULL, always present); cross-check `arb_session_id`→ArchitectureReviewBoard.org and `solution_id`→Solution.org. `EAWorkflowInstance.started_by_id`→User.org, fallback `workflow_definition_id`→EAWorkflowDefinition.org. Child rows (comments/steps/executions) derive from their parent item/instance. Definitions derive from creator. Each model's backfill picks its own most-reliable FK — document per model.
- Tenancy tests use tenant_ctx + make_org from tests/conftest.py; follow tests/test_tenant_isolation.py.

---

## PHASE A — columns + backfill (deploy-safe, still-global until Phase B)

### Task 1: nullable organization_id columns on ARB + EA models

**Files:** `app/models/architecture_review_board.py`, `app/models/workflow_models.py`; test `tests/test_arb_ea_org_columns.py`
**Do NOT add TenantMixin yet** — only the column: `organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)` on each of the 14 listed models. Keep code tolerant of NULL (no query changes here).

- [ ] Step 1 Failing test — for each model class, assert it has an `organization_id` column that is nullable and FKs organizations.id (introspect `__table__.columns`).
- [ ] Step 2 Verify fail.
- [ ] Step 3 Add the columns (nullable, indexed, FK). Nothing else.
- [ ] Step 4 `pytest tests/test_arb_ea_org_columns.py -q`; `python scripts/verify.py --gate compile --gate schema-drift` (schema-drift may need the test DB — run reconcile-schema against TEST_DATABASE_URL first so the columns exist); `--tag static` 22/22.
- [ ] Step 5 Commit `feat(tenancy): nullable organization_id columns on ARB + EA models (phase A)`.

### Task 2: backfill CLI command + coverage verification

**Files:** `app/commands/backfill_arb_ea_tenancy.py` (or add to an existing commands module — grep how `reconcile-schema`/other CLI commands register in `manage.py`/`app/commands/`); register the command; test `tests/test_backfill_arb_ea_tenancy.py`

Command `flask --app manage backfill-arb-ea-tenancy`:
- For each of the 14 models, for rows where `organization_id IS NULL`, derive org from the model's FK path (per the Global Constraints list) and set it. Idempotent (skips already-set rows). Runs OUTSIDE request context (no g.current_org_id) so scope explicitly.
- `--dry-run`: report per-model {rows total, rows NULL, rows derivable, rows ORPHAN (no derivable org)}. Do NOT write.
- `--org-id N`: assign ORPHAN rows (no derivable FK org) to org N — for manual cleanup only; without it, orphans are left NULL and reported.
- Print a summary: total backfilled, total orphans remaining. Exit non-zero if orphans remain and no --org-id given (so a deploy runbook can gate on it).

- [ ] Step 1 Failing tests — seed two orgs; create ARBReviewItem (submitter in org A) + EAWorkflowInstance (started_by in org B) + a child comment/step, all with NULL org; run the backfill; assert each row's org == its derived org (A/B correctly). Add an orphan case (a row whose FKs resolve to no org) → asserted reported as orphan, left NULL without --org-id.
- [ ] Step 2 Verify fail.
- [ ] Step 3 Implement the command + registration.
- [ ] Step 4 Tests pass; `--tag static` 22/22.
- [ ] Step 5 Commit `feat(tenancy): backfill command derives ARB/EA org from FK parents (phase A)`.

---

## PHASE B — enable filtering (deploy ONLY after backfill verified in prod)

### Task 3: add TenantMixin + close raw queries the gate now flags

**Files:** the two model files (add `TenantMixin` to the 14 classes' bases); whatever request-path queries the tenant-scoping gate now flags (the models now HAVE an org column, so unscoped raw queries over them become gate findings — fix or hatch); `verification_baseline.json` if count moves; tests extend `tests/test_tenant_isolation.py` (or a new `tests/test_arb_ea_tenant_isolation.py`).

- [ ] Step 1 Add `TenantMixin` to the **11 PER-TENANT models only** (base list: `class ARBReviewItem(TenantMixin, db.Model, OptimisticLockMixin)`). This gives auto-filter + auto-set-org-on-flush.
  **PER-TENANT (add TenantMixin):** ARBReviewItem, ARBReviewComment, ARBCapabilityImpact, ARBBoardMember, ARBException, ARBDocument, ARBAuditLog (ARB); EAWorkflowInstance, EAWorkflowStepExecution, EAWorkflowSchedule, EAWorkflowNotification (EA).
  **GLOBAL REFERENCE — do NOT add TenantMixin (leave the nullable org column unused/NULL; they are shared catalogs — Task-2 review found globally-unique codes, DEFAULT_* seeding, never queried by org; TenantMixin would hide them from every org):** ARBGovernanceStandard, ARBWorkflowStage, EAWorkflowDefinition. Add a one-line class comment on each: `# Global reference data (shared across tenants) — intentionally NOT TenantMixin; org column unused. See wave-4 Task-2 review.`
  (EAWorkflowDefinition global is the one product-flagged call — the safe default that doesn't break shared system workflow templates; recorded for human sign-off, not a blocker.)
- [ ] Step 2 Run `python scripts/check_tenant_scoping.py --json` — the 14 models are no longer in "leaky" (they're TenantMixin now, auto-filtered), so bare `.query` on them is SAFE and should NOT be flagged. But any RAW SQL over their tables (raw_sql_tenancy gate) or ORM `.get()` in a loop-over-tenants context may need attention. Triage + fix/hatch each; keep tenant_scoping honest.
- [ ] Step 3 Tenancy isolation tests: seed org A + org B ARB/EA rows; assert an org-A request sees only org-A review items / workflow instances (the exact leak Wave 3 found). Assert bulk and `.get()` paths per the CLAUDE.md tenancy notes.
- [ ] Step 4 FULL local CI: `--tag static` 22/22; full non-smoke suite green (adding TenantMixin auto-filter changes query results — many ARB/EA tests may need a tenant_ctx wrapper; fix them to seed/query within an org, don't weaken).
- [ ] Step 5 Commit `feat(tenancy): TenantMixin on ARB + EA models — governance data is org-scoped (phase B)`.

### Task 4: final review inputs + deploy runbook

- [ ] Step 1 Write the phased deploy runbook to the report: (A) deploy Phase-A commit → reconcile-schema adds columns on boot → run `backfill-arb-ea-tenancy --dry-run` on prod, inspect coverage/orphans → run it for real → verify 0 NULL org on all 14 tables → (B) deploy Phase-B commit (filtering). Between A and B, data stays global-but-intact; after B, scoped.
- [ ] Step 2 Full local CI green (static, bandit, full non-smoke suite).
- [ ] Step 3 Hand to the final whole-branch review.

## The controller (not a subagent) owns the production sequence

Phase-A deploy → prod backfill dry-run → prod backfill real → verify 100% coverage (0 NULL) → Phase-B deploy. If the prod dry-run reports ORPHAN rows (no derivable org), STOP and surface to the human — assigning a governance record to the wrong tenant is a breach; orphans need a human decision, not a guess.
