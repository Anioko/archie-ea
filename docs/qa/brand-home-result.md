# Brand home destination repair

## Change and policy

The shared sidebar's brand link now targets `dashboard.overview` (`/dashboard/overview`), not `admin.index` (`/admin/`). Only that `href` changed in `app/templates/components/admin_sidebar.html`; admin navigation, permissions, labels, styles and other controls are untouched.

Source evidence: canonical `app/modules/dashboard/routes/dashboard_views.py:186–189` protects overview with `@login_required`, without an administrator gate; dashboard index also redirects there. `dashboards/overview.html` selects its initial lens from `enterprise_role`. Conversely, `app/modules/admin/routes/admin_routes.py:75` protects the admin index with `@admin_required`. The fix preserves this real authorization boundary rather than weakening it or assuming every `/admin/` URL has the same policy.

`DESIGN.md` was read fully. The standard shared sidebar remains the sole component; no layout or CSS classes changed, so no CSS rebuild is required for this href-only change. The test-driven-development skill governed the observed red/green sequence.

## Executed local red/green

`tests/test_brand_home_navigation.py` renders the **actual sidebar Jinja** using real Flask URL generation and `get_sidebar_zones`, then clicks the actual brand anchor in Chromium against a temporary loopback server.

Before the production edit, `python -m pytest tests/test_brand_home_navigation.py -q` produced **2 failures** for the intended reasons:

- Synthetic solution architect: brand navigation reached `/admin/`, HTTP **403**, rather than an accessible home.
- Synthetic platform administrator: brand navigation reached `/admin/`, HTTP 200, rather than the expected shared dashboard.

After the one-line edit, the same command produced **2 passed**. Both reached `/dashboard/overview`, HTTP 200, and the destination heading. The administrator retained the separate **Command Center** link to `/admin/`; the ordinary user's real role-zone rendering did not include it.

Boundary disclosure: this local harness uses synthetic users and small synthetic destination handlers. It does **not** boot the full application, exercise real authentication/authorization, query a database, load the full shell's CSS/Alpine, or qualify mobile drawer behavior. The live browser click is real; the destination authorization/content are not full-app evidence. The known role policies were established by source inspection and historical audit observations, not inferred from the harness.

## Full-application coverage added, not executed

`tests/smoke/test_brand_home_navigation.py` parametrizes all **11 shared ARCHETYPES**, including platform administrator, data architect and security architect. Each uses the shared real login and seeded account, the real overview and sidebar, and a normal brand click with no request interception. It requires the resulting navigation to return HTTP 200 at `/dashboard/overview` and show the actual Dashboard h1. The platform-admin case also checks that the real Command Center navigation remains available.

`python -m pytest tests/smoke/test_brand_home_navigation.py --collect-only -q`: **11 collected**, exit 0. No fixture, PostgreSQL server, or full-application browser journey was executed locally. These tests currently cover desktop; they do not qualify opening/closing the mobile drawer or collapsed navigation.

## Other local checks

- `python -m pytest tests/test_sidebar_budgets.py tests/test_sidebar_role_filtering.py -q`: **22 passed**.
- `python -m ruff check --config ruff.toml tests/test_brand_home_navigation.py tests/smoke/test_brand_home_navigation.py`: **All checks passed**.
- Bytecode compilation of both new test files: exit 0.
- Scoped `git diff --check`: exit 0; inspected template diff contains only the link destination change.

The executed pytest runs emit one existing `datetime.utcnow()` deprecation warning from `app/models/vendor/vendor_organization.py:1227`; no test was skipped. No packages were installed, no production was accessed, no persistent data changed, and no commit/deploy occurred. Root owns independent candidate verification, ledger status, CI and release acceptance. **This is a locally verified component repair, not full-candidate or production qualification.**
