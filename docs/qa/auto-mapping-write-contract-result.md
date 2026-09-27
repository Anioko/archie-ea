# F500-090: synchronous auto-mapping write contract — red evidence

Regression-only stage; production code is deliberately unchanged.

**Correction: the initial seven failures demonstrated control flow and in-memory double effects, not successful database mapping writes.** The first model doubles accepted obsolete field names. Real SQLAlchemy expression construction subsequently rejected both active mapping queries: `UnifiedApplicationCapabilityMapping` has no `application_id`, and `ProcessApplicationMapping` has no `process_id`. The harness now validates queries against actual models. No PostgreSQL persistence claim follows from the initial run.

## Executed boundary

`tests/test_auto_mapping_write_contract.py` compiles the exact current `comprehensive_auto_map` handler from `app/modules/applications/routes/auto_mapping_routes.py` and the actual `bulk_ai_analyze` / `create_ai_mappings` methods from **`app/services/ai_import_service.py`**, which that handler imports. It does not substitute the similarly named module copy.

Provider analysis, source-query storage and commit/rollback effects are explicit in-memory test doubles. Source selection implements the selected filter, ordering and limit behavior; mapping queries now construct actual SQLAlchemy expressions against the actual models before using in-memory storage, and mapping construction delegates to the real model. The real writer decides which fields and categories to submit and when to commit. Flask supplies real request JSON and response serialization. Login/audit/rate decorators, application initialization, tenant middleware, SQL constraints, vendor inference and live provider calls are outside the executed unit boundary.

The counter regression now supplies a proposals-only analysis result and an explicit persistence receipt double (1 capability, 2 processes, 0 elements). It measures the real handler's aggregation arithmetic without claiming those rows were created by the currently broken ORM writer.

No external AI calls, production connections, persistent database changes, UI edits, generated asset edits, commits or deployments were made.

## Initial red evidence — permissive model doubles, superseded for persistence claims

Initial command:

`python -m pytest tests/test_auto_mapping_write_contract.py -q --override-ini addopts=''`

Result before adding the PostgreSQL counterpart: **7 failed, 2 passed in 4.00s**, no fixture errors.

Repeat excluding the subsequently added PostgreSQL counterpart:

`python -m pytest tests/test_auto_mapping_write_contract.py -q --override-ini addopts='' -k 'not postgresql'`

Result: **7 failed, 2 passed, 1 deselected in 7.85s**.

| Contract | Actual failure |
|---|---|
| `auto_create:false` preview performs no writes | Three rows entered the in-memory double's committed collection; this is not PostgreSQL persistence |
| Explicit `preview_mode:true` suppresses writes even with auto-create requested | The same three in-memory double rows remain |
| `application_ids:[10]` selects the older just-updated import | Returned application IDs are `[99]`, the unrelated newer eligible application |
| `map_capabilities:false` | One capability mapping reaches the permissive in-memory double |
| `map_processes:false` | One process mapping reaches the permissive in-memory double |
| `generate_archimate:false` | One element reaches the in-memory ArchiMate persistence double |
| Separate creation counters reflect persistence receipts | Response reports **3/3/3**, from a double-assisted **1 capability / 2 processes / 0 elements** result |

The original two passing controls were double-assisted writer creation of **1 capability / 2 processes / 1 element**, and an empty candidate set producing no write attempts or commits. The first is superseded by a real-model vocabulary regression and must not freeze internal commit ownership as intended behavior.

Revised controls assert that preview never reaches the writer and that disabled categories never reach the write stage. These remain meaningful when the current model vocabulary blocks actual mapping insertion. Real-model constructor success has not yet been qualified: an isolated constructor probe encountered an unrelated unresolved `ARBReviewItem` mapper dependency. The two invalid query expressions were demonstrated before that dependency error, without a database connection.

## PostgreSQL counterpart

`test_postgresql_explicit_scope_uses_imported_ids` uses the repository's shared `db_session`, `make_org` and `tenant_ctx` fixtures. It creates only synthetic source rows inside the outer rollback transaction. Source selection uses the real `ApplicationComponent` ORM query and the real tenant context, with a newer foreign-tenant row as a control. It passes request JSON to the actual handler without switching into the unit fixture's separate Flask app.

Provider suggestions remain deterministic and below the requested confidence threshold; this counterpart tests query selection, not PostgreSQL mapping insertion. It requires an explicit disposable `TEST_DATABASE_URL`. It is collect-only locally; neither a skip nor collection is a persistence/tenant verification pass.

## Candidate implementation boundary

1. Hand off committed, deduplicated created/updated IDs (or resolve them from an authorized import-history ID), not the imported row count. Empty scope must not fall back to 100 candidates.
2. Validate the complete requested application set in the active tenant before invoking analysis. Do not replace it with newest records or exclude selected imports merely because imported_capabilities is NULL.
3. Make preview genuinely non-mutating, including currently reachable vendor-product helper writes. Apply category options before both generation and persistence. Treat unsupported clone/layer options explicitly rather than accepting and ignoring them.
4. Give one layer transaction ownership; nested helper commits and whole-session rollbacks cannot support the route's existing all-or-nothing claim. Count only committed per-category results and report per-application partial failures truthfully.
5. Apply equivalent fresh application/capability/process validation to the accept endpoint. That security boundary remains a source finding: these tests do not prove cross-tenant exploitation.

The active analysis path's attempted confidence-review insertion has a mismatched helper signature and is caught before insertion; do not include review rows among runtime effects demonstrated here. These tests also do not qualify generated ArchiMate linkage, real vendor cloning or provider error behavior. Those remain implementation/verification boundaries, not inferred passing behavior.

Focused correctness lint passed. Final collection and diff-check results are recorded in the handoff. Parent owns the ledger and any production repair authorization. The deliberately red tests must not be described as a completed fix or merged as a green release.
No automatic PostgreSQL skip is installed; local commands explicitly deselect this case. Qualification must run it against the shared PostgreSQL fixtures.
