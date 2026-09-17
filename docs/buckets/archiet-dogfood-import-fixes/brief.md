# Task Brief: Archiet Customer-Zero Dogfood Import Fixes (DOGFOOD-001..005)

## Objective
Fix five defects found when Archiet Ltd imported its real enterprise model
(ArchiMate 3.2 Open Exchange XML, 168 elements, 121 relationships) through
Archie's OEF importer and inspected the result in the Element Catalog. Each
defect (R1-R5) must be demonstrated working in the deployed instance, not
just covered by a green test.

## Context
Archiet Ltd is "customer zero" — a real dogfood user importing their real
model via `POST /solutions/import/archimate/preview` and `/execute`. They
found five defects, each already root-caused with exact file:line references
by the reporter (verified independently against the current code before this
brief was written — all references confirmed accurate):

- `app/services/archimate_import_service.py`: `parse_oef_xml` (line 109)
  parses relationships but `execute_import` (line 322) never writes them.
  `<properties>`/`<propertyDefinitions>` are parsed nowhere — only `<name>`
  and `<documentation>`.
- `app/models/archimate_core.py:58`: `ArchiMateElement.name` is
  `String(100)`; `type` is `String(50)`, `layer` is `String(30)`. `execute_import`
  does one bulk `db.session.commit()` (line 404) — any single row's DB error
  rolls back the entire batch and returns the raw exception string.
- Layer vocabulary: the importer writes `"Implementation & Migration"`
  (lines 91-95) but the catalog counts/filters on `"Implementation"` —
  confirmed as a real mismatch, not yet independently verified against the
  catalog route's exact filter logic (that verification is this bucket's
  first job, under R3).
- The OEF import panel (`app/templates/solutions/partials/_import_preview.html`)
  is only reachable from `batch_import/job_detail.html` — not from the
  Element Catalog itself.

## Constraints
- Per this repo's CLAUDE.md ADR 0008 ("one system of record per concept"):
  R3 must produce ONE canonical layer vocabulary shared by importer, models,
  catalog, and filters — not a second mapping table patching over the
  mismatch.
- No non-nullable columns added without a migration/backfill plan;
  `reconcile-schema` is ADD-COLUMN-only per this repo's schema conventions.
- R4's product decision (widen `name` to 255 vs. keep 100 and rely on
  preview-side validation) is explicitly a founder/product call, not an
  engineering one — do not decide it silently; surface it for explicit
  sign-off, matching this repo's own escalation convention for commercial/
  product-direction questions with no technically-correct answer.
- R1 and R2 may share one PR (per the customer's own instruction); R3, R4,
  R5 are separate PRs.
- Per root CLAUDE.md's "Done means DEMONSTRATED" rule: each R needs a real
  browser test performing the actual journey and asserting persistence
  after reload — not just a green unit test.

## Deliverable
Five fixes, in the specified order (R1 → R2 → R3 → R4 → R5):

- **R1**: `execute_import` writes every relationship after elements,
  resolving source/target by the imported element identifier, honouring a
  valid-relationship-types table. **Two such tables already exist and must
  be reconciled, not duplicated a third time:**
  `ArchiMateImportService.VALID_RELATIONSHIP_TYPES`
  (`app/services/archimate_import_service.py:99`, a flat set of OEF
  `xsi:type` names) and `VALID_RELATIONSHIPS`
  (`app/models/archimate_core.py:212`, a `(type, source_layer,
  target_layer) → bool` matrix). Determine which is authoritative for this
  use (the matrix is almost certainly the one to honour, since it encodes
  the actual metamodel constraint the flat set does not) and note the
  other's fate (retire, or state why both remain) per this repo's ADR 0008
  "one accessor per concept" rule. Response includes
  `relationships_created` / `relationships_skipped` / `relationships_failed`
  with reasons.
- **R2**: every `<property propertyDefinitionRef=…><value>` stored on the
  element's `custom_properties` JSON column (`app/models/archimate_core.py:80`
  — corrected from the customer's "`properties`"; no column of that name
  exists), keyed by the property definition's `<name>`. **Correction found
  during bucket setup, not yet resolved:** ADR 0009
  (`docs/adr/0009-continuous-model-maintenance.md`) exists but is about
  scheduled drift-detection, not a `status`/`source`/`as_of` → model-age
  field mapping — no such mapping currently exists anywhere in the codebase.
  This is a genuine gap, not something to silently invent a spec for:
  solution-architect must either find the right existing convention (grep
  further before assuming there is none) or write the minimal mapping as
  part of this task's own design doc, and should flag to the customer if
  their "(ADR 0009)" reference was aspirational/a different document.
  Element detail page shows all properties. OEF export writes them back so
  import→export→import round-trips losslessly.
- **R3**: one canonical layer vocabulary shared by importer, models,
  catalog, and filters. A migration normalises existing rows. The
  store-agreement gate fails if any stored layer value is one the UI does
  not render.
- **R4**: (a) preview reports every constraint execute will apply, per
  element, with a suggested fix; (b) execute uses a savepoint per element,
  commits what's valid, returns HTTP 207 with failed identifiers and
  human-readable reasons — never a raw DB exception string; (c) the
  name-length product decision surfaced explicitly for founder sign-off.
- **R5**: an "Import model (OEF XML)" action on the Element Catalog header
  and empty state, rendering the existing panel. Diagram importer stays
  separate.

## Acceptance Criteria
- R1: import the Archiet OEF file → `GET /archimate/api/relationships`
  total == 121; catalog banner no longer says "No relationships: 168";
  preview and execute counts match.
- R2: open `M-CON-10G-FREE-PILOTS` → properties show
  `status=RULED`, `source="founder ruling 2026-07-19 —
  strategy/10G-ASSESSMENT-OFFER.md …"`, `layer=Motivation`; export →
  re-import reports 168 "exists", 0 "new", 0 "conflict".
- R3: catalog tiles sum to 168; Implementation tile shows 35 with
  WorkPackage/Deliverable/Plateau/ImplementationEvent/Gap breakdown;
  "All Layers" filter lists it.
- R4: import the original (unfitted) Archiet file: preview lists long-name
  elements with the exact limit; execute creates every valid element and
  returns 207 naming the rest.
- R5: from `/architecture/elements`, reach the OEF panel in one click,
  preview, import, land back on the catalog with new counts.

## Handoff Target
`tech-lead` first (this brief already carries SDD-level acceptance
criteria and root-caused file references from the customer report — no
business-analyst discovery pass needed) → produces 4-5 task briefs (R1+R2
combined, R3, R4, R5) → `builder` implements each, `refuter` reviews each,
same cycle as the sap-s4-interface-register bucket. One PR per task per the
customer's own instruction; `main` only receives a task's work after
refuter approval, matching this repo's established convention.

## Test fixtures — the real ground-truth file is not in this repo
`ground-truth/model/archiet.archimate` does not exist in this checkout (it is
Archiet's own proprietary model, not something to expect committed here).
`docs/dogfood/` does not exist yet either. Each task's automated/browser
tests need a synthetic OEF fixture built to the same shape the acceptance
criteria describe (168-ish elements across all six layers, 121-ish
relationships, at least one element with `<properties>` matching the
`M-CON-10G-FREE-PILOTS` shape — `status`/`source`/`layer` — and at least one
element with a >100-char name for R4) — do not block on requesting the real
file; construct a representative one and say so plainly in the result doc.
The customer's own re-test with their real file happens separately, in
their own session, against the deployed instance — that is the actual
acceptance gate, not this pipeline's fixture-based tests.

## Verification note (customer will re-run this after each deploy)
1. Import `ground-truth/model/archiet.archimate` (unfitted names) → expect
   168 elements, 121 relationships, 0 raw errors, Implementation tile = 35.
2. Open `M-CON-10G-FREE-PILOTS` → status RULED, source shown, age shown.
3. Export OEF → re-import → 168 exists / 0 new / 0 conflict.
4. Catalog banner: no "No relationships" warning.

Append results to `docs/dogfood/ARCHIET-CUSTOMER-ZERO.md` — rows close
only on a pass, and only the customer/founder closes them, not this
pipeline self-certifying.
