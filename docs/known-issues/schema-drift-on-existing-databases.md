# BUG: Existing databases drift from the ORM models and 500 (no column migrations on boot)

- **Severity:** High (user-facing 500s on core persona pages)
- **Type:** Schema / migrations / ops
- **Status:** Fixed (mitigated) — `flask reconcile-schema` added and wired into
  container boot (2026-07-16). Adopting Alembic autogenerate remains the ideal
  long-term direction (see options below).
- **Found by:** SQA live persona verification (2026-07-16)
- **Affects:** Any long-lived Archie database created from an older model version
  and upgraded in place. A **fresh** `docker compose up` / `flask --app manage
  init-db` install is **not** affected.

## Summary

Archie builds and updates its schema with SQLAlchemy `create_all()` (invoked by
`flask --app manage init-db`). `create_all()` creates **missing tables** but
**never adds columns to tables that already exist**. When a model gains a new
column in a later release, existing databases silently drift: the ORM `SELECT`
lists a column the physical table doesn't have, Postgres raises
`UndefinedColumn`, and the request returns **HTTP 500**. Because the first failed
statement aborts the transaction, later queries in the same request then fail
with `InFailedSqlTransaction`, so one missing column can take down a whole page.

There is no `flask db upgrade` step or column-reconcile on startup, so the drift
is invisible until a user hits an affected page.

## Impact (observed live)

Against a real seeded database (920 applications) that predated recent model
changes, two core persona pages returned 500:

| Route | Persona | Error |
|---|---|---|
| `/dashboard/overview` | Enterprise Architect (landing page) | Query failure left `persona_metrics` partial → Jinja `UndefinedError: 'dict object' has no attribute 'cfo'` at `templates/dashboards/overview.html:531` |
| `/arb/reviews` | Solution Architect (ARB governance) | `psycopg2.errors.UndefinedColumn: column arb_review_items.jira_issue_key does not exist` |

`/solutions/` did not 500 (it has a try/except fallback) but silently served a
**degraded** page — 177 KB fallback vs 371 KB once the schema matched
(`column solutions.ux_preferences does not exist`).

A reconcile pass found **47 drifted columns across ~20 tables** in that database,
including:

```
solutions.ux_preferences, solutions.initiative_id
arb_review_items.jira_issue_key, arb_review_items.servicenow_change_id
archimate_elements.acm_domain / acm_source / overlay_code / plateau / building_block_type (+2)
archimate_relationships.access_mode / flow_label / custom_label / connection_spec / created_by_id / updated_at
strategic_initiatives.initiative_type / target_platform / vendor_key / clean_core_target
codegen_generations.genome / genome_quality_score
ai_suggestions.architect_verdict / verdict_note / verdict_at
architecture_review_boards.organization_id, vendor_contracts.organization_id,
work_packages.organization_id, application_documents.organization_id, ... (several *.organization_id)
```

All 47 are declared in the current models — i.e. a fresh `create_all` install
would have them; only pre-existing databases lack them.

Separately (same class, surfaced during setup): the seeded DB was missing the
`soc2_audit_log` **table** entirely, which made an after-insert audit
event-listener fail and blocked **all user inserts** (e.g. `create_admin.py`
appeared to succeed but the row never committed). `init-db` created the table
and unblocked it — but this is the same "schema behind code" root cause.

## Root cause

`create_all()` is DDL-additive at the **table** granularity only. It has no
concept of `ALTER TABLE ... ADD COLUMN`. New columns added to existing models
between releases never reach an already-provisioned database, and nothing at
boot detects or repairs the gap.

## Steps to reproduce

1. Provision a database from an older Archie revision (`init-db`), add data.
2. Check out a newer revision that added columns to existing models.
3. Run `init-db` again (no error — it only ensures tables).
4. Log in and open `/arb/reviews` (or `/dashboard/overview`) → **500**.

## Fix (implemented)

A supported command now reconciles a drifted DB — **ADD COLUMN only, all
nullable, never drop/retype**, using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
so it is safe and idempotent:

```
flask --app manage reconcile-schema            # apply
flask --app manage reconcile-schema --dry-run  # report drift only
```

It diffs every mapped model's columns against the live table
(`sqlalchemy.inspect(engine).get_columns`) and adds any the model declares but
the table lacks. Implemented in `app/commands/reconcile_schema.py`, registered in
`app/_bootstrap/cli.py`. Running it resolved all 47 columns and turned every
persona route green; re-running is a no-op.

It is now wired into container boot in `docker-compose.yml`:

```
flask --app manage init-db && flask --app manage reconcile-schema && gunicorn ...
```

so `init-db` creates missing tables and `reconcile-schema` adds missing columns
on every start — existing deployments self-heal.

This supersedes the earlier piecemeal one-column patches
(`add_vendor_seed_column`, `add_integration_flow_columns`), which added specific
columns by hand; new column drift no longer needs a bespoke command each time.

## Longer-term direction

1. **Adopt Alembic autogenerate migrations** as the source of truth and run
   `flask db upgrade` on deploy. The repo already has a `migrations/` directory
   and Flask-Migrate; making column additions reliably captured/applied there is
   the cleanest end state. `reconcile-schema` is the pragmatic bridge until then.
2. **Optional fail-loud check:** a startup diff that logs the exact drift list
   (rather than relying on later requests to surface it) would make any residual
   gap obvious in the boot log.

## Hardening follow-ups (independent of the migration decision)

- **`/dashboard/overview` template robustness — DONE.**
  `templates/dashboards/overview.html` now sets a local
  `cfo = (persona_metrics or {}).get('cfo') or {}` and reads it with `.get(...)`,
  so a partial/missing `persona_metrics` degrades to an empty TCO table instead
  of raising `UndefinedError` and 500-ing the whole EA landing page. Verified
  against missing-key, None, and no-variable inputs.
- **Transaction hygiene:** a single `UndefinedColumn` aborts the request
  transaction and cascades into `InFailedSqlTransaction` for every later query
  on the page. Consider per-widget query isolation / savepoints on dashboard
  aggregations so one drifted column doesn't blank an entire page.

## Verification

After reconciling the 47 columns, all 15 persona-critical routes returned
HTTP 200 live (authenticated, real data): Enterprise Architect 5/5, Solution
Architect 4/4, Technology/Technical Architect 3/3, Data Architect 3/3.
