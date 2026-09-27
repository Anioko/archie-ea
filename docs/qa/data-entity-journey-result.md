# Data entity lifecycle qualification

Status: test implementation and local collection/static checks only. **The browser journey has not been executed.** No local database, production service, package installation, interception, or application modification was used for this task.

## Added scope

`tests/smoke/test_data_entity_lifecycle.py` adds three collected tests:

- One full-application lifecycle using the shared real login as `data_architect`, the smoke server, and the isolated test database when CI executes it.
- Two anonymous GET checks for the catalog and create form, requiring the login redirect. These assert the actual `@login_required` contract, not a conjectured permission restriction against other authenticated roles.

The lifecycle starts at `/architecture/data-entities` and clicks **Create Entity**. It fills the real form, selects the shared synthetic domain by its actual option value, and submits through **Create Entity**. The submitted form must carry a nonempty CSRF token and return the expected redirect; an independent authenticated read from `/architecture/api/data-entities` must find exactly the unique test entity with its saved classification/type/PII values.

The catalog's real **Search**, **Classification**, **Type**, and **Filter** controls exercise both an excluding classification (visible empty state) and a matching filter (exact row). The row's **Edit** link opens the exact created identity. **Save Changes**, reload, API readback, and reopening/reloading the form check that renamed and revised values persist.

The edit form's **Delete Entity** control must open the standard accessible **Confirm** dialog containing the exact entity name. **Cancel** must restore focus, submit no deletion, and preserve the entity in an independent read. Reopening and clicking **Confirm** must submit exactly one POST to that entity's delete endpoint, carry CSRF, redirect, and leave neither the row nor the API entity after reload. Uncaught page errors fail the lifecycle.

## Isolation and cleanup

The root-owned smoke fixture supplies `seeded['ids']['data_domain']`, a synthetic domain scoped to the smoke organization. Selecting it avoids the production handler's implicit creation of a `General` domain. No framework or business catalog data is invented for the product.

Each entity name contains a full random UUID. A `finally` block locates only the exact original/edited unique names, verifies the known identity when available, and deletes only that created row through its authenticated, CSRF-bearing form endpoint. Identity recovery also covers a creation that succeeded before the test observed its redirect. Cleanup does not replace the measured user-click deletion, does not retry a failed measured request, and asserts the exact entity is absent afterwards. The shared domain is not deleted by this test.

## Evidence and limits

Local commands on Windows:

- `python -m pytest tests/smoke/test_data_entity_lifecycle.py --collect-only -q`: **3 tests collected**, exit 0; fixtures and browser lifecycle not executed.
- `python -m ruff check --config ruff.toml tests/smoke/test_data_entity_lifecycle.py`: **All checks passed**, exit 0.
- `python -m py_compile tests/smoke/test_data_entity_lifecycle.py`: exit 0.
- Scoped `git diff --check`: exit 0.

Source inspection established the route/form contract from `app/modules/architecture/routes/data_architecture_routes.py`, `app/templates/data_architecture/entity_catalog.html`, `app/templates/data_architecture/entity_form.html`, and `app/static/js/ui/modal.js`. It is not executed browser evidence. The shared login and fixtures remain unchanged by this task.

Pending: execute all three tests against the isolated PostgreSQL smoke server in CI and inspect their results/artifacts. A skip is not acceptance. This does not qualify tenant-negative access, role-specific write restrictions, data lineage, imports, entity-to-ArchiMate synchronization, discoverability from the dashboard/sidebar, concurrent writes, or the entire data architecture product. The routes inspected explicitly enforce login; no stronger role policy was assumed. Root owns CI/no-skip acceptance and shared fixture integration.
