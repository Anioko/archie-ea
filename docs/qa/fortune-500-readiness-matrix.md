# Archie EA Fortune 500 readiness matrix

Status: **qualification in progress**

Candidate identity: resolved from the full Git SHA at execution time and recorded
with the OCI digest in CI's retained `release.json`; no mutable branch name or
short SHA is release evidence.

Qualification date: 3 September 2026

Operating procedure and finding state are maintained in [README.md](README.md)
and [fortune-500-findings.json](fortune-500-findings.json). Execution evidence is
append-only under [`runs/`](runs/).

This is the release evidence index, not a claim that the product is ready. A
row is green only when its evidence is tied to the final immutable release SHA.
`External` means code cannot manufacture the evidence; it still blocks general
enterprise availability until the named owner supplies it.

| Area | Required evidence and release threshold | Current evidence | Status |
|---|---|---|---|
| Build and static correctness | Every `verify.py --tag static` gate passes; no skip | Corrected local candidate: 42/42 static gates passed with zero skips | Proven locally; final CI required |
| Automated suite integrity | Suite collects with strict markers; no import/collection errors or applicable skips | Skip-producing maintenance/version branches were removed or made explicitly applicable; corrected Chromium suite passed 177/177 with zero non-passes | Proven locally; final PostgreSQL 16 CI required |
| Functional workflows | All unit, integration and persona journeys pass against PostgreSQL 16 | Typed ARB regression 439/439; typed ARB browser 26/26; corrected full Chromium browser suite 177/177 | Proven locally; final PostgreSQL 16 CI required |
| Tenant isolation | Cross-tenant read/write/search/export/cache/background paths denied; missing tenant context fails closed | Static SQL and ORM scoping gates pass at zero; extensive tenant tests collected | Pending full test execution and fail-closed design audit |
| Authorization | Route/API action matrix covers anonymous and every enterprise role | Corrected Chromium suite, typed-ARB authorization regression and runtime-role module pass; final CI matrix remains authoritative | Proven locally; final CI required |
| Frontend design system | Token, shell, navigation, UI-contract, asset, CSS and console gates pass | Design/UI static gates pass; full Chromium suite passes; Firefox exposed three CSP-blocked drag handlers and the corrected external-listener regression passes | Proven locally; final cross-browser CI required |
| Interaction correctness | Critical controls, modals, errors, loading, retry, empty and degraded states exercised | Corrected interaction-reality, adversarial, no-error-banner and console cohorts pass in the 177-test Chromium run | Proven locally; final browser CI required |
| Responsive design | Critical persona journeys pass at 320/390/768/1024 and desktop widths with no clipping or horizontal overflow | Mobile persona and repository-shell tests collected | Pending browser execution |
| Visual regression | Reviewed deterministic screenshots for critical pages/states/viewports; unapproved pixel diffs = 0 | Screenshot capture exists for architecture journey only; no broad approved baseline found | Gap—automation required |
| Browser compatibility | Agreed matrix passes: Edge/Chrome, Firefox ESR, Safari if supported | Exact-SHA WebKit passed 56/56. Full local Firefox passed 56/56, but exact-SHA Linux Firefox recorded one opaque intermittent console failure; diagnostics now preserve its structured arguments and source. Edge and real Safari remain external. | Failed in final Firefox CI; rerun required |
| Accessibility | WCAG 2.2 AA automated and manual evidence; no critical/serious issue on critical journeys | Linux Chromium exact-SHA audit reported four serious `/ai-chat` contrast failures. The exactly four Expertise Areas chips used a 4.26:1 base-on-tint pair and now use DESIGN.md's emphasis token at approximately 6.14:1, with regression coverage. | Fix ready for final Linux CI; manual NVDA/VoiceOver also external |
| Usability and information architecture | Representative personas complete critical tasks; ≥90% completion, no critical usability failure, findings dispositioned | No moderated study evidence in repository | External—product research |
| Frontend performance | Page-class budgets and Core Web Vitals at p75 on corporate hardware; no memory growth in long sessions | Query-growth tests exist; no browser performance gate found | Gap—automation and test environment required |
| Application performance | Agreed p95/p99 latency, throughput and error-rate SLOs under production-shaped peak and soak load | Isolated 61,500-row ORM benchmark passed: applications list p95 17.4ms, ArchiMate list p95 54.9ms, solution aggregate p95 4.3ms; all synthetic rows removed. This does not measure HTTP concurrency, throughput, error rate or soak behavior. | Partial—production-like load/soak still required |
| Security SAST | Secret scan, Bandit and dependency scan green; no unreviewed high/critical | Bandit new-finding gate green after narrow reviewed annotations; dependency advisories reduced to zero | Proven locally; full-history gitleaks pending CI |
| Dynamic security | Authenticated DAST, API fuzzing and independent penetration test; no open critical/high | No candidate-tied report | External/security environment |
| Genome HTML safety | Hostile model text cannot create executable elements or event attributes | Five DOM-level adversarial emitter tests pass | Proven locally; repeat in CI |
| AI safety | Direct/indirect prompt injection, cross-tenant retrieval, disclosure, approval bypass, malformed output and provider outage tested | Six AI/governance gates execute; deterministic approval summary test passes. R-61 golden dataset and R-62 persona differentiation remain unimplemented external-provider qualification work and are not represented as passing. | Blocked—red-team corpus and provider sandbox |
| Dependency and supply chain | Zero known shipped CVEs, immutable SBOM, verified vendor assets and provenance | `pip-audit` 0; dependency baseline 0; SRI/vendor gates pass; SBOM generated in CI | Proven locally except final SBOM |
| PDF export | Security-fixed renderer generates a real PDF in production runtime | WeasyPrint 69/pydyf 0.12; version test passes; Linux render test added | Pending Linux CI execution |
| Schema and migrations | Fresh install and supported upgrades pass; no drift; production-shaped rehearsal records counts/checksums/locks | Fresh install plus reconciliation added 3 foreign keys and 8 constraint triggers; subsequent drift gate passed | Proven diagnostically on PostgreSQL 12; PostgreSQL 16 rehearsal pending |
| Data integrity | Referential, uniqueness, tenant and ArchiMate synchronization invariants survive retries/concurrency | Repeatable failures remain in optimistic-conflict rendering, decision-quality counts and capability merge mapping | Failed; remediation required |
| Backup and restore | Encrypted off-host backup restored into isolation; integrity verified; measured RPO/RTO achieved | Pull/verify tooling exists; no candidate-tied full restore evidence | External production-like drill |
| Resilience | Database/Redis/worker/provider/network/disk failure injection meets SLO and alerts correctly | No candidate-tied chaos result | Gap—production-like environment |
| Observability | Health/readiness, logs, metrics, traces and actionable alerts verified end-to-end with tenant-safe redaction | Boot-health passes; runtime alert evidence absent | Pending staging exercise |
| Privacy | Export, erasure, retention and audit requirements pass with legal-approved policy | GDPR authorization tests collected | Automated run pending; policy/legal external |
| Licensing | Deployment model and AGPL/commercial obligations approved | ADR identifies unresolved commercial position | External—owner/legal decision |
| Deployment provenance | Exact green SHA and artifact digest promoted without rebuild; rollback rehearsal succeeds | CI now builds once only after all gates, emits `release.json`, and validates the image/production Compose contract. Host deployment accepts only digest + full SHA, forbids rebuild/source mounts, verifies running identity and rolls back by prior digest. Execution and rollback evidence remain required. | Implemented; final artifact/deploy rehearsal pending |
| Production acceptance | Live health plus critical synthetic persona journeys green; monitoring stable through observation window | No candidate deployment | Pending deployment |

## Final release decision rule

Approve Fortune 500 production use only when every applicable row above is
`Proven` for the same final commit and artifact digest, no automated gate skips,
no open critical/high security or usability finding, restore and rollback meet
the agreed RPO/RTO, and production synthetic journeys pass. Conditional,
pending, gap and external rows are not equivalent to acceptance.

## Evidence commands

```text
python scripts/verify.py --json --require-db
python scripts/ci/bandit_gate.py
python scripts/ci/dependency_audit.py
pytest -q --maxfail=20 --ignore=tests/smoke --cov=app --cov-report=xml
pytest tests/smoke -q --timeout=900
```

CI must additionally retain the full-history secret-scan result, CycloneDX SBOM,
coverage XML, browser failure evidence, immutable artifact digest and deployment
record for the final SHA.
