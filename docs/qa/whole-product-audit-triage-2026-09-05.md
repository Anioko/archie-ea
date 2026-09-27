# Whole-product audit triage — 5 September 2026

## Evidence boundary

Read-only triage of **nine completed role JSON reports** retained under `.qa-artifacts-33925485628/audit-<role>-c87d0d1fa739a3447f19440553bcd4fc3d9b2112/whole-product-audit-<role>.json`. The audited revision is **c87d0d1fa739a3447f19440553bcd4fc3d9b2112**, not the current candidate. Local source inspection was against HEAD **2dbeb823f614503b9fe5acb02ebf2e3c4b401b11** plus the shared worktree. No network, test execution, browser, database, production access, or ledger modification occurred in this task.

The parent reported run 33925485628 still active for `platform_admin` and `data_architect`, with the other jobs terminal/failed. Neither missing role has a report in this reviewed set. This report does not infer their results or independently refresh run status. These are historical executed observations, not current-candidate failures or release acceptance.

## Exact inventory

Each report records 1,232 route candidates, 2,464 audited page requests (two viewports), and 934 control-inventory entries. Across nine reports: **22,176 page requests**, **8,406 inventory entries**, **238,455 control-outcome records**, and **14,794 findings**. Counts repeat routes, aliases, shared shell controls, and viewports; they are not distinct defects or completed business journeys.

| Role | Outcome records | Findings | Records marked evidence_reused |
|---|---:|---:|---:|
| application_manager | 23,219 | 1,640 | 13,683 |
| arb_member | 24,384 | 1,646 | 14,903 |
| business_architect | 30,739 | 1,647 | 21,257 |
| cto | 27,931 | 1,647 | 18,437 |
| enterprise_architect | 31,479 | 1,649 | 21,975 |
| portfolio_manager | 24,871 | 1,639 | 15,213 |
| procurement | 25,593 | 1,643 | 15,935 |
| security_architect | 25,846 | 1,639 | 16,353 |
| solution_architect | 24,393 | 1,644 | 14,911 |
| **Total** | **238,455** | **14,794** | **152,667** |

After excluding `evidence_reused`, 85,788 records remain: **39,322 `verified`**, **11,391 failed/not-found/no-observable records**, **1,852 `dedicated-seeded-journey` statuses**, and **33,223 records with no status**. The last group includes editable fields and deferred potentially mutating controls; it is not a passing or failing action count. The 11,391 failed records match the total `control-no-outcome` findings. The other 3,403 findings include 988 expected-forbidden observations, 1,414 forbidden observations requiring policy context, 342 not-found, 315 template-leak, 108 missing-CSRF inventory observations, 90 duplicate breadcrumbs, 54 unavailable services, 36 dead links, 20 unauthorized-access, 18 no-main-landmark, and 18 server-error observations.

## Five highest-value follow-ups

All counts below use records **without** `evidence_reused`, at the exact named route. They refer to the older audited revision. Source checks increase or decrease plausibility; they do not substitute for a current full-app retest.

| Priority / route and intended outcome | Executed evidence in all nine reports | Current-source disposition and smallest useful qualification |
|---|---|---|
| 1. `/` → brand **A.R.C.H.I.E.** → usable home | **9 desktop clicks** navigate to `/admin/` and record `navigation-http-error`, **403**. The nine mobile clicks also fail, but with no HTTP status; do not conflate them with confirmed 403 navigation. | `app/templates/components/admin_sidebar.html:74` still hard-codes `url_for('admin.index')`, unchanged between audited SHA and inspected HEAD. Strong, source-supported navigation defect candidate for ordinary users. Keep admin authorization intact; use the appropriate accessible home destination and verify actual brand clicks as non-admin and admin at both viewports. Group under existing navigation umbrella **F500-041**, not nine new findings. |
| 2. `/architecture-assistant/model-viewer` → **Back to Architecture Assistant**; export when a model exists | **18 Back clicks** and **18 Export model as XML clicks** have `no-observable-outcome` (both viewports, all nine roles). | Both template handler around lines 264–274 and `app/static/js/architecture_assistant/archimate_model_viewer.js:46–57` gate both actions on `currentModel`; unchanged since audited SHA. The Back destination function already navigates to `/architecture-assistant/`, but its listener never calls it without a model. Source-supported empty-state escape defect. Back should remain useful without a model; export needs an honest unavailable state when no model exists. Retest empty-state Back first, then generate/load a synthetic model through its supported journey and verify a real parseable export. The audit did not establish that populated exports fail. |
| 3. `/dashboard/import-history` → **Apply filters to history** / **Refresh** → correct persisted job rows | **18 Apply filters clicks** and **18 Refresh clicks** have `no-observable-outcome`. | Template `applyFilters()` around line 564 explicitly reloads all data; its `loadImportHistory()` requests `/api/import-history` without filter parameters. The additional loaded `app/static/js/import_history.js` has a manager whose `loadImportHistory()` assigns an empty array without requesting the API. These paths remain in current source; multiple competing implementations must be resolved before claiming filter behavior. A same-data refresh can legitimately end with unchanged DOM, so that audit result alone is not a defect. Use two real synthetic jobs with different statuses/dates, apply excluding and matching filters, observe requests and exact visible persisted rows, then refresh after a known change. Connect this to the batch-import journey rather than inventing display rows to satisfy the UI. |
| 4. `/architecture/health` → **Toggle advanced architecture filters** and **Return to architecture table** | **18 desktop activation timeouts**, one per control per role. The corresponding **18 mobile records are `verified`**. | Current `_repository_workspace.html:90–109` has actual state-changing handlers (`showAdvanced`, `toggleViewMode()`), unchanged since audited SHA. This is not evidence of missing handlers or a universal dead control. Reproduce settled desktop layout with fresh stable locators and inspect what intercepts/obscures clicks; assert the advanced region's visibility and a real view-mode change. Preserve the mobile counterevidence. The truncated exception details do not identify the blocking element, so a source-only fix is unjustified. |
| 5. `/ai-chat` → open rail, switch **Context/Query/Chats**, return to conversation | **18 Context activation timeouts** at the exact `/ai-chat` route (all nine roles, both viewports). Other tab/export failures recur across AI route aliases; they are not independent features. | `ai_chat/index.html:362–389` intentionally makes the rail inert when closed and mobile-translated offscreen, while wiring real tab handlers. The census uses element visibility/ordinal replay rather than first opening the rail, so a closed/offscreen target is a plausible harness precondition failure, not a proven missing tab action. Qualify the actual opener → visible rail → alternate tab → Context sequence, plus keyboard focus and close/reopen. Do not add permissive click forcing or classify a closed rail's buttons as user-action failures. |

The first two have particularly direct current-source explanations. Import history merits a bounded end-to-end investigation because the source paths conflict. The last two are high-value **reproduction tasks**, not approved fixes; no current browser result was obtained here.

## Do not turn inventory or ambiguous probes into defects

- **AI suggestion chips:** at `/ai-chat`, “Review tech stack gaps” yields 18 `no-observable-outcome` records. Current `app/static/js/ai_chat/app.js:67` deliberately sets the input value and focuses it. `_OUTCOME_SNAPSHOT` measures structural/state/scroll changes, not editable values or focus. This is a concrete measurement blind spot, not evidence the suggestion failed. Test the input's value directly without retaining its contents in audit artifacts. Other two suggestion chips follow the same pattern.
- **Closed mobile navigation and skip links:** the application-manager report alone contains 356 non-reused Close navigation failures and 264 Skip to main content failures. The sidebar is deliberately translated offscreen when closed; skip links are keyboard affordances. Use open → close and keyboard Tab → skip → focus target journeys. Do not report these as hundreds of product-specific failures or remove the accessibility affordances.
- **Unchanged filters, Clear, current tabs, sorting, refresh:** clicking defaults or sorting a single/empty result set may correctly leave the snapshot unchanged. Seed distinguishable rows and select a non-default value before judging an outcome. `Refresh spec list` is wired to `loadSpecs()` with loading/error states in current `api_registry.html`; the old generic no-change flag does not establish a dead refresh.
- **File chooser:** `Browse for files` appears among no-outcome records, but the probe observes downloads/popups rather than file-chooser events. A real `expect_file_chooser` plus isolated supported upload is necessary.
- **Mutations:** `dedicated-seeded-journey` means deferred, sometimes because the probe blocked a non-GET request. It does not prove create/save/delete persistence, CSRF acceptance, or rollback. Do not promote those records to pass counts.
- **CSRF:** the 108 findings are DOM inventory checks, despite their detail claiming submission would 400. No such submission is established by that check. Current login template has `form.hidden_tag()`; configuration determines whether it emits a token. **F500-048** already tracks the audit server's disabled-CSRF defect. Rerun the corrected real login/form boundary, not duplicate 108 bugs.

## Known duplicates and source changes since this audit

| Historical observation | Ledger / current source | Disposition |
|---|---|---|
| Excessive reused outcomes / transferred navigation evidence | **F500-028/038/040/047**; current `control_outcome_fingerprint` keys page and control instance, and rejects HTTP-error navigation. The auditor differs from audited SHA. | Do not use 152,667 reused records as independent executed evidence; rerun candidate auditor. |
| `/admin/deprecation/` accessible to ordinary roles | **F500-044**; both current admin route implementations have `@admin_required`, added since audit. | Likely addressed in source, not closed by this read-only triage. |
| `/admin/governance-gates` accessible to security architect | Two extra unauthorized-access observations occur only for this role. Current role navigation explicitly offers Governance Gates to security architect; route has a dedicated read policy and distinguishes admin mutation controls. | `/admin/` URL prefix alone is not policy proof. Verify read versus mutation authorization; do not strip intended security-role access to satisfy the heuristic. |
| Five pages with duplicate breadcrumbs | **F500-045**; inspected rationalization enrichment template now uses the shared layout and its duplicate trail was removed since audit. | Existing repair/retest item, not 90 new bugs. Other affected pages still need candidate qualification. |
| RoPA public-shell About links / no main landmark | **F500-046/051**; current `genome/data_ropa.html` extends `layouts/admin_base.html` and has the repaired terminology/shell. | Likely addressed in source; retain full-app retest requirement. |
| `/auth/sso/callback/saml` HTTP 501 | **F500-052**; callback remains unsupported, but current SSO settings reject enabling SAML before mutating configuration. | Configuration honesty repair is present; this is not evidence of a working SAML integration. Keep unsupported/configured cases distinct. |
| `/dashboard/api/templates/frameworks` HTTP 503 | **F500-069**; current legacy handler now returns the actual collection, including 200 `[]`, with separate database-error handling. | Source repair present; candidate database/browser contracts, not this old report, decide acceptance. |
| `/ai-chat/api/health/llm` and `/ai-chat/guide/history` HTTP 503 | Current availability contracts explicitly distinguish missing provider and disabled guide configurations. | Configuration-dependent unavailability, not blanket permission to ignore 503s. Need configured-success and honest-unavailable UI outcomes. |

Existing blueprint governance/composition/delete fixes (**F500-062/065/070**) and roadmap work (**F500-067**) require their dedicated seeded journeys. The broad reports do not independently exercise those item-specific persistence outcomes, and must not be cited as green or red evidence for the current repaired controls.

## Handoff

Only this document was added. The nine reports were parsed for counts, failure classifications, exact-route examples and duplication; current source and the ledger were read, not modified. No current-candidate execution claims are made. Root owns ledger decisions, the remaining role artifacts, focused reproductions, and final immutable-candidate no-skip acceptance.
