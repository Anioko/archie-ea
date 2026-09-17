# Implementation Plan — Give `unified_capabilities` a Producer (ADR 0008)

Bucket: `unified-capabilities-producer`
Branch: `fix/unified-capabilities-producer` (worktree `../archie-oss-unified-caps`)
Author: tech-lead, 17 Sep 2026
Input: `docs/buckets/unified-capabilities-producer/brief.md`,
`docs/adr/0008-one-system-of-record.md`

---

## 1. Re-verification of ADR 0008's claims (done before planning, per the brief)

ADR 0008 is dated 31 Aug 2026 and the brief instructed me not to trust it. I read
the current code. **Three of its load-bearing claims are now false, and the
change is large enough to re-scope the bucket.**

### 1.1 "`unified_capabilities` has no producer" — FALSE, and comprehensively so

`app/commands/project_capabilities.py` (698 lines) already implements exactly the
projection ADR 0008 asks for, to a higher standard than the brief assumed:

- `INSERT ... ON CONFLICT (source_table, source_id) DO UPDATE`, idempotent on
  provenance (ADR 0008 rule 1's "idempotent on `(source_table, source_id)`",
  verbatim).
- Sets `source_table='business_capability'`, `source_id`, `source_org_id`, and an
  md5 `source_checksum` over sixteen source columns, so a re-run writes zero rows
  unless the source actually changed (`_CHECKSUM_SQL`, `_PROJECT_SQL`).
- Sets `scope='tenant'` and carries `organization_id` from each source row, so
  the `HybridCapabilityTenantMixin` shared (`organization_id IS NULL`) vs
  tenant-owned distinction is preserved — projected rows are never shared
  reference rows.
- Runs as raw SQL outside a request context on purpose, because
  `_protect_reference_capability_writes`
  (`app/models/unified_capability.py:501`) raises `PermissionError` for any new
  `UnifiedCapability` whose `organization_id != g.current_org_id`, and a
  projection writes for every tenant.
- Five pre-flight blockers (ownerless rows, owner/code drift, tenant code
  collision, archimate_id collision, source hierarchy cycle), three post-write
  verifications, an advisory lock shared with the tenancy cutover, dry-run/apply
  separation, and a JSON audit report.
- Registered: `app/_bootstrap/cli.py:313` imports its `init_app`, so
  `flask --app manage project-capabilities` exists.
- Tested: `tests/test_capability_projection.py`.
- Its documented pre-cutover blocker is cleared —
  `cutover_capability_tenancy.py:31` now sets
  `CLASSIFIES_PROVENANCE_ONLY_TENANT = True`, which is exactly what
  `_classifier_accepts_projection()` probes for.

**The defect is therefore not "the projection was never written". It is "the
projection is never run."** Nothing invokes it. The production boot chain is
`scripts/database/deploy-schema.sh` — `init-db`, `reconcile-schema`, then nine
named backfills — and `project-capabilities` is not among them. Neither is
`scripts/migrate_unified_capability_provenance.sql`, the standalone migration
that creates `uq_unified_capabilities_provenance`, *without which the command
refuses to run at all* (`run_projection` raises `ProjectionBlocked` when
`_has_provenance_index` is false, and `reconcile-schema` is ADD-COLUMN-only so it
can never create that index). A correct producer that no deploy executes is
observationally identical to no producer — which is why the ADR's measurement
still reproduces.

There is also **no ongoing sync**: the only event listener on `BusinessCapability`
is `create_capability_archimate_element`
(`app/models/business_capabilities.py:572`, a `before_insert` that mirrors the row
into `archimate_elements`). Nothing mirrors it into `unified_capabilities`. So
even a one-time backfill decays from the next UI-created capability onward.

### 1.2 "eight `/api/v1/*` route files read it" — overstated

`UnifiedCapability` is referenced in **three** files under `app/api/`:
`app/api/v1/capabilities.py` (the canonical list/detail/domains/levels accessor —
read-only, no POST), `app/api/v1/mappings.py`, and
`app/api/architecture_analytics.py`. It is referenced across ~60 files in `app/`
overall, but that is services and modules, not eight API route files. Scope the
demonstration to `/api/v1/capabilities/`, which is what the `store-agreement`
probe and the owner's original finding both name.

### 1.3 "`store-agreement` is a registered gate ratcheted at 1" — FALSE

This is the most important finding and it invalidates the brief's stated
acceptance criterion.

- `scripts/check_store_agreement.py` exists and is good (boots the app, picks the
  richest tenant, compares ANSWERS across ORM and HTTP surfaces, scope groups,
  no-evidence reporting).
- `grep 'Gate("' scripts/verify.py` returns **56 gate names and
  `store-agreement` is not one of them.** Nor is `canonical-store`
  (`scripts/check_canonical_store.py` also exists, also unregistered).
- `verification_baseline.json` contains **no `store-agreement` key** — case
  insensitive search for `store` and `capabilit` returns nothing. There is no
  ratchet of 1. There is no ratchet at all.

CLAUDE.md's "Registered 31 Aug 2026 and ratcheted at **1**" is prose that drifted
from the registry, in precisely the manner that file warns about. This is the
second instance found this session of a checker existing, being described as
enforcing, and not being registered — both are counted only by the
`unregistered-checks` ratchet (@41), which is a count, not an enforcement.

Consequence for this bucket: **"the ratchet drops from 1 to 0" cannot be
demonstrated, because there is nothing to drop.** Registering the gate is
therefore in scope here rather than being assumed done — closing the defect
without registering it would leave the estate exactly as unable to detect a
recurrence as it is today.

### 1.4 The six capability stores, re-measured

| Store | Status now | Action here |
|---|---|---|
| `business_capability` | **Live, the input source of truth.** `TenantMixin`, `organization_id` NOT NULL, ~461 prod rows, written by UI routes, `seed_capabilities.py:2036`, `vendor_capability_linker.py:256`, `vendor_analysis_routes.py:805`. `before_insert` mirrors into `archimate_elements`. | Source of the projection. Unchanged. |
| `unified_capabilities` | **Live, canonical, empty in production.** Model + hybrid scoping + four partial unique indexes + provenance columns all present. Twelve `UnifiedCapability(...)` construction sites exist (seeders, importers, per-row UI creates) — so it is not literally write-free, but none of them is a projection of the 461 rows. | Projection target. Populate it. |
| `capabilities` (`Capability`) | **Live model, 0 rows.** Already carries `source_type` (default `'business_capability'`) / `source_id` and a `canonical_capability_id` back-reference from `BusinessCapability` — i.e. a *second* half-built projection target. No producer either. | **Out of scope, explicitly.** Do not build a second projection. Note it; retiring it is its own bucket. |
| `enterprise_capabilities` | **No mapped model** — no `__tablename__` match in `app/models/`. Already dead. | Nothing to do. |
| `archimate_capabilities` | **No mapped model.** Already dead. | Nothing to do. |
| `technical_capabilities` | **Live** (`app/models/technical_capability.py:210`) but answers a *different* question — technology-layer capability, mapped to business capabilities via `unified_capability_technology_mapping`. Not a rival answer to "what business capabilities exist". | Nothing to do. Do not add it to the `store-agreement` registry. |

Net: the "six stores" is now effectively **three** relevant ones, two of which
answer the same question. That is a smaller problem than the ADR describes, and
the bucket should not manufacture work to match the older number.

---

## 2. The design decision (made here, not deferred to builder)

**Decision: both — a run-on-deploy backfill AND a write-time sync listener. Not
a scheduled job.**

Justification:

1. **Backfill alone is insufficient.** `business_capability` is written by live UI
   routes. A capability created after the backfill would be invisible to
   `/api/v1/capabilities/` until someone re-ran a CLI command, which is the same
   failure mode in slower motion, and the `store-agreement` gate would go red on
   the first create.
2. **A write-time listener alone is insufficient.** It cannot see the 461 rows
   that already exist, and it cannot recover a database where the listener was
   skipped (see 4 below).
3. **A scheduled job is rejected.** This repo has no reliable scheduler in the
   deployed topology (the boot chain is a shell script; `production-watch.yml` is
   GitHub Actions and the owner's account has Actions blocked), and a periodic
   sync introduces a staleness window that the `store-agreement` gate — which
   compares answers *now* — would report as a flapping disagreement. A gate that
   flaps gets waived. Reject.
4. **The listener extends an existing component, per ADR 0008 and CLAUDE.md's
   architect question.** `app/models/business_capabilities.py` already carries a
   `before_insert` listener (`create_capability_archimate_element`) that mirrors a
   `BusinessCapability` into a second store using a connection-level `insert()`
   during flush. The projection listener is the *same pattern in the same file*,
   not a new mechanism and not a new module.
5. **One SQL definition, not two.** The listener must execute the *same*
   `_PROJECT_SQL` from `app/commands/project_capabilities.py`, parameterised to a
   single source id — not a hand-written Python mapping of the same columns. Two
   independent column mappings would compute two different `source_checksum`
   values and every CLI re-run would report phantom drift. This is the
   "one way to do this thing" test, and it is the single most important
   constraint on Task 02.

Failure policy for the listener, decided:

- If the provenance unique index is absent (an un-migrated database), the
  listener **logs an error and skips**. It must not 500 a capability create on a
  database that has not had the migration applied; the CLI remains the recovery
  path. Checked once per process and cached.
- If the index is present and the projection write fails, the listener **raises**
  — the capability create fails atomically. A silently half-projected store is
  the defect this bucket exists to close; swallowing the error recreates it.
  (CLAUDE.md: a server failure returned to the caller as data is a defect;
  `silent-data` and `error-signalling` are must-be-0 gates.)
- Deletes: an `after_delete` listener removes the projected row matching
  `(source_table='business_capability', source_id=<id>)` and nothing else. An
  orphaned projection is a row claiming provenance to a source that no longer
  exists, which is worse than a missing row because it is undetectably stale.

---

## 3. Tasks

Ordered; each is a separate `builder` → `refuter` cycle. Briefs in
`docs/buckets/unified-capabilities-producer/tasks/`.

| # | Task | Handoff |
|---|---|---|
| 01 | Run the existing producer: provenance migration + `project-capabilities` in the deploy chain, with a measured backfill | builder → refuter |
| 02 | Write-time sync: extend the `BusinessCapability` listeners in `app/models/business_capabilities.py` to project on insert/update/delete, reusing `_PROJECT_SQL` | builder → refuter |
| 03 | Register `store-agreement` as a real gate with a baseline, and demonstrate `/api/v1/capabilities/` in a browser as a real persona | builder → refuter → qa-lead |

Task 03 depends on 01 and 02 both being merged — registering the gate before the
producer runs would land a red gate on main. Task 02 depends on 01 (it reuses
`_PROJECT_SQL` and requires the provenance index the migration creates).

## 4. Out of scope, recorded deliberately

- Retiring `capabilities` (`Capability`) into `unified_capabilities` via
  `retired_into_id`. It is a real second half-built projection target with a
  `canonical_capability_id` back-reference on `BusinessCapability`. Its own
  bucket.
- Making `unified_capabilities` user-writable, or repointing any screen off
  `business_capability`. `business_capability` stays the input; the 461-row
  screens must keep reading 461.
- `app/services/archimate_import_service.py`, `app/services/archimate_oef_service.py`
  and `app/modules/interface_register/` — concurrent work in other worktrees.
  **Do not touch.**
