# Framework catalog investigation

Date: 2026-09-05. Read-only source investigation; no database or browser run.

## Finding and recommended decision

An empty active ElementTemplate catalog is a representable, expected fresh-install
state in this checkout. There is no evidence that a specific built-in framework
catalog is mandatory, or that a repository-owned ElementTemplate seed command is
available. The legacy dashboard endpoint classifies this valid empty collection
as service unavailability, unlike the newer application endpoint reading the same
table. The smallest supported fix is to align the legacy collection response with
the newer endpoint: successful query returns its actual array, including `[]`;
database failure remains an error. This changes an incorrect empty-state contract,
not the adversarial gate, and requires no invented catalog rows.

## Source evidence

| Evidence | Implication |
| --- | --- |
| `app/models/element_templates.py:30` defines ElementTemplate on `element_templates`; `framework` is an ordinary string and `is_custom` explicitly supports custom templates. | This is a data-driven catalog, not an enum of guaranteed installed standards. |
| `app/models/element_templates.py:146` queries distinct active framework values, orders them, and returns a list. | Both zero total rows and all-inactive rows legitimately yield an empty list. |
| `app/application_mgmt/template_api_routes.py:90` calls that query; lines 102–110 convert an empty list into 503 with “Please seed framework data.” | The 503 represents an empty result, not a failed query. The remedy text has no matching seed implementation in this checkout. |
| `app/modules/applications/routes/rationalization_api_routes.py:651` queries the same active distinct framework values and directly returns the JSON array, including an empty array; its exception path returns 500. | There is already a repository-owned contract separating empty results from backend failure. |
| `tests/smoke/conftest.py:217` creates its organization/users and journey entities through the ORM; it does not seed ElementTemplate. | A clean candidate smoke database is expected to lack this catalog. |
| `README.md:84` fresh-install instructions use `init-db` and admin creation, without a framework catalog seed step. `manage.py:382` seeds requirement templates, which are a different model. | The documented fresh-install path does not promise this catalog's contents. |
| `tests/test_availability_response_contracts.py:282` onward replaces `ElementTemplate.get_frameworks` for empty, populated and exception cases. | Existing tests characterize the current 503 branch with doubles; they do not prove that branch is the right product contract or exercise the database. |

The model does not inherit TenantMixin or contain organization_id. Its framework
catalog is shared reference data. Test rows must therefore be controlled and
isolated; adding tenant filters to this model would not be a narrow fix.

## Exact seed-path search result

No ElementTemplate insertion/seed implementation was found in the tracked Python,
SQL, or documentation search for `ElementTemplate` / `element_templates`, or in
the seed command registration and orchestration paths examined. The model,
consumers, migrations, and template-usage creation paths do not establish an
ElementTemplate catalog population path. Do not prescribe a nonexistent
`seed-frameworks` command.

Related real paths target other data and cannot populate this endpoint:

- `app/commands/seed_commands.py` exposes `flask seed all`, backed by
  `app/services/unified_seed_orchestrator.py:32`. Its four registered seeders are
  vendor organizations, business capabilities, technical capabilities and vendor
  products. ElementTemplate is absent.
- `app/commands/seed_vendor_archimate_templates.py:79` exposes
  `seed-vendor-templates`, writing VendorArchiMateTemplate, not ElementTemplate.
- `app/seed/industry_apqc_seed.py:7` writes IndustryAPQCFramework and
  IndustryAPQCProcess sample rows and begins by deleting their existing contents.
  It is neither the correct table nor a safe substitute for a missing catalog.
- `app/seeds/apqc_process_hierarchy_seed.py` writes ApqcProcessHierarchy,
  likewise a different model.

No exact shipped frontend caller of either `/dashboard/api/templates/frameworks`
or the newer framework collection was found in the template/JavaScript searches.
Other ArchiMate and code-generation template browsers use different endpoints.
A report claiming that the ElementTemplate picker rendered successfully needs
an identified actual page and observed browser evidence; it cannot be inferred
from these similarly named features.

## Local licensing evidence and limits

`README.md:146`, `LICENSE`, and `COMMERCIAL-LICENSE.md` describe Archie's AGPL-3.0
and commercial licensing. `docs/adr/0006-dependency-licensing.md` addresses software
dependencies, not redistribution of framework catalog content. ElementTemplate's
docstring names PCF, ITIL, COBIT, APQC and TOGAF as examples. The examined local
docs/seed files contain no framework-specific content redistribution grant or
approved ElementTemplate content manifest.

Those examples and the presence of separate APQC seed data are not evidence that
a full standards catalog may be copied into this table. No commercial/licensing
decision is needed for the empty-list contract fix. If a production built-in
catalog is later requested, its content provenance, version, supported scope and
redistribution permissions must be established separately; this investigation
does not determine third-party legal rights.

## Smallest useful verification plan

1. Add real PostgreSQL tests using the shared `app`, `db_session`, `make_org` and
   `tenant_ctx` fixtures where needed. Exercise authenticated requests against
   both registered framework endpoints, not a replacement of `get_frameworks`.
   In the isolated candidate database establish the zero-active-row state and
   require 200 with exactly `[]` for both. Also test inactive-only data.
2. Insert clearly synthetic, custom test templates through the ORM in the
   transaction: explicit test framework names, valid ArchiMate type/layer, two
   active rows sharing one framework, another active framework and an inactive
   framework. Assert the real response is sorted, distinct, and excludes inactive
   values. Roll back after the test. These are test fixtures, never production
   built-ins and never presented as APQC/ITIL/COBIT content.
3. Retain a targeted injected database-exception test to prove backend failure
   remains 500 rather than becoming `[]`; keep authentication coverage enabled.
   Update the older availability characterization that currently demands 503
   for an empty list. Keep the adversarial status checks and baselines intact.
4. In a real browser against the explicitly isolated smoke PostgreSQL database,
   sign in normally and use same-origin browser fetch to both endpoints. Check
   HTTP status and actual JSON first with no active rows, then with synthetic
   committed fixtures visible to the separate server process, then clean up only
   those fixture rows in `finally`. Record this honestly as browser/authenticated
   HTTP coverage, not picker coverage. If a real consuming picker is identified,
   additionally exercise empty-state messaging, loaded options and backend-error
   display on that actual page; do not build or invent a picker merely for this
   regression.
5. Run the unchanged adversarial probe after the fix. It should no longer report
   the successful empty collection as 503. A synthetic populated-catalog smoke
   run alone would hide the fresh-install defect and is insufficient.

No source, tests, configuration, baseline or data changed during this
investigation. Only this findings document was written. The proposed behavior and
verification remain unimplemented here; no runtime success is claimed.
