# Task 01 — Relationship import + element properties (R1 + R2)

Handoff target: `builder` → `refuter`
Branch: `fix/archiet-dogfood-import` · one PR (R1+R2 combined per the customer's instruction)

## Objective

Make the OEF importer write the relationships it already parses, and carry
each element's `<properties>` through import, display and export so an
import → export → import round-trip is lossless.

## Context

`ArchiMateImportService.parse_oef_xml`
(`app/services/archimate_import_service.py:109`) already returns a
`relationships` list (lines 212-237) with `identifier`, `type`, `source`,
`target`. `execute_import` (line 322) iterates **elements only** (line 354)
and never reads `parsed_data["relationships"]` — so 121 relationships parse
and none persist. `preview_import` (line 250) passes them through untouched
(line 314) without classifying them.

`execute_import` also does not record the OEF `identifier` anywhere, so there
is no map from the XML's `id-elem-N` to the new DB id. A sibling method
`import_with_ids` (line 427) builds exactly such an `id_map` (line 483) but is
not what the routes call — `/solutions/import/archimate/execute` calls
`execute_import` (`app/modules/solutions_strategic/v2/routes/solution_import_routes.py:105`).
Note `import_with_ids` is misleading: despite its name and docstring it
matches on `name/type/layer`, never on `source_id` (line 470-472). Do not
build on it without fixing or retiring it.

`<properties>` / `<propertyDefinitions>` are parsed nowhere: the element loop
reads only `<name>` (line 176) and `<documentation>` (line 182).

**Column correction (already applied to the brief).** The target column is
`ArchiMateElement.custom_properties`, a nullable `db.JSON` defaulting to
`dict` (`app/models/archimate_core.py:80`). There is no column named
`properties`. No schema change is needed for R2's storage.

**Export half.** `ArchimateOEFExportService._add_element`
(`app/services/archimate_oef_export_service.py:160-177`) writes only
`identifier`, `xsi:type`, `<name>` and `<documentation>`. It emits no
`<properties>` and the model root has no `<propertyDefinitions>`, so
properties cannot survive a round-trip today. Note also that the only export
entry point is `export_solution(solution_id)` (line 89), scoped to elements
joined through `solution_archimate_elements` — there is no whole-model OEF
export, which R2's acceptance criterion 3 requires. Find or add one; check
`archimate_oef_service.py`, `archimate_export_service.py` and
`archimate_xml_export_service.py` first and **pick one** per ADR 0008 rather
than adding a fourth exporter.

### Relationship validity — the authority is already decided

Do not introduce a new table. Five already exist (see
`../implementation-plan.md` F3). **Use
`app/config/archimate_relationship_matrix.py` via
`RelationshipValidator.validate_relationship(source_type, target_type,
relationship_type)`** (`app/modules/architecture/services/relationship_validator.py:122`).
It is element-type-keyed (the real metamodel constraint), carries cardinality,
and returns `suggestions` that task 03 reuses for R4a.

You must record the disposition of the other three in the PR description and
in a comment at each site:

- `ArchiMateImportService.VALID_RELATIONSHIP_TYPES` (`archimate_import_service.py:99`) — a flat set of 11 OEF `xsi:type` spellings. Keep **only** if it is doing syntactic `xsi:type` recognition that the matrix does not; otherwise delete it. Either way it must stop being a second opinion on validity.
- `VALID_RELATIONSHIPS` (`app/models/archimate_core.py:212`) — layer-triple matrix. Do not call it from the importer. State whether it is retired or what still reads it (grep first).
- `ARCHIMATE_RELATIONSHIP_TYPES` / `_normalize_rel_type` (`app/modules/architecture/routes/archimate_routes.py:1417-1427`) — used by `POST /archimate/api/relationships`. Reuse `_normalize_rel_type` for casing if it fits; do not duplicate it.

### Property convention — NEW, and flagged as such

ADR 0009 (`docs/adr/0009-continuous-model-maintenance.md`) was read in full
during planning. **It does not define a `status`/`source`/`as_of` mapping.**
It proposes *model age* as the success measure (lines 94-97) but names no
field, no keys, no store. Nothing else in the tree defines one. The
customer's "(ADR 0009)" reference is aspirational.

Per the plan's instruction, do not block on a new ADR. Implement this
**minimal** convention:

- Every `<property>` is stored as a literal key in `custom_properties`, keyed
  by the referenced `<propertyDefinition>`'s `<name>`, value as the string in
  `<value>`. No key renaming, no type coercion, no allow-list.
- **No new columns.** `status`, `source` and `as_of` are ordinary keys inside
  that JSON like any other — they get no privileged storage.
- Reserve one namespaced key for provenance, `archie:imported_at` (ISO 8601),
  so a future model-age implementation has something to read and so an
  imported property is distinguishable from a hand-entered one. Namespacing
  it prevents a collision with a customer property genuinely called
  `imported_at`.
- Round-trip rule: export writes back every key **except** the `archie:`
  namespace, so re-importing an exported file produces byte-identical
  `custom_properties` for the customer's own keys.

**Flag, for solution-architect/builder to settle during implementation:** this
convention is new. Write it up as **ADR 0010** or as an addendum to ADR 0009
before the PR merges — whichever the solution-architect prefers — and say
plainly in the customer-facing note that their ADR 0009 reference did not
resolve to an existing spec. Do not let the code land with the convention
documented only in a docstring.

## Constraints

- ADR 0008: no sixth relationship-validity table; no fourth OEF exporter; one
  accessor per concept.
- No schema change for R2. If R1 genuinely needs a persisted OEF identifier,
  it must be a **nullable** column with no backfill requirement, tolerated
  when `NULL` (`reconcile-schema` is ADD-COLUMN-only). Prefer an in-request
  `id_map` over a new column if it suffices.
- `ArchiMateRelationship` in `app/models/archimate_core.py:110` does **not**
  carry `TenantMixin`. Check the normal-runtime mapping in
  `app/models/models.py` before writing — if it is genuinely untenanted, say
  so explicitly in the PR and do not create cross-org edges.
- Never invent data: an element with no properties renders `—`, not `{}` or a
  blank. A relationship whose source or target did not import is **failed with
  a reason**, never silently dropped.
- SQLAlchemy 2.0: wrap raw SQL in `db.text(...)`.
- No `console.log`; user notifications via `Platform.toast`.

## Deliverable

1. **`execute_import` writes relationships**, in a second pass after elements,
   resolving `source`/`target` OEF identifiers against an id map built during
   the element pass (including identifiers of elements that already existed
   and were skipped/updated — otherwise every relationship touching a
   pre-existing element fails).
2. Each candidate relationship is validated with `RelationshipValidator`
   before insert; a rejection carries the validator's own message and
   `suggestions`.
3. **Response gains `relationships_created`, `relationships_skipped`,
   `relationships_failed`**, where `relationships_failed` is a list of
   `{identifier, type, source, target, reason}` with a human-readable reason —
   never a raw exception string.
4. `preview_import` classifies relationships with the same validator and the
   same counts, so **preview and execute agree**.
5. `parse_oef_xml` reads `<propertyDefinitions>` from the model root and
   `<properties>/<property propertyDefinitionRef=…><value>` on each element,
   returning a `properties` dict per element.
6. `execute_import` (and `update_existing`) persists that dict to
   `custom_properties` per the convention above.
7. The element detail view renders all properties as label/value rows.
   Find the existing element-detail surface first (`architecture_crud.view_element`
   at `architecture_crud_routes.py:184` and the detail drawer in
   `app/templates/architecture/elements.html` around line 455) and **extend
   it** — do not add a new detail page.
8. OEF export writes `<propertyDefinitions>` + per-element `<properties>`, and
   a whole-model export path exists so the round-trip criterion is reachable.
9. ADR 0010 (or an ADR 0009 addendum) recording the property convention.
10. `tests/fixtures/oef/archiet_shaped.xml` — the synthetic fixture described
    in the plan, created by this task and reused by 02-04.

## Acceptance criteria

Verbatim from the customer's brief:

- **R1**: import the Archiet OEF file → `GET /archimate/api/relationships`
  total == 121; catalog banner no longer says "No relationships: 168";
  preview and execute counts match.
- **R2**: open `M-CON-10G-FREE-PILOTS` → properties show `status=RULED`,
  `source="founder ruling 2026-07-19 — strategy/10G-ASSESSMENT-OFFER.md …"`,
  `layer=Motivation`; export → re-import reports 168 "exists", 0 "new", 0
  "conflict".

Against the synthetic fixture the equivalents are: relationship total equals
the fixture's valid-relationship count with the invalid ones reported in
`relationships_failed` with reasons; the banner at
`app/templates/architecture/elements.html:88` ("No relationships: …") reads 0;
the fixture's `M-CON-10G-FREE-PILOTS`-shaped element shows its three
properties; and export → re-import reports every element as `exists`, 0 `new`,
0 `conflict`.

Additionally:

- `python scripts/verify.py` (bare, not `--tag static`) is green.
- A Playwright test in `tests/smoke/` uploads the fixture through the real
  UI control, runs preview then execute, **reloads**, and asserts both the
  relationship count and the properties persisted.
- The disposition of the three superseded relationship vocabularies is stated
  in the PR and at each code site.

## Handoff target

`refuter` — review focus: that no sixth validity table or fourth exporter was
added; that the id map covers pre-existing elements; that `relationships_failed`
reasons are human-readable and no raw exception string reaches the client; and
that the property convention was written up rather than left in a docstring.
