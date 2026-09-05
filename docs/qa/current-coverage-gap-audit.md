# Current whole-product coverage gap audit

Date: 2026-09-05. **Source/document inspection only. No browser, test suite, CI
service, database or production environment was executed or queried.**

Inspected the working tree whose HEAD was
`db061b955fa879a112438d65777b65316655eeac`; current working-tree additions are
included in the inventory, not claimed as committed or qualified. The finding
ledger records candidate_base `2f7fdc5c121890f3266d3e3ea6e55f6bdac89331` and
qualification_status `in_progress`. Root owns the matrix, ledger and execution
records; none was changed by this audit.

## Concrete gaps and misleading claims

1. **Historical success remains presented as current exact-SHA proof.** The
   matrix correctly opens with qualification reopened, but its build, suite,
   authorization, browser, security, integrity and production rows still use
   “Final exact-SHA” / “Proven—exact SHA” alongside historical 4,003-test counts,
   browser counts and release run 33854737201. These are evidence for that
   historical candidate, not every subsequently changed file. The ledger still
   has F500-028 open and F500-035/F500-041 and numerous later findings in progress,
   including tenant/backbone concerns F500-049/F500-050. An exact current run's
   artifacts must establish closure; source repairs or this audit cannot.

2. **Role/path counts have improved, but completion coverage has not caught up.**
   `tests/smoke/conftest.py::ARCHETYPES` and
   `test_archetype_journeys.py::JOURNEY` now name eleven roles and 24 unique paths,
   including security_architect and data_architect. The matrix's nine-role,
   twenty-path figure is historical, not the current inventory. Conversely,
   `test_task_completion.py::TASKS` still has nine roles. Its test gathers visible
   control text/hrefs and searches for keywords; it does not click those controls
   or finish the task despite its wayfinding language. The Level 10 walkthrough
   actually iterates four roles (CTO, enterprise architect, portfolio manager,
   ARB member); its seeder now creates five, which does not add a fifth executed
   journey. Security/data signature-page visits are not their work outcomes.

3. **“Complete backend and browser matrices” overstates authorization scope.**
   `test_authorisation_matrix.py::POLICY` enumerates seven page paths: three
   procurement pages, three my-applications pages, and AI chat. The separate
   transformation collection matrix adds one API resource. This is useful
   positive/negative coverage, not a browser matrix of every role against every
   read/create/update/delete/export action. Typed ARB has substantial dedicated
   role/tenant checks, but those do not establish unrelated catalog/import/admin
   permissions. Tenant isolation and authorization are separate assertions.

4. **The whole-product audit is neither a complete mutation harness nor a
   release dependency.** `.github/workflows/whole-product-audit.yml` is an
   eleven-role manual workflow. `.github/workflows/ci.yml::release-image.needs`
   does not depend on it. `production_readiness_audit.py::classify_control_for_outcome`
   explicitly classifies forms/mutations as `dedicated-seeded-journey` and fields
   as requiring form-specific work. These classifications correctly admit missing
   evidence. A successful inventory/safe-control audit cannot satisfy the matrix's
   “every reachable visible control” persistence/failure threshold. F500-035's
   narrative that the first audit has never run also needs reconciliation with
   F500-041's account of completed role surveys; this audit did not fetch either
   run to resolve their execution history.

5. **Cross-browser and responsive proof is sampled.** The compatibility job
   currently runs accessibility, archetype, authorization, roadmap CRUD and
   transformation-room files in Firefox/WebKit. It does not run the new blueprint
   composition/governance/delete outcomes or AI protocol journeys there. The
   320/768/1024 archetype test targets a motivation repository shell; 390px covers
   signature screens. This is not every critical workflow at every promised
   width. Matrix wording should preserve those boundaries rather than implying
   the entire product passed on every engine and viewport.

6. **Definitions and old counts cannot prove no skips.** Current CI explicitly
   runs the adversarial probe and separate enabled AI protocol journeys; the
   historical omission is repaired in source, not proof of their latest result.
   The viewed pytest commands produce JUnit and retain artifacts, but no JUnit
   zero-skip/xfail acceptance step was found in the workflow. Ordinary pytest can
   return success with skips. Import/browser guards remain in the tests. The
   matrix's zero-nonpass claim therefore needs the actual candidate report, not
   merely the green job label. AI protocol journeys use the local provider stub;
   they prove protocol/persistence integration, not live-provider quality.

Recent source additions improve coverage: blueprint composition/governance
mutations, roadmap CRUD, transformation creation/deep linking, architecture
downloads, RoPA generation, module-directory navigation, framework empty HTTP,
dashboard consistency and AI protocol persistence. They should be credited by
their exact executed artifacts when available. None justifies relabeling the
remaining product-wide gap as complete.

## Five highest-value next browser journeys

These are proposed tests, **not executed browser findings**. Use explicit
isolated PostgreSQL fixtures, real login, normal rendered clicks, CSRF enabled,
and record visible feedback plus independent persisted state after reload.
Run an allowed role and an unrelated role/tenant against each relevant operation;
assert the actual documented policy rather than assuming all architects share it.

| Priority and persona | Real route/control sequence | Required outcome and existing gap |
| --- | --- | --- |
| 1. Data architect: maintain a data entity | Navigate from `/architecture/data-architecture` to `/architecture/data-entities`; use the catalog's create link, form submit at `/architecture/data-entities/create`, catalog filter, edit link and `#btn-delete-entity` on `/<id>/edit`. Sources: `app/templates/data_architecture/entity_catalog.html`, `entity_form.html`; route module `data_architecture_routes.py:498–646`. | Create a synthetic entity, find it via filter, change classification, reload, cancel deletion with row intact, then confirm deletion with row absent. Verify no cross-tenant entity exposure or mutation. Current data persona journeys visit only dashboard and lineage pages; no dedicated entity-catalog mutation/reload smoke test was found. A GET of those signature pages cannot catch a dead form or confirmation. |
| 2. Security architect: complete risk lifecycle | `/risks/` → Add Risk (`openCreate`) → form submit (`submit`) → row **Mark mitigated**, **Reopen**, **Close**. Sources: `governance/risk_register.html:31,144–166,407–412`; real `POST /api/risks` and `PATCH /api/risks/<id>` in `risk_routes.py`. | Persist a real risk with owned likelihood/impact, verify displayed score/status against saved values, exercise all three transitions after reload, and preserve prior state on a rejected change. Cover a foreign-tenant ID and the role boundary. `tests/journeys/test_journey_risk_register.py` creates via Flask client as enterprise_architect; the security persona browser sample visits the register/governance gates. Neither proves these security-user clicks work. |
| 3. Business architect: stream → stage → capability mapping | `/value-streams/` → create stream → `/<id>` detail → stage create/edit controls → capability search/result → mapping-grid cell (`openCellModal`) → Save and Clear; exercise the visible **Retry** on failed grid loading. Sources: `value_streams/detail.html:73–79,185–245,314–327`; `value_stream_routes.py` create/stage/grid/mapping endpoints. | Prove stream/stage identity and order persist, selected capability maps to the intended stage, reload preserves the mapping, Clear removes only that relationship, and retry never invents empty/zero data. Existing business-architect journey posts via Flask client; the browser map visits value-stream index as enterprise_architect and capability map as business_architect. No stage/grid mutation journey was found. |
| 4. Portfolio manager: governed import to repository | `/batch-import/new` → **Import file** (`#fileUpload`, CSV/XLSX) → preview → **Create Import Job** → `/batch-import/jobs/<id>` → `/batch-import/batches/<id>/review` → select/approve/reject rows → **Commit to Repository** → application portfolio. Sources: `batch_import/new_import.html`, `batch_review.html`, `batch_import_view_routes.py:156,218,296`. | Use a tiny fixture with a valid row, duplicate and invalid row; preview must reflect real parsed values, rejected rows must not persist, committed rows must appear once after reload, repeated commit must not duplicate, and a failed commit must not claim success. Include permission denial and cancellation. Existing import backend/module tests and static census do not establish this multi-page browser outcome. If AI generation is required, use the configured local protocol harness and state that boundary explicitly. |
| 5. Platform/organization administrator: federation settings and subsequent login | `/admin/sso` → **Protocol**, **Email Domain(s)**, **Enable SSO for this organisation**, **Save Configuration** → reload → normal `/account/login`; exercise SAML enabled rejection and a supported OIDC configuration backed by an isolated local IdP. Sources: `admin/sso.html`; `sso_routes.py:156`. | Rejected enabled SAML must preserve prior settings/secret and show failure. OIDC save must persist to real PostgreSQL and a matching-domain login must complete through the configured local IdP, with invalid state/callback denied and ordinary users unable to configure federation. F500-052 remains in progress. `test_sso_configuration_validation.py` already exercises a real Chromium form but doubles storage; repeat that portion in the full app before claiming database/federation coverage. Do not claim support for a commercial IdP or SAML implementation from a local protocol test. |

For each new journey, retain the exact commit, role, viewport, seeded object IDs,
request outcomes and post-reload observations. A permission-denied or failed
dependency path should be a deliberate asserted outcome, not skipped coverage.
Avoid capturing form secrets in artifacts, especially federation credentials.

Only this document was written. All recommendations are bounded by source
inspection; this report adds no new executed release evidence.
