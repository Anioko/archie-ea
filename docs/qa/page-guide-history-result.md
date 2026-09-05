# Page Guide history policy split

## Implemented scope

- `app/modules/ai_chat/services/page_guide_service.py`: `is_enabled()` now
  describes administrator policy only. `AI_PAGE_GUIDE_ENABLED` must be enabled;
  an explicit falsy non-None `AI_CHAT_ENABLED` still disables the guide. Missing
  or None chat config is not treated as an administrator disable. Provider
  absence no longer hides the drawer or blocks saved records. The existing
  misplaced logger declaration was moved below imports to clear targeted E402
  lint in this owned file.
- `app/modules/ai_chat/routes/page_guide_routes.py`: `_feature_guard()` defaults
  to requiring a provider; only history GET and clear POST explicitly opt out.
  Message generation independently checks configured provider/model even when
  chat is explicitly enabled. Missing inference configuration returns a real
  structured 503 with `feature: chat`; no successful fallback is manufactured.
- `tests/test_availability_response_contracts.py`: the old history/provider
  coupling assertion is replaced by the intended no-provider validation path.
- `tests/test_page_guide_history_policy.py`: 24 no-database cases using real
  routes, guard logic, schema validation and Flask-Login, with disclosed
  persistence/inference/audit boundary doubles.
- `tests/test_page_guide_history_database.py`: two real-database cases using
  shared `app`, `db_session`, `make_org`, `client` and `login_as` fixtures. No
  module-owned app or cleanup convention bypasses the shared rollback boundary.

Authentication, registry validation, schemas, audit/rate-limit decorators,
per-user/session filters, real clear commit and generation code remain intact.
Global FeatureFlagService semantics and provider selection are untouched.
The UI inclusion follows the existing context processor/layout use of
`is_enabled()`; no template/JS change is required to expose saved history.
Actual browser behavior still needs the coordinator's database-enabled run.

## Red/green evidence

Before production changes:

- History/clear with chat None reached a forbidden provider resolver:
  **2 failed, 10 passed in 81.62s** (stopped at two failures).
- Generation matrix: **3 failed, 1 passed, 20 deselected in 44.66s**.
  Explicit true bypassed provider checks, and the automatic no-provider path
  misreported provider absence as guide policy disabled.

After the guard split:

`python -m pytest tests/test_page_guide_history_policy.py tests/test_availability_response_contracts.py -q --tb=short`

**37 passed, 6 existing import/deprecation warnings in 56.46s.** No provider
request or database connection is needed by these tests. In particular, the
history tests fail if provider resolution is attempted at all. Generation tests
exercise real guards with a deterministic resolver and an explicit inference
boundary double; passing them does not imply provider health or answer quality.

Targeted Ruff correctness lint (`F,E4,E7,E9`) and `git diff --check` pass.

## Database and release boundaries

Database tests are collection-only locally; PostgreSQL is unavailable. They
seed three real users across two organizations with identical page/scope keys,
other scopes/pages, and a foreign-user row with a deliberately colliding session
ID. Real authenticated reads must isolate each user; clearing exactly two owner
rows must leave every other seeded ID intact. Repeated clear must report zero,
and fresh reads must confirm both deletion and survivor contents. Commits run
inside the shared fixture's savepoint/outer-rollback boundary.

These pending tests are not reported as passes. They are required for actual
database persistence/user-isolation qualification; the model has no tenant
column and must not be described as implicitly organization-filtered.
No package installs, production/provider calls, credentials, external billing,
commits, deployments or full-suite run occurred. Existing AI model-note files
and the opt-in protocol suite were not edited in this assignment.
