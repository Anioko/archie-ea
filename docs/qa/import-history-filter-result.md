# Application Import History repair qualification

Candidate implementation, 2026-09-05. No production data was accessed or changed.
No commit, deployment, package installation or baseline waiver was performed.

## Implementation boundary

- The page now reads real `ApplicationImportHistory` records using
  `url_for('application_mgmt.get_import_history')`. Its resolved URL is
  **`/dashboard/applications/import-history`**, because the legacy blueprint
  already owns the `/dashboard` prefix. This corrects the unprefixed URL
  assumption in the earlier investigation; no alias or global route change
  was introduced.
- The existing GET retains the `history` response field and adds success,
  matching total, page, page size and page count. Status and strict ISO dates
  filter before pagination. Date-from is inclusive UTC midnight; date-to is
  exclusive midnight of the following day. Invalid status/date/range/page/
  format inputs return explicit 400 responses before ORM access.
- CSV is the same scoped GET with `format=csv`, exporting all matching records,
  not just the visible page. It preserves actual Created/Updated/etc. fields.
  A local adapter reuses the established `_sanitize_csv_value` and additionally
  detects formula prefixes after whitespace; numeric cells remain numeric.
- One Alpine owner replaces the disconnected inline/stale-manager pair. The
  old `js/import_history.js` is no longer included on this page; the similarly
  named inactive dashboard script was not edited. Rendering uses text bindings,
  not HTML interpolation of stored names, settings or errors.
- Loading, filtered empty, unfiltered empty, malformed response and HTTP failure
  states are distinct. Request revisions protect results, errors, statistics
  and loading from older responses. Matching total is distinguished from
  **on-this-page** Created/Updated/Failed totals. Missing values use em dashes.
- If a refresh finds that its page no longer exists, the loader makes at most
  one recovery request for the reported last page, retaining the original
  filter snapshot. Continued inconsistency becomes a visible error, not an
  infinite retry or a false empty result. Newer requests retain ownership.
- View uses the standard modal with an explicit invoking element for focus
  return. CSV uses `Platform.fetch`, validates the actual CSV header so an HTML
  login page or JSON response cannot become a successful download, and then
  creates a local download blob. No raw-fetch exception was added.

## Action and identity boundary

Rollback uses the actual application-history ID and existing
`POST /applications/rollback-import/<history_id>` endpoint, never a BatchJob ID.
Read-only eligibility comes from the separately owned/reviewed
`rollback_import_eligibility(history, current_user)` helper. The confirmation
names the recorded created-application count, says deletion is permanent and
explicitly says updated values are **not** restored. The endpoint independently
rechecks permission, strict seven-day eligibility and the full target set.
The page prevents duplicate pending writes, retains server error messages and
reloads history only after an explicit successful response.

The rollback endpoint's safety repair belongs to the separate rollback worker,
not this patch's scope. Local page tests do not prove database deletion safety.

Application-history retry remains **unimplemented** because these records do
not have a verified persisted batch-job link. The page shows an explicitly
unavailable Retry control with that reason; it does not send an application
ID to the batch retry endpoint or hide the missing capability. Running-record
progress similarly explains its missing saved linkage. Implemented batch
operations on other surfaces were not removed.

## Verification evidence

- Investigation red: seven failures and one passing empty/error check. The
  independent BatchJob-enum endpoint case was subsequently transferred to
  `tests/test_batch_import_history_api.py` ownership; it is no longer in the
  page test file.
- Application-history response red: one failure in 22.36s, because the old
  page expected `jobs` instead of `history`.
- Query-validation red: nine failures in 68.85s; old code entered ORM access
  instead of returning 400. This no-database test intentionally invokes the
  real view through a lightweight authenticated Flask app.
- Query-validation green: nine passed in 51.36s, six existing import warnings.
- CSV red: leading-tab plain text remained unprotected (one failed, eight
  passed in 60.25s). Final non-database route suite: **20 passed in 154.77s**,
  seven existing import/deprecation warnings. Eleven cases execute the real
  CSV writer through the route with only the persistence query doubled.
- Stale-response mutation proof: removing only the revision increment caused
  the older January record to overwrite newer February results (one failure
  in 17.04s). The increment was restored. That deliberately failing run also
  logged a Playwright `Target closed` teardown diagnostic.
- Malformed-row red: an object status caused a rendering exception instead of
  visible error feedback (one failed, four passed, one teardown error in
  21.00s). Response-row validation was added before publishing rows.
- View focus red: WebKit ordinary Close left the View button unfocused (one
  failure in 20.34s). Explicit invoker fixed this. The complete list/CSV/View
  matrix then passed **63 cases in 133.36s**, 21 each in Chromium, Firefox and
  WebKit.
- Rollback interaction red: missing confirmation control (one failure in
  45.98s). Rollback interaction green: **27 passed in 75.68s**, nine per engine,
  covering normal cancellation/Close/Escape focus, exactly one write from
  double-click, and 400/403/404/500 plus `success:false` without false success.
- The combined browser matrix before pagination recovery passed **108 cases
  in 285.38s**. The parent independently ran the expanded matrix: **108 passed,
  three failed in 316.62s**; all three failures were the last-page refresh
  regression, one per engine (expected surviving rows, observed no rows).
- Additional recovery red: **two failed in 20.66s** on Chromium, exercising
  captured filters while draft inputs change and visible failure after a
  bounded retry. Recovery green: **nine passed in 57.17s**, three per engine.
  Final expanded browser matrix: **117 passed in 306.21s**, 39 each in
  Chromium, Firefox and WebKit, exit 0 with no reported warnings or failures.
- Template syntax and references: two gates passed, no failures/skips.
- Raw-fetch scan: zero sites after repository-native download transport.
- Focused correctness lint and diff whitespace checks passed.
- The initial CSS check reported stale output and an outdated Browserslist
  notice. The parent subsequently rebuilt shared CSS (hash `5402f5e0`) and
  reported a passing freshness check. Pagination recovery changes JavaScript
  only; the parent owns the final shared gate run.

## Real database qualification still required

`tests/test_application_import_history.py` includes a shared rollback-transaction
database case covering inclusive subsecond date bounds, filtering before
pagination, true totals, all-matching CSV, same-org colleague visibility and
foreign-org exclusion. It was **collected, not executed** locally.

`tests/smoke/test_application_import_history_journey.py` was **collected, not
executed** locally (the final combined route/smoke collection found 22 cases in
3.26s). It requires the shared smoke harness's
explicit disposable `TEST_DATABASE_URL` and shared real login/server. Unique
committed fixture rows are necessary for visibility to the server process;
exact-ID cleanup removes only those records. It exercises visible filtering,
CSV, rollback cancellation, confirmation, response status, full reload and
database snapshots: created application removed, updated application unchanged,
other and foreign history preserved. No HTTP interception, provider or handler
doubles are used in this pending full-app journey.

The local browser matrix renders the actual template/macros/scripts/CSS with a
minimal fixture parent layout and a real loopback HTTP server. History/export/
rollback responses are explicit fixtures, not a real application database.
The fixture's post-reload state is not claimed as PostgreSQL persistence. No
full-product or deployment acceptance follows from these focused results.
