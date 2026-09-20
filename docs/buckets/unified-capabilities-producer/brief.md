# Task Brief: Give `unified_capabilities` a Producer (ADR 0008)

## Objective
Close the specific defect ADR 0008 names as the highest-cost example in this
codebase: `unified_capabilities` is the correctly-designed canonical store
for "what capabilities exist" (it alone can express provenance and the
shared-vs-tenant-owned distinction), it is wired into `/api/v1/capabilities`
and eight other route files, and **nothing writes to it**. Every one of
those endpoints answers empty against 461 real rows sitting in
`business_capability`.

## Context
Raised directly by the product owner tonight after being walked through
several other real, documented defects this session found evidence for
independently (schema management's three overlapping mechanisms, the two
parallel module layouts, a tenant-scoping gap on `.get()`, CSP blocking
inline handlers) — the pattern being that serious, previously-identified
architectural debt sits documented but unfixed. This bucket is the first
direct remediation of one of them, not another audit.

ADR 0008 (`docs/adr/0008-one-system-of-record.md`) is explicit about the
fix shape: **"If you find a store like this, write the projection; do
NOT repoint its readers at whatever table currently holds data."** That
would trade a correct architecture for a working screen and leave the
duplicate in place — do not do that.

The `store-agreement` verification gate exists specifically to catch this
class of defect (it boots the app and compares what different surfaces
answer for the same question, rather than reading source) and is
"ratcheted at 1" — that single known disagreement (`business_capability`
and `/dashboard/api/capabilities` both answering 12 while
`unified_capabilities` and `/api/v1/capabilities/` both answer 0) is
recorded as the live defect this bucket exists to close. Closing it means
that ratchet drops to 0, not that a `store-agreement-ok` exception is added.

## Constraints
- Do not repoint the eight existing `/api/v1/*` routes at
  `business_capability` — write the projection into `unified_capabilities`
  instead, per ADR 0008's explicit instruction.
- `business_capability` remains the input/source of truth for now (461 real
  rows); `unified_capabilities` becomes a correctly-provenanced derived
  store, not a second place users type directly into, unless the task
  investigation finds the intended design was always "write both" — verify
  this against `HybridCapabilityTenantMixin` and the model's own docstrings
  before assuming either direction.
- Every projected row must carry `source_table`/`source_id`/`source_checksum`
  (ADR 0008 rule 2 — "a copy declares itself") so the projection's
  provenance is queryable, not just visually correct.
- `organization_id IS NULL` on `unified_capabilities` rows means shared
  reference data (`HybridCapabilityTenantMixin`) — do not break this
  distinction when writing the projection; a tenant-owned capability and a
  shared reference capability are not interchangeable.
- No non-nullable columns added without a migration plan; this repo's
  `reconcile-schema` is ADD-COLUMN-only.
- This is real, tenant-visible data — any bulk write path needs the same
  tenant-scoping discipline as everything else in this codebase (no
  cross-org writes, `TenantMixin`/`HybridCapabilityTenantMixin` conventions
  respected).

## Deliverable
1. Investigate and confirm exactly what feeds `business_capability` today
   (which routes/services write to it) and exactly which of the "six
   capability stores" ADR 0008 names are actually still live vs. already
   dead, before writing anything — the ADR is over two weeks old at time of
   writing and the six-store count should be re-verified against current
   code, not assumed accurate.
2. A projection mechanism (a service function, an event listener on
   `business_capability` writes, or a backfill + ongoing sync — the task's
   own design decision, made and justified, not left open) that populates
   `unified_capabilities` from `business_capability`, correctly setting
   `source_table='business_capability'`, `source_id`, `source_checksum`,
   and the shared-vs-tenant `organization_id` distinction.
3. A one-time backfill for the current 461 rows.
4. Verification that the `store-agreement` gate's ratchet drops from 1 to 0
   — this is the actual acceptance criterion, not a unit test asserting the
   projection function was called.
5. Confirm the eight `/api/v1/*` route files ADR 0008 names now return real
   data, with a browser-demonstrated check (per this repo's "Done means
   DEMONSTRATED" standing rule) — not just an API curl.

## Acceptance Criteria
- `python scripts/verify.py --gate store-agreement` passes (ratchet drops
  to 0, or the gate's own baseline file is updated with
  `--update-baseline` ONLY if this task provides evidence the remaining
  disagreement, if any, is a different one than the one being closed here).
- A real browser check (Playwright) as a persona that uses capability data
  (solution_architect or enterprise_architect) shows a non-empty,
  non-fabricated capability list from a `/api/v1/capabilities`-backed
  screen, matching what `business_capability` shows elsewhere on the same
  page, for the same organization.
- No regression to `business_capability`-reading screens that currently
  work correctly (461-row screens must still show 461, not silently switch
  to a possibly-different projected count without explanation).

## Handoff Target
`tech-lead` first — this is defect remediation against an already-written
ADR with a stated fix shape, not new-feature discovery, so no
business-analyst pass is needed. Tech-lead should re-verify ADR 0008's
"six stores" claim against current code (some may already be retired),
produce task brief(s), then the standard `builder` → `refuter` cycle,
same rigor as tonight's other two buckets. Work on branch
`fix/unified-capabilities-producer` (already created, isolated worktree at
`../archie-oss-unified-caps`), separate from the in-flight
`fix/archiet-dogfood-import` branch — do not touch files in
`app/services/archimate_import_service.py`,
`app/services/archimate_oef_service.py`, or anything under
`app/modules/interface_register/`, all of which belong to concurrent work
in other worktrees.
