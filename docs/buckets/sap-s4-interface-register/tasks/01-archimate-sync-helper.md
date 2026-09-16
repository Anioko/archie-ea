# Task 01 — Backbone element helper, and the interface-count store-agreement correction

## Objective

Give the ArchiMate backbone module an **element-first** entry point so an
`ApplicationInterface` element can be created before the row that references
it, and make the platform answer "how many application interfaces exist" from
one place. No new module, no new helper file.

## Context

Extends **`app/services/archimate_backbone.py`** — the single sanctioned
element-creation implementation (ADR 0008; its own docstring, lines 11–35,
records that it exists because three rival `_sync_archimate_element` helpers
previously did). Do not create a new sync helper anywhere; see
`implementation-plan.md` §1 for the full arbitration.

Two mechanical facts you are fixing:

- `ELEMENT_TYPES` (`archimate_backbone.py:45-59`) has no interface entry, so
  `sync_archimate_element` hits `if mapping is None: return None` (line 113) and
  silently does nothing.
- `sync_archimate_element` assigns `obj.archimate_element_id` *after* creating
  the element (line 153). `ApplicationInterfaceMetadata.archimate_element_id`
  (`app/models/integration_metadata.py`) is `nullable=False, unique=True`, so
  the element must exist first.

Separately: `app/modules/architecture/routes/architecture_routes.py:578`
answers `interface_count` from `SELECT COUNT(*) FROM application_interfaces`,
while this feature will produce interfaces as `ArchiMateElement` rows. Left
alone, the dashboard and the register disagree from day one.

## Constraints

- `sync_archimate_element`'s signature, idempotency and raising behaviour are
  **unchanged**. Fourteen call sites import it; none may be edited.
- Do **not** write to `ApplicationInterface` (`app/models/application_layer.py:42`)
  and do **not** rely on its `before_insert` listener
  (`create_interface_archimate_element`, line 618) — it uses a raw core
  `connection.execute(insert(...))` that skips `scope`, `custom_properties` and
  the ORM tenant hooks.
- `flush()`, never `commit()` — the helper participates in the caller's
  transaction.
- Do not add a column anywhere. No schema change in this task.

## Deliverable

1. **`app/services/archimate_backbone.py`**
   - New public function:
     ```python
     def create_backbone_element(
         *, element_type, layer, name, description=None,
         organization_id, session=None, provenance=None,
     ) -> "ArchiMateElement":
     ```
     Body is the existing lines 136–154 logic, minus the `obj` assignment:
     `MAX_NAME` truncation with the `…` suffix,
     `provenance["source_name"]` when truncated,
     `provenance.setdefault("source_model", ...)`, `scope="enterprise"`,
     `session.add`, `session.flush()`, return the element. Raise `ValueError`
     on a blank `name` or a missing `organization_id`, with the same message
     shape as lines 121–134. Never return `None`.
   - `sync_archimate_element` refactored to call `create_backbone_element` and
     then set `obj.archimate_element_id = element.id`. Same return value, same
     `None` for unmapped types, same raises.
   - `ELEMENT_TYPES` gains
     `"ApplicationInterfaceMetadata": ("ApplicationInterface", "Application")`.
2. **`app/modules/architecture/routes/architecture_routes.py`** — replace the
   `interface_count` raw-SQL count at line 578 with an ORM count over
   `ArchiMateElement` filtered to `type == "ApplicationInterface"`. No
   `organization_id` predicate (`ArchiMateElement` is `TenantMixin`; the filter
   is injected). Keep the existing `except` branch passing
   `interface_count=None` — do not substitute `0`.
3. **`docs/buckets/sap-s4-interface-register/srs.md`** — correct §0 bullet 1 and
   Assumption A3 in place: an `ApplicationInterface` ORM class does exist at
   `app/models/application_layer.py:42`; this feature deliberately does not
   write it, per `implementation-plan.md` §1.2. Stories unchanged.
4. **`docs/adr/0008-one-system-of-record.md`** — append a short note recording
   `application_interfaces` as a partially-superseded store: the canonical
   answer to "what interfaces exist" is now
   `ArchiMateElement(type='ApplicationInterface')`; `retired_into_id` wiring and
   any row migration are deferred to their own bucket.
5. **`tests/test_archimate_backbone_sync.py`** — extend (do not fork):
   - `create_backbone_element` returns a flushed element with an `id`, correct
     `type`/`layer`/`scope`/`organization_id`, and `source_model` provenance.
   - a >100-char name is truncated and the full value lands in
     `custom_properties["source_name"]`.
   - a blank name raises `ValueError`; a missing `organization_id` raises.
   - `sync_archimate_element` still behaves identically for an existing mapped
     type (e.g. `WorkPackage`) — the refactor is non-breaking.
   - `ELEMENT_TYPES["ApplicationInterfaceMetadata"]` resolves, i.e. the silent
     `None` path is closed.

## Acceptance Criteria

- `python scripts/verify.py` (bare, not `--tag static`) is green.
- `pytest tests/test_archimate_backbone_sync.py tests/test_backbone_insert_ownership.py -q` passes.
- No new file under `app/services/` and no function named
  `_sync_interface_archimate_element` anywhere in the tree
  (`grep -rn "_sync_interface_archimate_element" app/` returns nothing).
- The software-architecture dashboard still renders and its Interfaces card
  shows a number ≥ the previous `application_interfaces` count for the same
  org, or `—` on error. Verify by loading the page, not by reading source.
- No new `tenancy-ok` / `fabricated-ok` / `raw-sql-tenancy` escape hatch.

## Handoff target

`builder` → Task 02.
