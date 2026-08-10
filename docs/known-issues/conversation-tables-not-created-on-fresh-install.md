# Chat history is broken on a fresh install, and used to say so silently

**Found:** 2026-08-10, by a smoke test that only started failing once
`/ai-chat/threads` was made to answer failures with HTTP 500.

## What happens

`conversation_threads` and `conversation_messages` are created by exactly one
thing: `migrations/versions/add_conversation_tables.py`. There is **no model**
for either table — `app/services/conversation_history.py` reads and writes them
with raw SQL.

Deploys do not run `flask db upgrade` (see CLAUDE.md, "Schema management"), and
`create_all()` cannot create a table that no model declares, so neither
`flask init-db` nor `flask reconcile-schema` will ever produce them. A fresh
database therefore has no conversation tables at all, and every call to
`/ai-chat/threads` raises `UndefinedTable`.

Production has the tables — the migration was applied there at some point — so
the live site is unaffected. Any new environment is not.

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

## The fix, which is not done here

Two options, and choosing between them is a schema-management decision rather
than a defect fix:

1. **Declare models** for both tables so `create_all()` and `reconcile-schema`
   handle them like everything else. This matches how the rest of the codebase
   works and is the smaller change. `conversation_history.py` can keep its raw
   SQL; the models only need to exist for table creation.
2. **Adopt the ADR-0002 target state** — an Alembic baseline with `db upgrade`
   on deploy — which fixes this and the whole class of drift with it.

Until one of those lands, a new environment needs the migration applied by
hand. The DDL is in the migration file.

## Related

`docs/known-issues/schema-drift-on-existing-databases.md` covers the opposite
direction: columns present in an old database that the models no longer
declare. This is the same root cause seen from the other side — three
mechanisms for schema, none of them authoritative.
