# Initial whole-product survey: triage update

Run `33923515022`, revision `09c2c675`, has eight downloaded role reports: application manager, ARB member, business architect, CTO, enterprise architect, portfolio manager, procurement and solution architect. Each contains 2,464 page requests over 1,232 route candidates at two viewports. Together they contain 2,872 observations, including 752 non-informational observations. These are repeated observations, not unique defects or verified interaction counts. The three remaining roles were still running when checked.

This revision predates later audit corrections. In particular, the survey does not establish correct role privilege seeding, CSRF-enforced submissions or L10 click outcomes.

| Observation | Evidence and disposition | Still required |
|---|---|---|
| `/dashboard/api/value-streams` returns 404 | `application_mgmt.api_get_value_streams` requires `domain_id` or `domain_code`; the survey supplied neither. This is a JSON lookup, not a missing HTML page. | Seed a real domain and exercise the consuming UI and its request parameters. |
| `/ea-workflows/deliverables/vision` returns 404 | Route checks for workflow definition `ADM_PHASE_A_VISION`; missing definition yields 404. | Seed the workflow and exercise launcher, editor and persistence. |
| `/implementation/*` returns 404 | Blueprint checks `architecture_implementation_planning` feature flag before dispatch. | Test enabled and disabled configurations; do not treat disabled configuration as feature qualification. |
| `/account/saml/login` and metadata return 404 | Account routes require SAML availability/configuration. | Qualify configured account SAML with controlled identity-provider fixtures. |
| `/auth/sso/callback/saml` returns 501 | Separate organisation-federation service explicitly has an unimplemented SAML path; this is not a successful feature. | Prevent enabling unusable configuration, and retain SAML implementation/qualification as outstanding scope. |
| Missing form CSRF tokens | Initial audit uses TestingConfig with CSRF disabled. | Rerun with the corrected audit server (F500-048), including real submissions. |
| Unnamed account switches | Their names use `aria-labelledby`, which the old probe ignored. | Corrected probe regression passes; repeat application audit (F500-043). |
| Duplicate breadcrumbs | Five pages rendered two trails. Repairs now use one shared-header trail; local syntax, shell and breadcrumb gates pass. | Full application browser and deployed retest (F500-045). |
| RoPA dead About links/missing main | Direct live browser confirms public-site shell. Generate RoPA succeeds and renders eleven activities. | Deploy and retest the application-shell repair (F500-046). |
| Billing and deprecation administrative access | Independently reproduced with actual route permission tests; guards repaired. | Full application role-matrix and deployed verification (F500-042/044). |

Unlisted observations, including Lucidchart connection setup, remain untriaged. Raw per-role reports are retained in `.qa-artifacts-33923515022/` in the shared worktree and as the run's GitHub artifacts. Original observations have not been deleted or represented as passing tests.
