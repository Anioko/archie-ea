# Archie EA Fortune 500 readiness matrix

Status: **qualification in progress**

Current candidate: `e69ebbcf` (superseded when the remediation below is committed)

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
| Build and static correctness | Every `verify.py --tag static` gate passes; no skip | 42/42 static gates passed; candidate-wide verifier passed 49/50 total gates with zero gate skips | Proven locally; repeat after remediation and in final CI |
| Automated suite integrity | Suite collects with strict markers; no import/collection errors or applicable skips | Candidate-wide run: 3,933 passed, 4 failed, 22 errors and 8 skips; all failures/errors traced to missing pgcrypto in PG12 scratch databases and focused remediation passed 36 tests. Skip hygiene remediation is in progress. | Failed on candidate; corrected candidate pending |
| Functional workflows | All unit, integration and persona journeys pass against PostgreSQL 16 | Typed ARB regression 439/439; full browser 177 passed/1 maintenance skip; complete unit suite requires post-remediation rerun | Pending corrected candidate and PG16 CI |
| Tenant isolation | Cross-tenant read/write/search/export/cache/background paths denied; missing tenant context fails closed | Static SQL and ORM scoping gates pass at zero; extensive tenant tests collected | Pending full test execution and fail-closed design audit |
| Authorization | Route/API action matrix covers anonymous and every enterprise role | Repeatable failures include business-case delete status, GDPR platform-admin erasure and an unauthorized admin navigation link | Failed; remediation required |
| Frontend design system | Token, shell, navigation, UI-contract, asset, CSS and console gates pass | Broken-surface defect fixed with regression test; repeatable sidebar, portfolio criticality and data-quality-banner failures remain | Failed; remediation required |
| Interaction correctness | Critical controls, modals, errors, loading, retry, empty and degraded states exercised | Interaction-reality, adversarial, no-error-banner and console suites collected | Pending browser execution |
| Responsive design | Critical persona journeys pass at 320/390/768/1024 and desktop widths with no clipping or horizontal overflow | Mobile persona and repository-shell tests collected | Pending browser execution |
| Visual regression | Reviewed deterministic screenshots for critical pages/states/viewports; unapproved pixel diffs = 0 | Screenshot capture exists for architecture journey only; no broad approved baseline found | Gap—automation required |
| Browser compatibility | Agreed matrix passes: Edge/Chrome, Firefox ESR, Safari if supported | CI now defines Chromium, Firefox and WebKit jobs with retained JUnit/screenshots; execution evidence is not yet recorded. Edge and real Safari remain external. | Pending CI execution and support-policy decision |
| Accessibility | WCAG 2.2 AA automated and manual evidence; no critical/serious issue on critical journeys | Axe ratchet, keyboard/focus/legibility tests collected | Automated run pending; manual NVDA/VoiceOver external |
| Usability and information architecture | Representative personas complete critical tasks; ≥90% completion, no critical usability failure, findings dispositioned | No moderated study evidence in repository | External—product research |
| Frontend performance | Page-class budgets and Core Web Vitals at p75 on corporate hardware; no memory growth in long sessions | Query-growth tests exist; no browser performance gate found | Gap—automation and test environment required |
| Application performance | Agreed p95/p99 latency, throughput and error-rate SLOs under production-shaped peak and soak load | Locust dependency present; no signed capacity result tied to candidate | Gap—production-like environment |
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
| Deployment provenance | Exact green SHA and artifact digest promoted without rebuild; rollback rehearsal succeeds | No deployment executed. Current `deploy/deploy.sh` rebuilds on the host, conflicting with immutable promotion. | Failed—artifact promotion path required |
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
