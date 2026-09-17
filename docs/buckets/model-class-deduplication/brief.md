# Task Brief: Model Class Deduplication (Strategy Doc P2, Target-State Decision 1)

## Objective
Close the pattern that already caused a real, confirmed defect tonight:
model classes defined twice, where one copy has `TenantMixin` and the other
doesn't. Consolidate to one definition per concept, per ADR 0008.

## Context
The target-state strategy doc (`archiet-strategy/strategy/
20-TARGET-STATE-ARCHIE-2026-09-17.md`, commit `2ee66b8`) names "15 core
model classes defined twice" as a verified as-is defect and states decision
(1): "`archimate_core.py` is the only definition; the `models.py` twins go."

This was independently, exhaustively verified tonight (not assumed from the
doc) via a full grep of every class definition in `app/models/**/*.py`
(790 total definitions, including indented/conditional ones a naive
column-0-only grep misses — that blind spot is exactly what hid the first
confirmed instance below from an earlier quick check). **13 genuinely
duplicated class names found**, credible against the doc's "15" figure.

**A live instance of the highest-risk pattern already caused a real bug
tonight**, found by `refuter` reviewing unrelated dogfood-import work:
`ArchiMateRelationship` is defined in `app/models/models.py:468` (WITH
`TenantMixin`, the normal-runtime class, re-exported by
`archimate_core.py:22-24`) AND in `app/models/archimate_core.py:110`
(WITHOUT `TenantMixin`, only mapped when `APP_FAST_INIT=1`). Under
fast-init, relationships get written through the untenanted mapper,
producing `organization_id IS NULL` rows invisible to every normal-runtime
read — a real orphan/cross-org-visibility bug in the fast-init e2e path.

## Verified findings (from tonight's exhaustive audit — use these, don't re-derive)

**High risk — asymmetric TenantMixin, same bug pattern as the confirmed one:**
| Class | Tenanted copy | Untenanted copy |
|---|---|---|
| `ArchiMateRelationship` | `models.py:468` | `archimate_core.py:110` |
| `Principle` | `models.py:1633` | `motivation_extended.py:27` (same `__tablename__="principles"`) |
| `ApplicationComponent` | `application_portfolio.py:80` (+`OptimisticLockMixin`) | `application_component_fast.py:26` |

`ApplicationComponent` is one of the four examples the strategy doc names
by name — directly confirmed, not inferred.

**Medium risk — both TenantMixin, but load-order-dependent which definition
wins at `extend_existing` time (both carry a comment admitting this is
deliberate: "In fast-init/test contexts we may define a lightweight X"):**
| Class | Copy 1 | Copy 2 |
|---|---|---|
| `ArchiMateElement` | `archimate_core.py:53` | `models.py:253` |
| `ArchitectureModel` | `archimate_core.py:33` | `models.py:204` |

**Lower risk — duplicate, same table, neither TenantMixin (schema-mapping
ambiguity, not a tenant bug):**
- `TechnologyStack` — `models.py:1223` / `technology_stack.py:13`
- `Requirement` — `models.py:572` / `requirements.py:13`

**Naming collisions, likely NOT the same defect class — verify each
individually before treating as a duplicate-to-merge:**
- `Representation` (`archimate_business.py:382` vs `representation.py:30`)
  — may be two genuinely different concepts sharing a name, not one
  concept defined twice.
- `ApplicationCapabilityMapping` (`application_capability.py:26` vs
  `application_portfolio.py:655`)
- `ApprovalStatus`, `DuplicateType`, `CheckpointType`, `BatchJobStatus` —
  plain Python `Enum`s with genuinely DIFFERENT members reused across
  unrelated features. Not a tenant risk (enums aren't tenant-scoped) but a
  real "wrong import silently gets the wrong enum" risk. Do not merge
  these into one enum if their members genuinely differ per feature —
  rename to disambiguate instead; forcing a merge could be the actual
  regression here.

## Constraints
- Per ADR 0008 and the strategy doc's own decision: `archimate_core.py` is
  the intended canonical location for the ArchiMate-metamodel classes
  (`ArchiMateElement`, `ArchiMateRelationship`, `ArchitectureModel`). Verify
  this is still the right call given `models.py`'s copies may have more
  callers/history — check actual import counts before assuming
  `archimate_core.py` wins by default just because the doc says so.
- `Principle` and `ApplicationComponent`'s "twin" files
  (`motivation_extended.py`, `application_component_fast.py`) may exist
  for a real reason (fast test-init performance) — investigate WHY the
  fast-path duplicate exists before deleting it; if fast-init genuinely
  needs a lighter mapping, the fix may be "add TenantMixin to the fast
  copy," not "delete the fast copy and accept slower test init." Read
  git history/commit messages for these files if available.
- This is a large, high-blast-radius change (3,413 registered routes
  potentially touching these models per the strategy doc's own repo
  measurement). Per the strategy doc's own risk section: "Collapsing the
  15 twins breaks the 3,413-route surface → behind feature flags, with
  the route census as regression suite." Do NOT attempt a single big-bang
  merge across all 13 in one task. Sequence by the risk table above,
  highest-risk (asymmetric TenantMixin) first, one class-pair at a time,
  each independently verified before moving to the next.
- No non-nullable column changes without a migration plan (ADD-only
  reconcile-schema convention).
- Every consolidation must be demonstrated in a real browser per this
  repo's "Done means DEMONSTRATED" rule — not just a passing unit test —
  given the route-surface blast radius.

## Deliverable (Task 1 of what will likely be a multi-task bucket)
Start with the single highest-value, already-proven-dangerous pair:
**`ArchiMateRelationship`**. Investigate why the untenanted `archimate_core.py`
copy exists (APP_FAST_INIT — confirm the actual reason, likely test-boot
speed), decide the real fix (add TenantMixin to the fast-init copy so
both are safe, vs. genuinely deleting the fast copy and accepting the
init-time cost, vs. some third option — this is the task's own
engineering decision, backed by evidence of why fast-init exists at all),
fix it, and add a regression test proving relationships written under
`APP_FAST_INIT=1` are still tenant-visible under normal runtime.

Do not attempt `Principle` or `ApplicationComponent` in this same task —
scope Task 1 to `ArchiMateRelationship` alone, prove the pattern/process
works cleanly on the smallest of the three, then task 2/3 repeat it for
the other two asymmetric-TenantMixin pairs.

## Acceptance Criteria
- The `APP_FAST_INIT=1` path no longer produces relationship rows with
  `organization_id IS NULL` (or, if the resolution is "fast-init test mode
  isn't a real deploy topology, so document and ratchet-fence it instead
  of silently ignoring it" — that's an acceptable resolution IF explicitly
  justified, not silently left as-is).
- A test that writes a relationship under fast-init and confirms it's
  visible to a normal-runtime tenant-scoped read.
- `python scripts/verify.py --tag static` clean, no regression.
- Real browser check: create a relationship via any existing UI flow that
  exercises this code path, confirm it's visible correctly.

## Handoff Target
`tech-lead` first — investigate the APP_FAST_INIT rationale and produce a
scoped Task 1 brief (ArchiMateRelationship only) plus a rough outline for
Tasks 2+ (Principle, ApplicationComponent, then the medium-risk pair) —
then standard `builder` → `refuter` cycle. Work on branch
`fix/model-class-deduplication` (already created, isolated worktree at
`../archie-oss-model-dedup`) — do not touch files belonging to concurrent
work in `fix/archiet-dogfood-import` or `fix/unified-capabilities-producer`
worktrees (both actively in progress).
