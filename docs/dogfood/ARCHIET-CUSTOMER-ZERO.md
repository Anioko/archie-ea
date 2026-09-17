# Archiet Ltd — Customer Zero dogfood log

Archiet Ltd is Archie's first real dogfood user, importing its own enterprise
model (ArchiMate 3.2 Open Exchange XML, 168 elements, 121 relationships)
through the OEF importer and inspecting the result in the Element Catalog.

**This file is the acceptance gate for the `archiet-dogfood-import-fixes`
bucket (DOGFOOD-001..005).** It is filled in by the customer/founder after a
deploy, against their **real** model file — not by the delivery pipeline, and
not against the synthetic fixture the automated tests use.

## How to use this file

- One block per deploy. Copy the template below, fill in the date and the
  deployed commit, run the four steps, record what you actually saw.
- **A row closes only on a pass, and only the customer/founder closes it.**
  No row in this file may be pre-filled as passing by an agent or a build.
  An empty result cell means the step has not been run — it does not mean
  the step is fine.
- If a step fails, paste the actual observed value and any error text. "Did
  not work" is much less useful than the number that was wrong.
- The automated tests in this bucket run against a **synthetic** fixture
  (`tests/fixtures/oef/archiet_shaped.xml`), built to the same shape as the
  real model. A green test run is evidence of no regression in the code; it
  is not evidence that these four steps pass. That is what this file records.

## Re-test steps

1. **Import** `ground-truth/model/archiet.archimate` (the unfitted file, with
   original names) → expect 168 elements, 121 relationships, 0 raw errors,
   Implementation tile = 35.
2. **Open `M-CON-10G-FREE-PILOTS`** → expect `status` RULED, `source` shown,
   age shown.
3. **Export OEF → re-import** → expect 168 "exists" / 0 "new" / 0 "conflict".
4. **Catalog banner** → expect no "No relationships" warning.

## Finding status (code side — not acceptance)

A fix being merged is not a row passing above; only the deploy log closes a step.

| Finding | What it was | Code status |
|---|---|---|
| DOGFOOD-001 | One over-long name aborted the whole import with a raw SQL error | fix in PR #__PR_NUMBER__ (preview flags `name_too_long`, execute writes each element in its own savepoint and returns `failed`) |
| DOGFOOD-002 | Implementation & Migration elements imported but invisible in the catalog | fix in PR #__PR_NUMBER__ (importer writes the catalog's `Implementation` layer key) |
| DOGFOOD-003 | Relationships parsed and previewed, never written | fixed on `main` in f5362b5; relationship `<documentation>` persisted in PR #__PR_NUMBER__ |
| DOGFOOD-004 | OEF `<properties>` dropped on import | fixed on `main` in f5362b5 |
| DOGFOOD-005 | No entry point to the OEF importer from the catalog | fixed on `main` in f5362b5; empty-state link added in PR #__PR_NUMBER__ |

---

## Deploy log

### Deploy: _(not yet run)_

- Date:
- Commit / build_id:
- Tested by:
- Model file used:

| # | Step | Expected | Observed | Pass? |
|---|------|----------|----------|-------|
| 1 | Import unfitted model | 168 elements, 121 relationships, 0 raw errors, Implementation tile = 35 | | |
| 2 | Open `M-CON-10G-FREE-PILOTS` | status RULED, source shown, age shown | | |
| 3 | Export OEF → re-import | 168 exists / 0 new / 0 conflict | | |
| 4 | Catalog banner | no "No relationships" warning | | |

Notes:

---

<!--
Copy this block for each subsequent deploy. Do not delete previous blocks —
the history of what failed and when is the point.

### Deploy: <date>

- Date:
- Commit / build_id:
- Tested by:
- Model file used:

| # | Step | Expected | Observed | Pass? |
|---|------|----------|----------|-------|
| 1 | Import unfitted model | 168 elements, 121 relationships, 0 raw errors, Implementation tile = 35 | | |
| 2 | Open `M-CON-10G-FREE-PILOTS` | status RULED, source shown, age shown | | |
| 3 | Export OEF → re-import | 168 exists / 0 new / 0 conflict | | |
| 4 | Catalog banner | no "No relationships" warning | | |

Notes:
-->

## Open questions awaiting founder ruling

| # | Question | Raised by | Status |
|---|----------|-----------|--------|
| E1 | Widen `ArchiMateElement.name` from 100 to 255 characters, or keep 100 and rely on import-preview validation to flag over-long names? Note: widening is a column **retype**, which `reconcile-schema` cannot do — it needs a real migration and a maintenance window (ADR 0002). Evidence (which real elements exceed 100, and by how much) will be available once task 03's preview validation ships. | tech-lead, bucket `archiet-dogfood-import-fixes`, task 03 (R4c) | **Open — not decided** |
| E2 | The customer's brief cited "ADR 0009" for a `status`/`source`/`as_of` property mapping. ADR 0009 is about scheduled drift detection and defines no such mapping; none exists anywhere in the codebase. A minimal convention (literal keys inside `custom_properties`, no new columns) is proposed in task 01 and is to be written up as ADR 0010 or an ADR 0009 addendum. Confirm whether the original "(ADR 0009)" reference pointed at a different document. | tech-lead, bucket `archiet-dogfood-import-fixes`, task 01 (R2) | **Open — awaiting customer confirmation** |
