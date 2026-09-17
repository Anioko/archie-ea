# Task 01 result — Relationship import + element properties (R1 + R2)

Branch: `fix/archiet-dogfood-import`. Not committed — left for coordinator review per instruction.

## What changed

### R1 — relationships now written on execute_import

- `app/services/archimate_import_service.py`
  - `execute_import` now builds an OEF-identifier → `{db_id, type}` map
    during the element pass (including pre-existing elements matched under
    `skip_duplicates`/`update_existing`, so relationships touching them
    resolve), then writes relationships in a second pass.
  - Every candidate relationship is validated via
    `RelationshipValidator.validate_relationship()` (the tech-lead's ruled
    authority, `app/config/archimate_relationship_matrix.py`) before insert.
    A rejection is never dropped silently — it lands in
    `relationships_failed` with a human-readable `reason` and the
    validator's own `suggestions`. No raw exception string ever reaches the
    client; unexpected DB errors get a generic message and the real
    exception is only logged server-side.
  - Response now carries `relationships_created`, `relationships_skipped`
    (already-existing, same source/target/type), `relationships_failed`
    (list of `{identifier, type, source, target, reason, suggestions}`).
  - `preview_import` classifies relationships with the same
    `_classify_relationships()` helper (type-only, no DB duplicate check —
    preview cannot know the new elements' future ids), so preview and
    execute agree on which relationships are valid vs invalid. New summary
    keys: `relationships_valid`, `relationships_invalid`,
    `relationships_total`.
  - `ArchiMateImportService.VALID_RELATIONSHIP_TYPES` (flat set, dead code —
    grepped, no external reader) **deleted**, replaced with a comment
    pointing at the real authority.
  - `import_with_ids` — left in place, **unfixed**, with a docstring note
    explaining it is dead (nothing calls it) and that its own docstring is
    misleading (matches by name/type/layer despite claiming source-id
    matching). Flagged for a follow-up to fix or delete rather than let a
    third near-duplicate importer accumulate.

- Disposition of the other three relationship-validity vocabularies,
  recorded in code comments at each site per the brief:
  - `app/models/archimate_core.py::VALID_RELATIONSHIPS` (layer-triple) —
    **not retired**. Still read by `solution_ai_orchestrator.py`,
    `solution_archimate_routes.py`, `modules/genome/patch/coherence.py`.
    Comment added; importer does not call it.
  - `app/modules/architecture/routes/archimate_routes.py::ARCHIMATE_RELATIONSHIP_TYPES`
    / `_normalize_rel_type` — kept as a syntactic spelling check (not a
    metamodel check). `_normalize_rel_type` is **reused** (not duplicated)
    by the importer's `_classify_relationships`.

- **Third relationship-import surface found, out of scope, flagged:**
  `POST /archimate/api/import-oef` (`archimate_routes.py:6888`,
  `api_import_oef`) already does its own from-scratch element+relationship
  import with its own de-dup and its own duplicate-detection logic,
  entirely separate from `ArchiMateImportService`. Not touched — out of
  scope for this brief, which is specifically about the
  `/solutions/import/archimate/*` path — but it is a fourth near-duplicate
  importer alongside `execute_import`, `import_with_ids`, and
  `ArchiMateOEFService.import_model`, and should be on the list the next
  ADR-0008 cleanup pass works through.

### R2 — properties parsed, stored, rendered, exported

- `parse_oef_xml` now reads `<propertyDefinitions>` (id→name map) and each
  element's `<properties>/<property propertyDefinitionRef=…><value>`,
  returning a `properties: {name: value}` dict per element (empty dict, not
  `None`, when absent — never fabricated).
- `execute_import`/`create_all` write that dict into
  `ArchiMateElement.custom_properties` (confirmed real column) via a shared
  `_write_properties` helper: literal keys, no renaming, no coercion, plus
  one reserved `archie:imported_at` (ISO 8601 UTC) provenance key.
  `update_existing` merges into existing `custom_properties`;
  `skip_duplicates` leaves an existing element's properties untouched
  (matches the "don't touch skipped rows" contract already in place for
  `description`).
- **Column-duplication finding, not in the original brief:** the normal
  runtime mapping (`app/models/models.py:274`) carries a *second*,
  independent `ArchiMateElement.properties` column (`db.Text`, JSON
  string), already populated by older financial/tagging features
  (`annual_cost`, `owner` — see `tests/test_qa100_cm01_o02_o03.py`'s
  pre-existing `test_oef_export_includes_property_definitions_and_values`).
  This is two systems of record for "element properties." Not resolved
  here — flagged in the ADR 0009 addendum — but export now reads and merges
  **both** (`custom_properties` wins on a key collision) so neither an OEF
  import nor a pre-existing `properties` value is silently dropped.
- **Element detail view** (`app/templates/architecture/elements.html`): the
  detail drawer's `selectElement()` now also fetches
  `/archimate/api/elements/<id>/detail` (which already returned
  `custom_properties` — `archimate_routes.py:2494`, unused by the UI until
  now) and renders every non-`archie:` key as a label/value row under a new
  "Properties" section, `—` when empty (never `{}` or blank).
  **Found and fixed in passing:** the pre-existing relationships fetch on
  the same page used `/architecture/api/elements/<id>/relationships`, which
  resolves to a *different* blueprint's handler
  (`app/modules/architecture/routes/archimate_crud/routes.py:1583`) than
  the one this task actually needs (`archimate_routes.py`, `/archimate/api/...`)
  — same URL shape, two different blueprints, ADR-0008 violation. Left the
  pre-existing relationships call as-is (out of scope) but used the
  correct, explicit `/archimate/api/...` path for the new properties fetch
  and left a comment explaining why, so the ambiguity is not silently
  repeated.
- **Export.** `ArchiMateOEFService.export_model()` /
  `export_model_validated()` (`app/services/archimate_oef_service.py`) is
  the whole-model OEF exporter (`model_id=None` = every element, already
  reachable at `GET /architecture/export/oef` — no new exporter added, per
  ADR 0008). It already emitted `<propertyDefinitions>`/`<properties>` but
  read a non-existent-for-this-purpose path (see the column-duplication
  finding above); fixed to read `custom_properties` (merged with the legacy
  `properties` column) and to exclude the `archie:` namespace, per the
  round-trip rule.
  `ArchimateOEFExportService.export_solution()` (solution-scoped,
  `app/services/archimate_oef_export_service.py`) is a different,
  legitimately separate use case (export one solution's elements, not the
  whole model) and was left untouched.
- **New reachable page.** `solutions/partials/_import_preview.html` (the
  Alpine panel driving `/solutions/import/archimate/preview` + `.../execute`)
  existed but was never included on any page — dead UI, unreachable. Added
  `GET /solutions/import/archimate` (`solution_import_routes.py`) +
  `app/templates/solutions/import_archimate.html` rendering it, and a
  discoverable "Import OEF Model" link from the ArchiMate Element Catalog
  toolbar (`app/templates/architecture/elements.html`).
- **ADR.** `docs/adr/0010-*` was already taken (enterprise-genome), so the
  property-import convention is recorded as an **addendum to ADR 0009**
  (`docs/adr/0009-continuous-model-maintenance.md`), including the ADR-0009
  reference not resolving to an existing spec, the minimal convention
  itself, and the `properties`/`custom_properties` duplication finding.
  Flagged for solution-architect to renumber into a standalone ADR if a
  fuller property-governance decision is made later.

## Fixture

`tests/fixtures/oef/archiet_shaped.xml` — 15 elements across Strategy/
Business/Application/Technology/Motivation/Implementation layers, 13
relationships (12 valid, individually confirmed against
`RelationshipValidator` — see test file — 1 deliberately-invalid
`Composition(ApplicationComponent → BusinessActor)`), and a
`M-CON-10G-FREE-PILOTS`-shaped `Constraint` element carrying
`status`/`source`/`layer` properties matching the customer's shape.

## Tests

- `tests/test_archimate_import_service.py` (5 tests, all pass against a
  real Postgres via the shared `db_session`/`tenant_ctx` fixtures):
  property parsing, relationship creation + failure classification,
  preview/execute agreement, idempotent re-import (0 new / 0 conflict),
  export→reimport property round-trip.
- Pre-existing `tests/test_qa100_cm01_o02_o03.py` and
  `tests/test_oef_export_direction_validation.py` still pass (20/20
  combined with the new file) — the property-column merge fix did not
  regress the older `annual_cost`/`owner` export test.
- `tests/smoke/test_oef_import_journey.py` — **real Playwright browser
  journey**, not a source-reading claim: logs in as `solution_architect`,
  navigates to `/solutions/import/archimate`, uploads the fixture through
  the real file input, clicks "Preview Import" then "Import Elements",
  reloads `/architecture/elements`, searches for the Constraint element,
  clicks its row, reads the rendered Properties panel (`status`/`RULED`,
  `layer`/`Motivation`), and independently checks
  `/archimate/api/elements/<id>/detail` and `/archimate/api/relationships`
  confirm persistence. **Passed** (see `/tmp/oef_smoke4.log`-equivalent —
  `1 passed`).

## Verification

- `python scripts/verify.py --tag static`: **48 passed, 0 failed, 0
  skipped**.
- `python scripts/verify.py` (bare, full): kicked off; see coordinator/
  refuter for the final result — it was still running (the `tests` gate
  runs the whole suite against Postgres) at the time this doc was written.
  All targeted tests above are green; no reason to expect the bare run to
  differ, but per "Done means DEMONSTRATED" this doc does not claim it
  green without having watched it finish.

## Round 2 (refuter B1-B4, M5, M6, M9)

- **B1** — `_import_preview.html` never rendered any relationship result.
  Added a "Total/Valid/Invalid" tile row to the preview summary
  (`preview.summary.relationships_total/valid/invalid`) and a
  "Created/Skipped/Failed" panel plus a per-failure reason list to the
  "Import Complete" panel (`importResult.relationships_created/skipped/
  failed`). Renamed the execute button "Import Elements" -> "Import Model"
  since it writes relationships and properties too.
- **B2** — `elements.html`'s properties fetch `catch` set
  `customProperties = []` on any failure, indistinguishable from a genuine
  zero-properties element. Added a `propertiesError` flag mirroring
  `relationshipsError`, and a "Could not load properties." error state
  rendered instead of the em-dash when it's true.
- **B3** — corrected in place below (not deleted) per instruction: the
  original claim that `ArchiMateRelationship` carries no `TenantMixin` was
  false. See the struck-through entry in "Known gaps" for the correction and
  the real bug it was masking (fast-init dual-mapper orphan rows).
- **B4** — `archimate_oef_service.py` exported `xsi:type` in whatever case
  `rel.type` was stored in (lowercase, per the importer's normalization),
  which is not valid per the OEF/XSD spec and is rejected by a real
  conformant tool (Archi) even though Archie's own importer tolerates it by
  lowercasing again on read. Added `_PASCAL_CASE_REL_TYPES`, built from
  `RELATIONSHIP_TYPES` (the same canonical authority `RelationshipValidator`
  already uses — `t.capitalize()`, since every name in that list is a single
  lowercase word) rather than a second hardcoded spelling list, and used it
  for the exported `xsi:type` attribute. The ArchiMate-3.2-matrix
  valid/invalid/reversed direction check right above it still compares on
  the lowercase key, unaffected.
- **M5** — strengthened `test_export_then_reimport_preserves_custom_properties`:
  now also asserts `new == 0` / `exists == 15` (not just `conflict == 0`,
  which alone doesn't rule out a full silent re-creation), and actually
  calls `execute_import` on the reimported/exported XML rather than only
  previewing it, asserting `created == 0`, `skipped == 15`, and that the
  relationship count is unchanged — this is the assertion that would catch
  export reversing or dropping an edge via `ArchimateValidityService`
  disagreeing with `RelationshipValidator`. **Fifth relationship-validity
  vocabulary, disposed here as required:** `ArchimateValidityService`
  (`app/services/archimate_validity_service.py`) is used only by
  `ArchiMateOEFService.export_model_validated()`'s direction-check pass
  (`archimate_oef_service.py:110-ish`) — a *different* authority than the
  importer's `RelationshipValidator`
  (`app/modules/architecture/services/relationship_validator.py`). Both
  claim to encode "the ArchiMate 3.2 matrix" independently; they were not
  reconciled here (out of this task's brief) but the strengthened test now
  at least detects the failure mode if they disagree on the fixture's 12
  valid relationships. Flagged for the same ADR-0008 cleanup pass as the
  other four relationship-validity vocabularies in this doc.
- **M6** — the element-import `except` block (unlike the relationship one)
  put the raw exception string straight into `errors` and never rolled back
  the session, so a single bad element's failed flush left the transaction
  in `InFailedSqlTransaction` for every subsequent element in the same
  batch. Sanitized the message to match the relationship path's
  "internal error" wording, and added `db.session.rollback()`. **Known
  limitation, left for Task 03 (R4/partial-commit) per this brief's
  instruction:** without a per-element `begin_nested()` savepoint (Task 03's
  deliverable), this `rollback()` undoes the *whole* session, including
  elements already added-but-uncommitted earlier in the same
  `execute_import` call — so today a mid-batch element failure still
  discards the batch's prior successes rather than isolating just the bad
  row. That is strictly better than the pre-fix state (which cascaded into
  every *later* element failing too, with a misleading `created: 0`
  suggesting nothing at all was attempted) but is not full partial-commit;
  Task 03 is the fix for that.
- **M9** — added a `/solutions/import/archimate` row to
  `tests/smoke/test_authorisation_matrix.py`'s `POLICY` dict, `set(ARCHETYPES)`
  (the route carries only `@login_required`, no role gate at all), matching
  the existing `/ai-chat` precedent for "deliberately wide open, pin it so a
  change is visible."

## Round 2 verification

- `tests/test_archimate_import_service.py`: **5 passed** (includes the
  strengthened M5 round-trip test).
- `tests/smoke/test_oef_import_journey.py`: **1 passed** (updated for the
  renamed "Import Model" button and now also asserts the new
  `[data-testid='relationship-import-result']` panel is visible with the
  fixture's 12-created/1-failed shape — B1's browser-level proof).
- `tests/smoke/test_authorisation_matrix.py`: **71 passed** (includes the new
  `/solutions/import/archimate` row).
- `python scripts/verify.py --tag static`: **47 passed, 1 failed** —
  `evidence-contract` (ratchet, ships at 30 > baseline 29). Investigated:
  the one new item is commit `45c60a3b` ("fix(ui): add horizontal
  scroll-fade affordance to workbench_table"), which was already on this
  branch/`main` before this session started (see the repo's own recent-commit
  log) and touches an unrelated file (`workbench_table.html`). Not
  introduced by this round's changes — pre-existing regression to flag to
  whoever owns that commit, not fixed here (out of this bucket's scope).
- `python scripts/verify.py --require-db` (bare, full, run to completion by
  me this round, not left to refuter): **53 passed, 3 failed** —
  `evidence-contract` (as above, pre-existing/unrelated), plus:
  - **`tests`** — the `unit+integration` pytest subprocess hangs inside
    `tests/journeys/test_journey_arb_member.py` (collected 5550 items,
    progressed 4 into `tests/csp/test_csp_evaluator.py`, then stalled with
    zero further progress). Reproduced in isolation
    (`pytest tests/journeys/test_journey_arb_member.py`, hangs with no
    output past collection) — confirmed pre-existing and unrelated to any
    file this bucket touches (`tests/journeys/` is a different suite
    entirely; nothing in this round's diff touches ARB, journeys, or that
    conftest). Not fixed here — flagging for whoever owns
    `tests/journeys/test_journey_arb_member.py` or the shared journeys
    fixtures; this is a pre-existing environment/test defect, not something
    introduced by relationship/property import work.
  - **`nav-verified`** — 63 sidebar-reachable routes with no test loading
    them (pre-existing baseline-exceeding count; `/solutions/import/archimate`
    is **not** in that list — it isn't a sidebar link, per the original
    round's note that it's reached from the ArchiMate Element Catalog
    toolbar, and it now has direct smoke coverage). Not this bucket's
    regression.

**Honest bottom line:** the bucket's own targeted tests (unit + both smoke
journeys) are green, and both bare-run failures are demonstrably pre-existing
and outside this bucket's file set — not something to report as "done with a
known issue" on this task, but also not fixed here since they belong to
different owners (`workbench_table.html` UI work; the ARB journeys test
suite). Bare `verify.py` is **not** green; refuter/coordinator should route
the two pre-existing failures to their respective owners rather than back
into this bucket.

## Known gaps / follow-ups (not fixed here, flagged per CLAUDE.md's
"docs/known-issues is a decision record, not a backlog" — these are
genuinely out of this task's scope, not deferred bugs)

1. `properties` (legacy `db.Text`) vs `custom_properties` (`db.JSON`) is a
   second system of record for "element properties" — export merges both,
   nothing deduplicates them. Needs its own ADR-0008 cleanup pass.
2. A fourth near-duplicate OEF importer (`POST /archimate/api/import-oef`)
   exists, untouched.
3. `import_with_ids` is dead and its docstring is wrong; left broken rather
   than fixed, per the brief's "do not build on it without fixing it" —
   fixing it was not this brief's deliverable.
4. `/architecture/api/elements/<id>/relationships` and
   `/archimate/api/elements/<id>/detail` are two same-shaped URLs on two
   different blueprints; only the second carries `custom_properties`. Not
   unified here.
5. **CORRECTED per refuter B3 — the claim below was FALSE and is left in
   place, struck through, per CLAUDE.md's "correct in place, don't delete"
   convention, because it was a real defect in this document, not just in
   the code.** ~~`ArchiMateRelationship` carries no `TenantMixin` (confirmed,
   per the brief's instruction to say so explicitly) —
   `/archimate/api/relationships` pooled relationships across every org in
   the shared test database during manual/smoke verification.~~ This is
   wrong: there are **two** `ArchiMateRelationship` classes.
   `app/models/models.py:468` (re-exported by `archimate_core.py:22-24`) DOES
   carry `TenantMixin` and is the one mapped in normal runtime — the
   `/archimate/api/relationships` endpoint reachable in production and in
   every normal test run **is** tenant-scoped. `app/models/archimate_core.py:110`
   defines a second, un-tenanted `ArchiMateRelationship` that is only mapped
   when `APP_FAST_INIT=1` (the fast e2e-test bootstrap path), and that is
   almost certainly what the manual/smoke verification above actually
   exercised, which is why it looked pooled.

   **The real bug this masked:** under `APP_FAST_INIT=1`, `execute_import`
   writes relationships through whichever `ArchiMateRelationship` mapper is
   currently registered — the untenanted one in fast-init mode — so those
   rows get `organization_id=NULL` and are invisible to any normal-runtime
   read (which filters on `organization_id` via `TenantMixin`/
   `do_orm_execute`). This is a real orphan-row / silently-invisible-data
   bug confined to the `APP_FAST_INIT=1` bootstrap path, not a cross-org
   leak in the shipped code path. Not fixed in this round — de-duplicating
   the two `ArchiMateRelationship` mappers is an ADR-0008 cleanup on the
   order of the `properties`/`custom_properties` duplication above, and is
   out of a template/service-fix-scoped round; flagged here for that
   cleanup pass. Until then, don't run OEF import against a fast-init
   (`APP_FAST_INIT=1`) app instance and expect the written relationships to
   be readable afterwards.


## Round 4 (refuter D1 -- round-3's M6 fix introduced a new blocker)

- **D1 (BLOCKER, fixed)** -- `db.session.rollback()` (added in round 2 to fix
  M6) rolls back the whole transaction on an element-flush failure, but the
  loop-local `created`/`updated`/`skipped` counters and `id_map` were not
  reset alongside it. Refuter traced the exact failure: elements
  `[A, BAD, C, D]` where `BAD` raises on flush -- `A` flushes first
  (`id_map["A"]=101`, `created=1`), `BAD`'s failure triggers `rollback()`
  which deletes row 101 from the DB, but `created` stays `1` and
  `id_map["A"]` still points at the now-nonexistent id 101. Depending on
  whether a relationship in the batch touches `A`, this produced either a
  phantom-FK secondary commit failure (masking the real cause) or -- the
  actual blocker -- a confidently wrong non-zero `created` count reported to
  the user for an element that no longer exists.

  **Fix** (`app/services/archimate_import_service.py`, element pass): on any
  element-flush exception, after `db.session.rollback()`, now also resets
  `created = 0`, `updated = 0`, `skipped = 0`, and `id_map.clear()`, sets a
  new `element_batch_failed` flag, appends an error stating the *entire*
  element batch was discarded (not just the one element that raised), and
  `break`s out of the element loop -- no further elements in the batch are
  attempted, since the transaction's state after an uncontrolled rollback is
  no longer trustworthy to build further inserts on top of. Immediately
  after the loop, `if element_batch_failed:` short-circuits and returns
  `created=0, updated=0, skipped=0, relationships_created=0,
  relationships_skipped=0, relationships_failed=[]` plus the accumulated
  `errors` -- the relationship pass (which reads `id_map`) never runs at all
  after a batch failure, so it cannot silently succeed against an empty map
  or attempt a phantom-FK write.

  This matches refuter's suggested minimal fix (treat the whole batch as
  invalidated) and stays within this round's scope -- true per-element
  savepoint isolation (so a single bad element doesn't sacrifice the rest of
  a large, otherwise-good batch) remains Task 03's (R4/partial-commit)
  deliverable, unchanged from round 2's note above.

- **New regression test** --
  `tests/test_archimate_import_service.py::test_element_flush_failure_discards_whole_batch`
  reproduces refuter's exact repro: elements `[A, BAD, C]`, `db.session.flush`
  monkeypatched to raise on the second call (BAD's), asserts the response is
  `created=0, updated=0, skipped=0, relationships_created=0,
  relationships_failed=[]` with a "discarded" error message, and -- the part
  that actually catches the D1 defect -- that **none** of `A`, `BAD`, or `C`
  exist in the DB afterward (before the fix, `A` would have been left
  reported-created despite no longer existing).

### Round 4 verification

- `tests/test_archimate_import_service.py`: **6 passed** (5 pre-existing +
  the new D1 regression test).
- `tests/smoke/test_oef_import_journey.py`: **1 passed** -- real Playwright
  journey unaffected by the fix (its fixture has no flush-failing element).
- `tests/smoke/test_authorisation_matrix.py`: **71 passed**.
- `python scripts/verify.py --tag static`: **47 passed, 1 failed** --
  `evidence-contract` (ratchet, `30 > 29`), the same pre-existing,
  unrelated-to-this-bucket item identified in round 2 (commit `45c60a3b`,
  touches `workbench_table.html`, already present on the branch before this
  session). No new static failure introduced by the D1 fix.

**Commit-message note for whoever lands this bucket:** this round's diff
(`app/services/archimate_import_service.py` +
`tests/test_archimate_import_service.py`) is a behavioural fix, so per
CLAUDE.md's evidence-contract gate the eventual commit for this bucket needs
its own `Evidence:` trailer citing the actual commands run -- at minimum:
`pytest tests/test_archimate_import_service.py`,
`pytest tests/smoke/test_oef_import_journey.py`,
`pytest tests/smoke/test_authorisation_matrix.py`, and
`python scripts/verify.py --tag static`. Omitting it moves the
`evidence-contract` ratchet from 30 to 31 for a *second*, newly-introduced
reason on top of the pre-existing `45c60a3b` one -- don't conflate the two
when that commit lands.

**Not committed this round** -- left uncommitted per standing instruction for
coordinator/refuter review.
