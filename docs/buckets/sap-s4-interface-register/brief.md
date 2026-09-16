# Task Brief: SAP S/4HANA Interface Register

## Objective
Give Archie a working Interface Register and As-Is/To-Be comparison for a SAP
S/4HANA integration programme, built entirely from existing ArchiMate 3.2
Application and Implementation & Migration layer models — no new bespoke
schema, no Excel-shaped fields.

## Context
Saint-Gobain is running an S/4HANA transformation: ~18 applications integrate
directly into S/4HANA, £3m budget. The data model to support this already
exists and is unused:

- `ApplicationInterface` / `ApplicationInterfaceMetadata`
  (`app/models/integration_metadata.py`) — protocol, message pattern,
  sync/async, `business_criticality`, `transaction_volume_daily`.
- `Plateau` / `Gap` / `WorkPackage` (`app/models/implementation_migration.py`)
  — already carry `estimated_effort_hours`, `estimated_cost`, and
  plateau-to-plateau gap linkage (`baseline_plateau_id`,
  `originating_plateau_id`, `target_plateau_id`).
- The initiative table at `implementation_migration.py:42` already carries
  `investment_budget`.

The one existing reference to `ApplicationInterfaceMetadata` is a read-only
enrichment block on a single element detail page
(`app/modules/architecture/routes/archimate_routes.py:2627`) — no CRUD, no
list view, no cost rollup. This is the ADR-0008 "store with no producer"
pattern: modelled correctly, never built out.

## Constraints
- No new top-level tables for "interface complexity" or "T-shirt size" —
  derive a size band (S/M/L/XL) from existing `WorkPackage.estimated_effort_hours`
  at display time; do not add a parallel free-text field.
- Every interface must be a real `ApplicationInterface` ArchiMate element (via
  `_sync_archimate_element()`), not a plain form field — per root CLAUDE.md's
  "the field *is* the element" rule.
- `TenantMixin` on any new/touched write path; this data is Saint-Gobain's,
  multi-org isolation applies.
- Must satisfy `store-agreement`, `fabricated-data`, `breadcrumb-coverage`
  gates — no screen may show a count another surface would answer
  differently.
- No non-nullable columns added to existing tables (`reconcile-schema` is
  ADD-only).
- One system of record: `ApplicationInterfaceMetadata` stays the only store
  for interface technical detail; `WorkPackage`/`Gap` stay the only store for
  remediation cost/effort. Do not duplicate either.

## Deliverable
1. **Interface Register** screen: list/create/edit `ApplicationInterface` +
   `ApplicationInterfaceMetadata` pairs, scoped to a named initiative (reuse
   the existing initiative/`investment_budget` table).
2. **As-Is/To-Be plateau comparison** for the interface landscape: two
   `Plateau`s ("Current Integration Landscape" / "S/4HANA-Integrated
   Landscape"), each interface's `Gap` between them, with `gap_kind` covering
   interface-specific gaps (protocol change, new interface, retirement).
3. **WorkPackage costing rollup**: sum `estimated_cost` /
   `estimated_effort_hours` across `WorkPackage`s linked to each `Gap`, rolled
   up against the initiative's `investment_budget` (£3m), with a derived
   T-shirt size band shown per work package.
4. Sidebar entry reachable by the relevant persona (solution architect /
   integration architect), per the Information Architect gate in root
   CLAUDE.md.

## Acceptance Criteria
- A browser walkthrough (`tests/smoke/`) as a named persona: create an
  interface, see it as a real ArchiMate element, raise a gap against a to-be
  plateau, attach a work package with a cost, and see the £3m rollup update —
  after a page reload.
- `store-agreement` gate: the rollup total on the register screen and any
  dashboard card referencing it agree.
- `python scripts/verify.py` clean; no new `fabricated-ok` / `tenancy-ok`
  escape hatches without a stated reason.
- Extends `tests/smoke/test_authorisation_matrix.py` for the new route(s).

## Handoff Target
`business-analyst` first (SRS from this brief, cross-checked against
ArchiMate 3.2's Application and Implementation & Migration metamodel) →
`integration-architect` + `solution-architect` in parallel → `tech-lead`
reconciles → `builder`.
