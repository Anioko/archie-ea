# Import History filter investigation

Read-only production investigation, 2026-09-05. No production source, database,
import, export, retry or rollback operation was changed or invoked.

## Reproduction and limits

`python -m pytest tests/test_import_history_filters.py -q --tb=short`
finished **7 failed, 1 passed, 1 existing datetime deprecation warning in 34.89s**.
These are ordinary failing regressions, not skipped or expected-failure tests.
The new test file must not be mistaken for a green qualification gate.

Seven browser cases use Chromium, the actual `dashboard/import_history.html`,
its macros, shipped CSS/core/modal/Alpine/CSP-adapter assets and the **active**
`js/import_history.js`. A minimal parent layout supplies the page's Alpine
ancestor; this is not full-app authentication/navigation qualification. Native
fetch goes to a real loopback HTTP fixture with two deliberately distinct
January-completed and February-failed records, using the active API's field
names. Their enum fields are JSON strings to isolate the downstream renderer
from the separate API serialization failure. Filters are implemented only at
this disclosed fixture boundary, not in production. No functions or fetch
implementations are replaced. Apply, Refresh and filter inputs use normal
browser actions. No Firefox/WebKit or database-backed test was run here.

One Flask endpoint case executes the real authenticated route and normal JSON
serialization, with a query/persistence double containing the real model's
`BatchJobType` and `BatchJobStatus` enum values. It does not instantiate a fully
configured mapped row or execute PostgreSQL. The initial diagnostic attempt
to instantiate a mapped row encountered an unrelated unresolved mapper
registration; the final test explicitly uses a plain record double with real
enums instead. Initial browser teardown failures due to an omitted session
keepalive fixture were corrected with that exact endpoint. The final run has
no such teardown errors.

## Established failures

| Boundary | Evidence |
| --- | --- |
| Apply status | Selecting Failed and clicking Apply sends `{}` query parameters, not `status=failed`. |
| Apply dates | Each date input, tested separately, still sends `{}`. |
| Refresh | Selecting status plus both dates then clicking Refresh sends `{}` and retrieves the complete updated fixture set. Refresh is not a dead click: it reloads, but ignores the visible filters. |
| API/UI record contract | Both cards render, but real `job_name` values are absent, dates display `Invalid Date Invalid Date`, and counts are presented as zero despite nonzero item counts. |
| Loading state | While the initial HTTP response is held pending, the actual loading indicator is already hidden. |
| Endpoint JSON | Real route returns 500 and logs `Object of type BatchJobType is not JSON serializable`. The raw status enum is also incompatible with normal Flask JSON serialization. |
| Empty/error distinction | Passed: Refresh after an empty response shows the empty state and zero total; subsequent HTTP 500 shows error state, hides empty state and restores em-dash totals. |

## Exact source chain

- `app/modules/dashboard/routes/dashboard_pages_routes.py:249` renders this
  template. The parallel v2 route also names it.
- `app/templates/dashboard/import_history.html:209` starts an inline loader.
  Line 212 fetches `/api/import-history` without query parameters; it assigns
  `data.jobs` to the inline history array. `applyFilters` at line 564 explicitly
  reloads all data. `refreshHistory` at line 560 calls the same loader.
- The renderer around lines 259-323 reads `file_name`, `imported_by_name`,
  `imported_at`, `import_source`, `records_created`, `records_updated`, etc.
  Those are application-import audit fields, not batch-job item statistics.
- The template includes `app/static/js/import_history.js` at line 572. This
  second manager installs change listeners, sets an unsolicited last-30-day
  date range, and its loader sets its own array to `[]` without any request.
  It targets absent `#import-history` and `#statistics` rather than the active
  `#import-history-list` and individual metric elements. Thus it does **not**
  erase the inline loader's completed list, but its shared `#loading` toggle
  prematurely hides the initial indicator. Input changes call this inert
  loader; Apply calls the separate inline loader. There are two disconnected
  states/listener systems, not two successful API loads racing each other.
- `app/static/js/dashboard/import_history.js` is **not** the referenced script
  and was not used as the diagnosis or browser proof.
- `app/api/import_history_routes.py:29-69` queries `BatchJob` scoped to
  `created_by_id`, reads and discards `date_from`/`date_to`, passes the status
  string through, and manually emits raw enum objects plus `job_name`,
  `created_at`, `successful_items`, `failed_items`, etc. `total` is the current
  page length, not the full matching result count.
- `app/models/batch_processing.py:15-36` has no `partial` status, although the
  UI offers Partial. It includes non-import job types. Its enum mapping stores
  enum names by default; passing lowercase UI values directly needs explicit
  normalization and a PostgreSQL regression, not an assumption that it works.
  This binding issue is source-supported, not database-reproduced here.

## Source-of-record decision needed for repair

The page explicitly presents application-import audit history, including
Created/Updated/Skipped counts and Partial status. The matching existing source
is `ApplicationImportHistory`, a `TenantMixin` model, populated by real import
flows in `app/application_mgmt/import_routes.py`. The existing authenticated
`/applications/import-history` route at line 4576 returns these records as
`history`, but currently caps at 50 and does not process filters either.

Recommended bounded repair is to use this application-import source of record
for this screen, preserve its tenant scope, and implement filters before
pagination/limits there. Do not reinterpret batch `successful_items` as
applications Created: that would invent a meaning the data does not contain.
Do not merely switch URLs: response validation, field normalization, dates and
error-details representation also need alignment. The application model's
`to_dict()` already parses `error_details` into an array, while the template
currently parses it again as a string. Missing names/dates/counts should be
shown honestly rather than synthesized.

Consolidate this page to one loader/event owner and remove only its obsolete
script inclusion after checking other consumers. Keep filter values on
Refresh; make each request reflect the selected filter snapshot. A request
sequence guard or abort controller must prevent an older response, error or
finally block from overwriting newer results/loading state. The current
inline loader has no such protection; overlapping out-of-order completion was
identified from source, not separately reproduced in this bounded pass.

The batch-job API serialization/status/date defects are separately real; a
source-of-record correction on this page does not claim to repair that API.
Changing the application-history route or active page is outside the current
read-only authorization and awaits parent review.

## Required repair regressions

- Real persisted application audit records: statuses including Partial; dates
  before, on and after both boundaries; independent status/date bounds and
  combinations; clearing filters restores the intended result set.
- Define inclusive date-only bounds consistently with stored UTC timestamps:
  start-of-from-day inclusive and start-of-day-after-to exclusive. Validate
  invalid dates, impossible dates and inverted ranges with explicit 400/error
  feedback; no silent broadening. Validate allowed statuses.
- Verify filtering before pagination, true total versus displayed count, and
  clear statistics labels; do not call a page count a global total.
- Ordinary Apply and Refresh must update visible records, preserve selected
  values and show loading. Rapid successive requests must retain newest data,
  including a stale success after newer error and stale error after success.
- Empty unfiltered, empty filtered, HTTP error, malformed/missing response
  shape, error-details array/string/malformed values, null fields, and escaped
  names/errors must remain distinct and truthful.
- Shared real-database tenant fixtures must prove another organization's
  records never appear. Preserve established policy for same-organization
  history instead of accidentally replacing it with BatchJob's per-user scope.
- If batch API remains in scope separately, exercise real enum serialization,
  valid/invalid status conversion, dates and existing user authorization with
  actual PostgreSQL rows.
- Keep rollback/retry/export out of this read-only repair qualification unless
  separately authorized; their mixed ID/endpoint assumptions need separate
  review before any mutation tests.
