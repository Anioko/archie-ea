# Modal invoking-control audit

2026-09-05; read-only source audit of the fortune500-readiness worktree. Only this
report was changed. The modal controller and data-entity form are owned by the
modal worker. This is a migration inventory, not a browser failure census.

## Contract and evidence boundary

The selected controller design accepts an explicit element in
`confirm(message, { returnFocus: control })` and
`open(id, payload, { returnFocus: control })`. Its internal `awaitResult` forwards
the options and is exported as `prompt`. No application calls to
`Platform.modal.awaitResult(...)` or executable `Platform.modal.prompt(...)` were
found by the focused search; matches were controller implementation/examples.

Do not assume a global click-origin fallback: it is being removed because a
microtask can make synchronous-event provenance ambiguous. Without explicit
invoker information, activeElement remains a fallback and may identify a
previous input after WebKit pointer activation. An `async` function that opens
before its first `await` still lacks explicit invoker information; the function's
async label alone is not the issue.

For Alpine handlers, pass `$event.currentTarget` into the method. For direct DOM
listeners, capture `event.currentTarget` before awaiting (or use the listener's
`this`). For delegated listeners, use the matched button, not document or a
nested icon. Carry the element through helper calls, promise callbacks and custom
event detail. Do not store the Event object for later use. Preserve existing
modal payloads: `open`'s options are its third argument.

“Source-linked” below means a route renders the template and, for external JS, a
template references its script. It does not prove that a particular role,
feature flag, populated row or browser can currently reach the control. No
production actions or browser mutations were performed for this audit.

## First migration: shared adapter and delayed opens

| Source and function | Invoking control / evidence | Recommended threading and qualification |
|---|---|---|
| `app/static/js/ui/modal.js`, `confirmSubmit` | Existing form handlers pass `$event`; examples: admin `webhook_settings.html`, `sso_settings.html`, `api_settings.html`, `feature_flags.html`; procurement `contract_form.html` / `license_form.html`; application `list_simple.html` | Capture `event.submitter` and pass it as `returnFocus`, retaining caller-specified options. Current adapter derives the form but discards submitter. Enter-key submit may have no submitter; retain fallback for that case. This is a central coverage opportunity, not a reason to rewrite every form. |
| `app/templates/components/document_analyzer.html`, `applyAnalysis()` (confirm near line 765) | Apply Analysis button at line 544; macro imported and rendered by `vendors/vendor_detail.html` | Pass button at invocation and retain it across the apply-analysis HTTP request into the later reload confirmation. Ensure the control is enabled/rendered when restoring focus. Source-linked delayed confirmation. |
| `app/templates/codegen/partials/_wb_chat_panel.html`, `applyPatch(msg, patch, pi)` (confirm near line 316) | Patch Apply button at line 97; included by `codegen/_wb_ide.html`. `applyAll` also invokes `applyPatch` | Capture individual Apply or Apply All button; thread through the loop and apply request to the security-warning retry confirmation. Do not infer the opener from the now-completed request or from a removed row. Source-linked delayed error-path confirmation; requires a requires_force response to qualify in browser. |
| `app/templates/admin/abacus_consolidation.html`, `autoMergeHighConfidence()` → `bulkMergeSelected()` | Auto-merge button line 82; first confirmation near 365, then another confirmation in `bulkMergeSelected` near 332 | Preserve the original Auto-merge control across both confirmations. Passing only the control to the first call is incomplete. Source-linked through capabilities `abacus_consolidation.py`. |

## Admin, data, governance and catalog controls

The following source-linked callers currently omit an explicit return element.
Most open synchronously, so these are focused migration/test candidates; they are
not individually established failures. Line numbers describe the audited source
and may move as other workers edit files.

| Exact source / function | Invoking control | Recommended change |
|---|---|---|
| `templates/data_architecture/entity_form.html`, delete click listener, line 143 | `#btn-delete-entity` | Pass the existing `btn` to confirm. Modal worker owns this case; avoid a competing edit. Rendered by `modules/architecture/routes/data_architecture_routes.py`. |
| `templates/admin/jira_settings.html`, five click listeners, lines 498/585/612/638/735 | `#push-btn`, `#kanban-push-btn`, `#push-epics-btn`, `#push-dependencies-btn`, `#push-applications-btn` | Each listener already has an exact `this` button; pass it to confirm before disabling it. Test Cancel/Escape without invoking external sync. |
| `templates/admin/servicenow_integration.html`, syncBtn click listener, line 311 | `syncBtn` | Pass existing button to confirm. Source-linked canonical admin route; cancel-only browser test avoids a real CMDB write. |
| `templates/admin/seed_management.html`, `seedAll()`, line 164 | Seed All button (`@click="seedAll()"`, line 22) | `seedAll($event.currentTarget)` → confirm options. Validate dismissal without seeding. |
| `templates/admin/abacus_settings.html`, `cancelCurrentJob()`, line 842 | Job cancel control invoking this helper | Add invoker parameter and propagate from actual cancel control. Job ID must exist to reach dialog; do not cancel a live job in a focus test. |
| `templates/admin/abacus_consolidation.html`, `mergePair`, `bulkMergeSelected`, `autoMergeHighConfidence` | Row merge line 196, selected merge line 74, automatic merge line 82 | Add final invoker argument to each helper and pass to all confirmations; selected/high-confidence rows are reachability prerequisites. |
| `templates/admin/abacus_compare.html`, inline confirm at line 257 | Merge action button | Add `{ returnFocus: $event.currentTarget }` directly; source-linked compare render in capabilities route. |
| `templates/admin/solution_prompts.html`, `openEdit(prompt)` / `openReset(prompt)`, lines 294/343 | Row Edit line 78 / Reset line 88 | Add invoker after prompt and pass third open argument; opens are synchronous. Source-linked canonical admin solution-prompt route. |
| `templates/ai_chat/admin_prompts.html`, `openEdit(persona)` / `openReset(persona)`, lines 303/384 | Row Edit line 84 / Reset line 95 | Same invoker parameter pattern. Source-linked `modules/ai_chat/routes/chat_admin_routes.py:94`. |
| `templates/governance/risk_register.html`, both `openCreate()` methods, lines 473/537 | Create risk and create RAID controls (separate Alpine scopes) | Thread each scope's clicked button to its respective create-risk/create-raid modal. Source-linked risk route at `risk_routes.py:231`. |
| `static/js/governance/governance_dashboard.js`, `openEditModal(row)` / `confirmBulkDelete()`, lines 286/332 | Governance table row edit buttons at template lines 250/297; bulk delete line 133 | Row + invoker for edit, invoker for bulk delete. Loaded by `templates/capability_management/governance_dashboard.html:19`; both capability governance/management routes render that template. Do not confuse it with `templates/governance/dashboard.html`. |
| `templates/arb/dashboard.html`, `arbQuickAction(itemId, action)`, line 242 | Delegated `[data-arb-action]` control; matched `btn` at line 259 | Pass matched btn into helper and confirm. Passing delegated event.currentTarget would incorrectly select document. Source-linked `arb_routes.py:985`; legacy/typed view can affect control availability. |
| `templates/arb/sessions.html`, direct opens at lines 13/27 and empty-state CTAs 210/212 | New Review / Schedule Session, including empty-state buttons | Direct Alpine open gets third options argument; macro action string must preserve `$event.currentTarget` on the actual rendered button. Source-linked sessions/reviews render paths in arb routes. |
| `templates/arb/decisions.html`, page-header action at line 21 | New Decision | Thread rendered macro button into open or migrate static trigger to the controller's declarative `data-modal-open` contract. Confirm macro support before choosing. |
| `templates/architecture/elements.html`, `deleteElement(el)`, line 913 | Row Delete button (`@click.stop`, line 367) | Add invoker after el and pass confirm options. Source-linked architecture CRUD routes; generic low-priority route also renders same template. |
| `templates/archimate_crud/detail.html`, `deleteElement()`, line 354 | Detail Delete button line 46 | Pass clicked control into method and confirm. Source-linked `archimate_crud/routes.py:1119`. |
| `static/js/archimate_crud/dashboard.js`, `openCreateModal()` / `openEditModal(el)`, lines 747/760 | `data-testid="btn-create-element"` and edit row controls | Thread invoker through methods; template script include verified at `archimate_crud/dashboard.html:568`. Other open calls near 822/873 need their helper/control chains inspected before migration. |
| `templates/framework_config/dashboard.html`, direct open at lines 27/61 | New Configuration header action and empty-state button | Explicit return element on each trigger. Route renders found in `framework_config/routes.py`; do not edit unreferenced framework_instances_table.js as a substitute. |
| `templates/industry_apqc/dashboard.html`, `seedFrameworks()`, line 138 | Seed-default-frameworks control | Add invoking control argument and confirm options; route render in industry_apqc module. Cancel-only qualification. |
| `templates/vendors/list.html`, Add Vendor action at line 32; `static/js/vendors/vendor_list_table.js`, `openEditModal(row)` / bulk-delete helper, lines 72/109 | Header Add Vendor; vendor name and row Edit controls at lines 95/138; bulk action | Preserve each actual button, especially vendor-name vs row-edit alternatives. Script load confirmed at list template line 18; multiple vendor routes render list. |
| `static/js/enterprise/work_packages_table.js`, `openEditModal` / `openCreateModal` / `confirmBulkDelete`, lines 91/103/181 | Template `enterprise/work_packages.html`: New line 31, row Edit line 170, bulk Delete line 67 | Pass invoking element into each method and third open argument. Script load verified at template line 18; runtime route/role should be reconfirmed for browser migration. |
| `templates/enterprise/requirements_traceability.html`, `openLinkCapModal(reqId, capId, capName)`, line 287 | Requirement capability-link control | Add invoker as last argument; source-linked enterprise CRUD route at line 760. Existing nextTick runs after open, so do not capture the opener inside it. |
| `static/js/components/unified_mapping_modal.js`, discovery/direct/reverse open helpers, lines 156/638/676 | Mapping buttons across vendor detail/list, application list/dashboard and capability map | Add `returnFocus` to existing config/options objects at the control and forward as third open argument; retain payload semantics. Component script include at `components/unified_mapping_modal.html:361`, included by these live templates. Methods open before their awaits, but helper chains still must preserve the button. |
| `templates/batch_import/dashboard.html`, `confirmCancel(job)`, line 503 | Job Cancel control | Add invoker after job; rendered by import_batch view route line 75. Cancel dialog dismissal can be tested without cancelling the import. |

Paths in this table omit the common `app/` prefix for readability.

## Observer-opened and uncertain sources: do not count as active API defects

| Source | Evidence and next action |
|---|---|
| `static/js/admin/api_settings_inline.js`, `openOrModal()` line 183 and `openEnvModal()` line 388 | This is the script actually loaded by `templates/admin/api_settings.html:473`. It directly removes `hidden`, then loads data; its close helpers re-add `hidden`. Controls are `.or-change-model-btn` and `#load-env-btn`. Assess observer behavior separately, then migrate both opening and closing to the controller with a captured invoker. The similarly named `static/js/admin/api_settings.js` has API calls at 182/385 but no template/Python load reference was found. Editing only that copy would not repair the observed page. |
| `static/js/dashboard/import_history.js` | Contains API opens at 300/315, but rendered dashboard template loads `js/import_history.js` at line 572 and has inline `viewDetails` itself. No active load reference to the dashboard subdirectory copy found. Inspect the loaded script and inline functions as a separate visibility/observer migration, not these duplicate matches. |
| `static/js/framework_config/framework_instances_table.js`; `static/js/framework_management/dashboard.js`, `extension_dashboard.js`, `manufacturing_table.js` | No template/Python script load reference found for these files. Framework-management dashboard currently contains an inline stats component; extension template has its own inline reset confirmation. The inline reset helper at extension_dashboard.html:347 contains only a reset comment after confirmation: browser reachability/functional qualification is required before treating this as an implemented reset flow. |
| `static/js/components/application_merging_modal.js`, `previewMerge()` | A real async boundary exists before preview-modal open at 430; pass the Preview row button through if this feature is activated. No template include/script reference found for this file/component in this audit, so it is not classified as an active route. Its openMergeModal also separately stores document.activeElement; do not migrate one focus owner without inspecting the other. |
| `static/js/components/document_analyzer.js` | Duplicates a delayed confirmation, but the source-linked vendor page uses the inline document-analyzer macro. Migrate the macro first; confirm a script loader before changing this copy. |
| `templates/admin/team.html` | Route renders the template, and delegated remove-member handler has an exact matched btn. However its script is after the final endblock in an extending template, so source render linkage does not prove the listener is emitted. Inspect rendered response first. If active, pass btn; if omitted, handle the missing handler as a separate defect. |
| `templates/arb/partials/_legacy_dashboard.html` | Not simply dead: `arb/dashboard.html:150` includes it in the non-typed branch. Its Create Review opener needs the same invoker pattern, but branch reachability must be qualified. |
| `static/js/core/06-session-timeout.js` and core-admin/core-composer bundle copies | Session-timeout modals are timer/programmatic opens with no single clicked invoker. Preserve activeElement semantics; do not assign an unrelated last-click button. Bundle duplicates are not three independent user controls. |
| Controller comments and component migration examples | modal.js and components/modal.html/modal_form.html contain example API mentions. They must not inflate a runtime call-site total. |

## Remaining product coverage and acceptance

The broad source search also found modal callers in business cases/models, value
streams, roadmap/capability map, solution blueprint/composition, workflow approval,
application rationalization/import and the ArchiMate composer. They remain in
scope for subsequent focused passes; their individual trigger chains have not
been qualified by this bounded audit. No claim is made that all textual matches
are active, migrated or browser-tested.

Prioritize the shared submit adapter, the two source-linked delayed confirmation
paths, then admin/governance/catalog controls above. For each migrated control,
qualify keyboard activation and WebKit pointer activation with a previously
focused input, then Cancel and Escape; assert the exact initiating control is
focused. For dynamic rows, separately handle a removed/disabled opener. Include
both macro header and empty-state triggers and nested dialogs. Confirm-dismissal
tests should assert no destructive/sync/seed request was sent. A source-only
invoker change is not evidence that the modal appears, closes, or restores focus
in the running product.
