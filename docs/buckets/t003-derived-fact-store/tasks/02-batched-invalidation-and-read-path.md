# T-003 / Task 02 — Batched invalidation, stale-never-current read path, OA-2 record (DE-3, FR-4)

Depends on task 01 (the table must exist). Read `00-verification-notes-and-sr1.md`.

## Objective
Mark affected derived rows stale in **one** batched `UPDATE` per flush, inside the
user's own flush so staleness commits or rolls back with the model write, and make
it structurally impossible for any read path to return a stale row without the
`"stale": true` / `"reason": "derivation_stale"` flag.

## Context
- **Extends existing components.** The listener is wired into the existing,
  already-called `register(app)` at `app/modules/intelligence/__init__.py:15` —
  reached from `app/_bootstrap/blueprints.py:174` → `_register_intelligence` at
  `:1334`, which imports and calls it in a log-and-continue try/except. That
  function's docstring already reserves itself as T-003's wiring point. Do not
  invent a second registration point for this module, and do not register the
  listener at model-import time.
- The reason string `"derivation_stale"` is already a member of the closed DE-14
  vocabulary at `app/modules/intelligence/services/reason_codes.py:20`. Emit it
  through `validate_reason_code()` (`:46`), not as an inline literal — that function
  exists precisely to stop an endpoint inventing an absence string.
- Watched models are the existing `ArchiMateElement` and `ArchiMateRelationship`
  (imported lazily, as `derivation_runner.py:69` does, to avoid pulling
  `app.models` in at module-import time).
- **`record_query_latency` does not exist anywhere in this repo** — verified by
  full-tree grep; the only mentions are in the T-003 brief. There is no existing
  OA-2 record to extend, so you are creating it. Do not go looking for it, and do
  not report it as "already present".
- Blueprints register non-fatally, so a failure in this listener's registration
  must degrade this one feature, not 500 the app.

## Constraints
- **`after_flush`, one batched statement per flush, never one per id** (DR-2,
  SEC-16). The predicate is a single `UPDATE` over the store using array predicates:
  `chain && :changed_relationship_ids::integer[] OR source_element_id =
  ANY(:changed_element_ids) OR target_element_id = ANY(:changed_element_ids)`,
  `AND organization_id = :org_id`, `AND stale = FALSE`.
- Do **not** move marking to an asynchronous queue, a Celery task, an
  `after_commit` hook or a background thread. Staleness must commit or roll back
  with the write (ADR-004). The SR-2 escalation to an in-request bounded queue
  applies only if measurement shows >100 ms p95 and is explicitly **not** this
  task's default — if you measure a breach, report the measurement, do not
  unilaterally re-architect.
- It is raw SQL inside a multi-model listener, so `organization_id` is written
  explicitly into the predicate — the ORM tenant listeners do not reach raw SQL.
- Inspect `session.new`, `session.dirty`, `session.deleted`. When no watched object
  is present, issue **no** statement at all — a flush touching nothing must cost
  nothing.
- `stale_reason` values are exactly `relationship_created`, `relationship_updated`,
  `relationship_deleted`, `element_deleted`. When one flush carries several causes,
  the statement stays single: use a `CASE` in the `SET`, not a second `UPDATE`.
- `stale_since` is set in the same `SET` (satisfying `ck_derived_stale`), and only
  rows with `stale = FALSE` are touched, so an already-stale row keeps its original
  `stale_since` and first cause.
- Reads apply `stale = FALSE` **by default**. The default must live in one accessor
  that every reader goes through, so "forgot the filter" is not reachable — not a
  filter each caller is trusted to remember. `include_stale=true` returns stale rows
  each carrying `"stale": true` and `"reason": "derivation_stale"`.
- No new store, dependency, route, template or query surface in this task (NFR-8).
- Guard against recursion: the listener's own `UPDATE` must not re-trigger marking.

## Deliverable
1. `app/modules/intelligence/services/invalidation.py` — the `after_flush` listener,
   the id-collection logic, and the single batched `UPDATE`; returning the number of
   rows it marked.
2. Wiring in `app/modules/intelligence/__init__.py::register(app)`, replacing the
   `return None` no-op, registered non-fatally.
3. A single read accessor over the store (co-located with the model's service, e.g.
   `app/modules/intelligence/services/derived_facts.py`) applying `stale = FALSE`
   by default and taking `include_stale`, returning the flag and the validated
   reason code on stale rows. This is the only permitted read path; task 03's
   endpoints go through it.
4. `app/modules/intelligence/services/observability.py` — the OA-2 structured
   record, **new**, carrying `invalidated_rows` (the count the batched statement
   marked) alongside the run/latency fields. State in the build report that no
   prior record existed and this is a new module, not an extension.
5. Tests under `app/modules/intelligence/tests/`, against the shared fixtures in
   `tests/conftest.py`.

## Acceptance Criteria
1. **(Brief item 4)** A flush touching N relationships and M elements (N, M > 1)
   issues **exactly one** `UPDATE` against the store. Assert by counting statements
   with a SQLAlchemy `before_cursor_execute` event or `sqlalchemy` echo capture —
   counting is the assertion, not a comment claiming it. The statement is scoped by
   `organization_id` and filtered `stale = FALSE`, and the marked count appears as
   `invalidated_rows` on the OA-2 record.
2. A flush touching no `ArchiMateElement`/`ArchiMateRelationship` issues **zero**
   statements against the store.
3. **(Brief item 5)** Same-transaction guarantee: a model write that is rolled back
   leaves **no** rows falsely stale — a test performs the write, asserts marking
   happened in-session, rolls back, and asserts the store is untouched.
4. **(Brief item 6, FR-4 stale-never-current, OA-6 item 3)** Mutate a relationship
   and re-query **in the same request**: the affected derived row is absent on the
   default read, and with `include_stale=true` is present, flagged `"stale": true`
   with `"reason": "derivation_stale"`. Separately assert no default-read path
   returns a stale row without the flag.
5. **(Brief item 13, mutation proof)** Disable the read accessor's `stale = FALSE`
   default, confirm the item-4 test goes **red**, re-enable, and record the test id
   and both outcomes in the build report. A test that stays green with the guard
   removed is not evidence.
6. **(Brief item 7)** `stale_reason` fidelity: a relationship create, a relationship
   update, a relationship delete and an element delete each stamp the corresponding
   value; a single flush carrying two causes still issues one statement.
7. An already-stale row is not re-marked: its `stale_since` and `stale_reason`
   retain the first cause.
8. Cross-tenant: a flush in tenant A marks no row belonging to tenant B.
9. `python scripts/verify.py` (bare) green, no ratchet raised, `error-signalling`
   and `silent-data` clean — a failed marking surfaces as an error, never as a
   quietly-unmarked store.

## Handoff Target
`builder`. Then task 03 (recompute job and the API surface), which consumes this
task's read accessor and OA-2 record. The refuter verifies parent-brief items 4, 5,
6, 7 and 13 here — item 13's mutation proof by re-running it, not by reading the
report.
