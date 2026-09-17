# Task 03 — Preview validation + partial commit (R4)

Handoff target: `builder` → `refuter`
Branch: `fix/archiet-dogfood-import` · separate PR

## Objective

Make an import that contains a few invalid elements import the valid ones and
report the rest by name with a human-readable reason and a suggested fix —
instead of rolling back all 168 and returning a raw database exception string.

**Scope note: this task implements (a) and (b) only. (c), the name-length
product decision, is escalated and is NOT decided here.** See "Open question".

## Context

`execute_import` (`app/services/archimate_import_service.py:322`) adds every
element to the session inside a per-element `try` (line 361) — but the `try`
only catches Python-level errors. A `String(100)` overflow, a constraint
violation or any other DB error is not raised at `db.session.add()`; it is
raised at the single `db.session.commit()` on line 404. That handler (lines
405-413) rolls back the whole batch and returns:

```python
return {"created": 0, "updated": 0, "skipped": 0,
        "errors": [f"Database commit failed: {exc}"]}
```

So one over-long name discards 167 good elements, and the user is shown a raw
psycopg exception. The per-element `except` at line 396 is effectively dead
for DB errors — do not assume it is doing anything.

`ArchiMateElement.name` is `db.String(100), nullable=False`
(`app/models/archimate_core.py:58`); `type` is `String(50)`, `layer` is
`String(30)`. Those are the constraints `execute` actually applies and
`preview` reports none of them — `preview_import` (line 250) classifies only
new/exists/conflict and never measures a field against its column limit.

The route already returns 207 when errors are present
(`app/modules/solutions_strategic/v2/routes/solution_import_routes.py:107`),
so the status-code half of R4b exists; what is missing is that `errors` is
currently all-or-nothing and unstructured. Extend that route's contract, do
not add a second import endpoint.

Task 01 makes `RelationshipValidator` authoritative and it returns
`suggestions` — reuse that field verbatim for the relationship half of the
"suggested fix" column rather than composing new advice text.

## Constraints

- ADR 0008: extend `preview_import` / `execute_import` and the existing
  `/solutions/import/archimate/*` routes. No parallel "validated import"
  service, no second endpoint.
- **Derive the limits from the model, do not hardcode them.** Read
  `ArchiMateElement.__table__.columns['name'].type.length` (and the same for
  `type`, `layer`) so the preview message stays correct automatically whichever
  way the open question below is decided. A hardcoded `100` becomes a lie the
  moment the column is widened.
- Never return a raw exception string to the client. Log the exception; return
  a composed, human-readable reason.
- Never invent data: an element that failed is reported as failed — it must
  not be counted in `created`, and it must not be silently omitted.
- SQLAlchemy savepoints: `db.session.begin_nested()` per element, with the
  outer `db.session.commit()` after the loop. A failed savepoint must be
  rolled back before the next element or the whole transaction stays in a
  failed state (`InFailedSqlTransaction` cascades — see
  `docs/known-issues/schema-drift-on-existing-databases.md` for that exact
  failure mode).
- Per-element savepoints on a 168-element file are ~168 extra round trips.
  Measure it on the fixture; if it is materially slow, batch optimistically
  and fall back to per-element savepoints only for the failing batch — but do
  not trade correctness for it.

## Deliverable

### (a) Preview reports every constraint execute will apply

1. `preview_import` gains a per-element `violations` list:
   `[{field, limit, actual, message, suggested_fix}]`, populated by checking
   each element against the real column limits and against `nullable=False`.
2. `suggested_fix` is concrete — e.g. for a 138-character name, the truncated
   100-character form the user would get, not "shorten the name".
3. The summary gains a count of elements that **will fail** if executed, so
   the preview answers "what happens if I press import" before it is pressed.
4. `app/templates/solutions/partials/_import_preview.html` renders the
   violations per element and the will-fail count. (Task 04 is what makes this
   panel reachable; this task may need to preview it via the existing
   `/solutions/import/archimate/preview` endpoint until then.)

### (b) Execute commits what is valid

5. `execute_import` wraps each element in `db.session.begin_nested()`, so one
   bad row rolls back only itself.
6. The response gains `failed`: a list of
   `{identifier, name, type, reason, suggested_fix}`. `created`/`updated`/
   `skipped` count only what actually persisted.
7. The route returns **207** when `failed` is non-empty and 200 when it is
   empty, and never surfaces a raw DB exception.
8. The same treatment applies to the relationship pass added in task 01 —
   a failed relationship does not discard the successful ones.

### (c) NOT in this task — see below.

## Open question — ESCALATED, not decided here

**Should `ArchiMateElement.name` be widened from `String(100)` to
`String(255)`?**

This is a founder/product call, not an engineering one, and this task brief
does not decide it. It is a question about what Archie promises a customer
about their own naming conventions — the customer's real model contains
element names longer than 100 characters, and the choice is between accepting
their names as they are and requiring them to rename their model to fit ours.
There is no technically-correct answer; both are implementable.

**Timing recommendation (tech-lead): ship (a) and (b) now, surface (c) as a
follow-up decision.** Rationale:

- (a) and (b) are correct at *either* length. They change how a violation is
  reported, not what the limit is. Nothing about them has to be redone if the
  column is later widened — the limits are read from the model, per the
  constraint above.
- Shipping them first makes the decision *cheaper and better informed*: once
  preview reports violations, the founder can see exactly which of Archiet's
  real elements the limit bites, named, with their actual lengths. Deciding
  the number first throws that evidence away.
- The customer's R4 acceptance criterion is satisfied by (a)+(b) alone — it
  asks that preview "lists long-name elements with the exact limit" and that
  execute "creates every valid element and returns 207 naming the rest". It
  does **not** ask for the limit to be raised.

If (c) is later decided as "widen": `String(100)` → `String(255)` is a type
change, and `reconcile-schema` is **ADD-COLUMN-only** — it will not retype an
existing column, so widening needs a real migration and a maintenance window
(see ADR 0002). That cost belongs in the decision and must be stated when the
question is put to the founder. Widening is not the free option it looks like.

**Builder: do not implement (c). Do not pick a number. If asked to decide,
escalate.** Record the question and the evidence (which fixture/real elements
violate, and by how much) in the PR description so the founder has what they
need to rule.

## Acceptance criteria

Verbatim from the customer's brief:

- **R4**: import the original (unfitted) Archiet file: preview lists long-name
  elements with the exact limit; execute creates every valid element and
  returns 207 naming the rest.

Against the synthetic fixture (which carries at least one >100-character name
per the plan): preview lists that element with the exact limit read from the
model; execute persists every other element and returns HTTP 207 whose body
names the failed element and gives a reason and suggested fix; and **no raw
exception string appears anywhere in the response**.

Additionally:

- A test asserts that after a partial import, the DB contains exactly the
  valid elements — not zero, and not all of them.
- A test asserts the response body contains no `psycopg`/`sqlalchemy` text.
- `python scripts/verify.py` (bare) green — note `error-signalling` and
  `silent-data` are directly relevant here and must stay at 0.
- Playwright: upload the fixture, press the real preview control, assert the
  violation is shown; press import; reload; assert the valid elements persisted
  and the failure is reported on screen.

## Handoff target

`refuter` — review focus: that the column limits are read from the model and
not hardcoded; that a failed savepoint is rolled back before the next element;
that `created` counts only what persisted; that no raw exception reaches the
client; and **that (c) was not quietly decided** — a `String(255)` in the diff
is a rejection.
