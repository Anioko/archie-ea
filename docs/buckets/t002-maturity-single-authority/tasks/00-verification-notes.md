# T-002 — Tech-lead verification notes (citations re-checked against this worktree)

Branch: `feat/t002-maturity-single-authority`, branched from `origin/main` tip (`0ada3769`).
Checked 2026-09-18. **These line numbers, not the brief's, are the ones the task files below cite.**

## Citations that were CORRECT in the brief (no drift)

| Brief claim | Verified |
|---|---|
| `app/models/unified_capability.py:47` `HybridCapabilityTenantMixin` | correct (`class HybridCapabilityTenantMixin:` at `:47`) |
| `:106` mixin applied to `UnifiedCapability` | correct |
| `:151-158` provenance columns | correct (`source_table` 151, `source_id` 152, `source_org_id` 153-157, `source_checksum` 158) |
| `:159` `retired_into_id` | correct (declaration 159-163; relationship `foreign_keys=[retired_into_id]` at `:274`) |
| `:193-194` `current_maturity_level` / `target_maturity_level` | correct |
| `:307` composite maturity index | correct (`Index("idx_capability_maturity", ...)`) |
| `:502` `_protect_reference_capability_writes` | correct (`:502-517`) |
| `app/models/capabilities.py:118-119` `target_maturity` / `current_maturity` | correct, and the brief's disambiguation note holds — `app/api/v1/capabilities.py` and `app/compat/capabilities.py` carry neither |
| `app/models/capability_models.py:167` `maturity_level`, `:180` `target_maturity_level`, `calculate_maturity_gap` at `:231-235` | correct |
| `app/models/capability_gap_analysis.py:208` `current_maturity`, `:213` `required_maturity_level` | correct |
| `app/jobs/tenant_safe_job.py:199` `job_lock` | correct (`:198-251`; `@contextmanager` on 198, body to 251 — brief said 199-246) |
| `run_for_each_tenant` | correct in substance, now at `:285` |
| `app/_bootstrap/extensions.py:224` `init_scheduler`, `:226-227` `app.testing` early return | correct |
| `:398-405` interval-job pattern with `max_instances=1` | correct (the typed-ARB waiver expiry job) |
| `CapabilityMaturityAssessment` at `capability_models.py:138` | correct (`:138`, `__tablename__` 146, FK at `:152-153` — brief said 152-154) |

## Citations that DRIFTED (the brief's numbers are stale)

| Brief said | Actually now |
|---|---|
| `project_capabilities.py:521` `run_projection` | **`:562-657`** |
| `project_capabilities.py:607` `execute_projection_with_audit` | **`:660-689`** |
| `project_capabilities.py:639-654` CLI entry | **`:692-720`**; `init_app` registers at **`:752`** |
| `project_capabilities.py` is 697 lines | now **~755** lines |
| registered at `app/_bootstrap/cli.py:313` | **`app/_bootstrap/cli.py:320`** |
| `business_capabilities.py:66-67` maturity columns | **`:67-68`** (PR #23's "never invent data" comment block at `:61-66` pushed them down; both are now `nullable=True` with no default) |
| `maturity_routes.py:176-185` raw-SQL UPDATE | **`:177-199`** (statement built from `:177`, executed at `:199`) |
| `maturity_routes.py:268-273` | **`:269-273`** |
| `maturity_routes.py:311-315` | **`:313-318`** |

## PR #23's actual merged state (do not re-do)

Confirmed present in this worktree:
- `scripts/database/deploy-schema.sh:48-53` — one-shot `flask --app manage project-capabilities --apply --report /tmp/project-capabilities-report.json`, non-fatal on failure, report echoed.
- `app/models/business_capabilities.py:601-790` — write-time sync: `_provenance_index_available` (`:634`), `_project_capability_row` (`:652`), `_delete_projected_capability` (`:756`), and the three listeners `after_insert` (`:778`), `after_update` (`:783`), `after_delete` (`:788`). These skip silently when the provenance index is absent (`:672`, `:763`).
- `scripts/verify.py:567-597` `gate_store_agreement`, registered in `build_gates()` at `:1623-1632`, tags `["boot","db"]` (**not** `static`).
- `verification_baseline.json` → `"store_agreement": 1`.
- `app/commands/apply_unified_capability_provenance_migration.py` exists (applies the provenance index migration).

Confirmed **absent** — this is the open work:
- `app/jobs/` contains only `__init__.py` and `tenant_safe_job.py`. No projection job.
- `extensions.py:224-430` `init_scheduler` registers ea-workflows, data-maturity digest, and typed-ARB waiver expiry. **No capability-projection job.**
- No change in `app/models/capabilities.py`, `capability_models.py`, `capability_gap_analysis.py` — all three still hold their own maturity columns with live readers.

## Brief claims that are WRONG and must be corrected in execution

1. **"the `store-agreement` ratchet for capability maturity"** — there is no maturity concept in
   `scripts/check_store_agreement.py`'s `CONCEPTS` registry (`:129-161`). The registry holds exactly
   three concepts: `capabilities` (population counts across `BusinessCapability`, `UnifiedCapability`,
   `GET /dashboard/api/capabilities`, `GET /api/v1/capabilities/`), `applications`, and `gaps`.
   The baseline `1` is therefore a **capability-count** disagreement, not a maturity one. Acceptance
   criterion 10 as written ("the maturity ratchet reads 1 before and 0 after") **cannot be satisfied by
   the reader migration alone**. Task 05 closes this by registering a maturity concept in `CONCEPTS`
   and re-baselining honestly; do not claim AC-10 against the existing count-shaped 1.
2. **"eight route files read `unified_capabilities`"** (SR-4) — the real number is **18** route files
   (66 occurrences), enumerated in task 05. The "eight" is stale prose carried from `CLAUDE.md`.
3. **A fifth duplicate the brief does not name**: `app/models/capability_models.py:422-423`
   (`CapabilityRoadmapItem.current_maturity_level` / `.target_maturity_level`), plus
   `app/models/capabilities.py:243` (`maturity_level`) and `:487-490`
   (`process_/technology_/skills_/governance_maturity`). These are in scope for the grep assertion in
   AC-8 only insofar as they are **current-value reads**; roadmap *targets* and the four sub-dimension
   scores are not the authority's columns and are explicitly out of scope — say so in the build report
   rather than silently leaving them.

## Not verified by this tech-lead — builder must run and record

This invocation had **no shell**. The following brief-mandated measurements were NOT taken and are
assigned to the builder as the first act of task 01, recorded verbatim in the build report:
- `python scripts/verify.py --gate store-agreement` — the exact current count (baseline file says 1;
  the file is not the measurement).
- `flask --app manage project-capabilities --dry-run` — whether `uq_unified_capabilities_provenance`
  exists on *this* database and whether `CLASSIFIES_PROVENANCE_ONLY_TENANT` is satisfied. Both
  preconditions are still enforced in source (`run_projection` `:573-579` and `:620-627`), so neither
  can be assumed closed by PR #23.
