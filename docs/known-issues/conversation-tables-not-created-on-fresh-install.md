# Chat history is broken on a fresh install, and used to say so silently — fixed

**Found:** 2026-08-10, by a smoke test that only started failing once
`/ai-chat/threads` was made to answer failures with HTTP 500.
**Fixed:** 2026-08-10 — option 1 below. `app/models/conversation.py` declares both
tables, so `flask init-db` creates them and `flask reconcile-schema` maintains
them like every other table. Kept as the decision record; the "What happens"
section is written in the past tense it now deserves.

## What happened

`conversation_threads` and `conversation_messages` were created by exactly one
thing: `migrations/versions/add_conversation_tables.py`. There was **no model**
for either table — `app/services/conversation_history.py` reads and writes them
with raw SQL.

Deploys do not run `flask db upgrade` (see CLAUDE.md, "Schema management"), and
`create_all()` cannot create a table that no model declares, so neither
`flask init-db` nor `flask reconcile-schema` would ever produce them. A fresh
database therefore had no conversation tables at all, and every call to
`/ai-chat/threads` raised `UndefinedTable`.

Production has the tables — the migration was applied there at some point — so
the live site was unaffected. Any new environment was not.

## Why nobody noticed

The endpoint answered its own failure with success:

```python
except Exception:
    return jsonify({"success": True, "threads": []})   # HTTP 200
```

`{"threads": []}` at 200 is exactly what a user with no conversations gets, so
the rail rendered "no conversations yet" and nothing anywhere reported a
problem. The defect was invisible from the browser, invisible in the UI, and
invisible to every test — until the handler was changed to return 500 as part
of the `error-signalling` work, at which point four smoke tests failed
immediately.

That is the clearest evidence in this audit for why the gate exists: the bug
was not found by looking for it. It surfaced the moment the product stopped
claiming success it had not achieved.

## The fix

Two options were on the table, and choosing between them was a schema-management
decision rather than a defect fix:

1. **Declare models** for both tables so `create_all()` and `reconcile-schema`
   handle them like everything else. This matches how the rest of the codebase
   works and is the smaller change. `conversation_history.py` can keep its raw
   SQL; the models only need to exist for table creation.
2. **Adopt the ADR-0002 target state** — an Alembic baseline with `db upgrade`
   on deploy — which fixes this and the whole class of drift with it.

**Option 1 shipped.** `app/models/conversation.py` declares
`ConversationThreadRecord` and `ConversationMessageRecord`, imported from
`app/models/__init__.py`. `conversation_history.py` is untouched and still uses
raw SQL — the models exist so the tables get created, not to replace the service.
A fresh install now needs nothing but `flask init-db`.

Option 2 remains the right end state and is unaffected by this: it is tracked in
[ADR 0002](../adr/0002-schema-management.md).

### Three things the models had to get right

* **The DDL is the migration's, exactly.** Column names, types, lengths,
  nullability, both foreign keys and both indexes. `python scripts/verify.py
  --gate schema-drift` reports 0 against a database that already holds these
  tables, which is the check that matters: production has them *with data*, so a
  model that drifted would make `reconcile-schema` ALTER a populated table.
* **No `TenantMixin`.** Neither table has an `organization_id` column in
  production. The mixin would declare one — so `reconcile-schema` would try to add
  it to the live table — and would inject `WHERE organization_id = ...` into ORM
  reads of a column that does not exist. Tenancy here runs through `user_id`,
  which is what the service already filters on and what a user's single
  organisation membership makes sufficient.
* **`message_count` keeps its `DEFAULT 0`.** The migration writes `default=0`,
  which Alembic renders Python-side only, but the live tables carry a server-side
  `DEFAULT 0`. The model declares both, so `create_all()` on a fresh database
  reproduces the shape production actually has rather than the one the migration
  file would have produced.

Pinned by `tests/test_conversation_models.py`, which is database-free — it asserts
against `db.metadata`, so it fails on a model edit rather than waiting for a
deploy.

## Related

`docs/known-issues/schema-drift-on-existing-databases.md` covers the opposite
direction: columns present in an old database that the models no longer
declare. This is the same root cause seen from the other side — three
mechanisms for schema, none of them authoritative.
