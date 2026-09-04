# Archie EA Fortune 500 readiness matrix

Status: **qualification reopened; whole-product interaction coverage and active
frontend defects block repository-controlled approval**

Candidate identity: resolved from the full Git SHA at execution time and recorded
with the OCI digest in CI's retained `release.json`; no mutable branch name or
short SHA is release evidence.

Qualification date: 4 September 2026

Operating procedure and finding state are maintained in [README.md](README.md)
and [fortune-500-findings.json](fortune-500-findings.json). Execution evidence is
append-only under [`runs/`](runs/).

This is the release evidence index, not a claim that the product is ready. A
row is green only when its evidence is tied to the final immutable release SHA.
`External` means code cannot manufacture the evidence; it still blocks general
enterprise availability until the named owner supplies it.

| Area | Required evidence and release threshold | Current evidence | Status |
|---|---|---|---|
| Build and static correctness | Every `verify.py --tag static` gate passes; no skip | Final exact-SHA CI: 45 static checks passed; independent local rerun: 44/44 with zero skips | Proven—exact SHA |
| Automated suite integrity | Suite collects with strict markers; no import/collection errors or applicable skips | Final CI collected and passed 4,003/4,003 backend tests with zero failed/skipped/xfail/xpass; 2,398 endpoints exercised | Proven—exact SHA |
| Functional workflows | All unit, integration and persona journeys pass against PostgreSQL 16 | Historical candidate passed 4,003 backend tests and the sampled browser suites, but the journey map covers only 20 unique paths across 9 personas and the separately named Level 10 walkthrough covers only 4 personas. Those samples did not prevent multiple broken production controls. | Gap—whole-product outcome inventory active |
| Tenant isolation | Cross-tenant read/write/search/export/cache/background paths denied; missing tenant context fails closed | Static SQL/ORM scoping gates measure zero; full PostgreSQL suite and authorization matrix pass; AI tool-executor identity call sites traced to server-trusted `current_user.id` | Proven automated/code audit; independent DAST remains external |
| Authorization | Route/API action matrix covers anonymous and every enterprise role | Complete backend and browser matrices pass; typed ARB and Governance Gates role boundaries included | Proven—exact SHA |
| Frontend design system | Token, shell, navigation, UI-contract, asset, CSS and console gates pass | Static gates passed historically, but role-specific dashboard panels still shipped fourteen colored side accents after a claimed flat-card correction (F500-030). The current repair requires rendered multi-role verification. | Reopened—active visual defect |
| Interaction correctness | Every reachable visible control has an observed navigation, modal, download, mutation, feedback, persistence, authorization and failure outcome | The structural census passed while production solution controls did nothing. The repository has 564 templates, 476 containing button/link-like controls, versus only 20 unique archetype journey paths and 9 structural census cases. F500-028/F500-029 reopen this row; product-wide outcome coverage is not yet present. | Blocked—active critical coverage gap |
| Responsive design | Critical persona journeys pass at 320/390/768/1024 and desktop widths with no clipping or horizontal overflow | Exact-SHA Chromium responsive persona/repository coverage passes; Firefox/WebKit critical journeys pass | Proven automated; real-device evidence external |
| Visual regression | Reviewed deterministic screenshots for critical pages/states/viewports; unapproved pixel diffs = 0 | Screenshot capture exists for architecture journey only; no broad approved baseline found | Gap—automation required |
| Browser compatibility | Agreed matrix passes: Edge/Chrome, Firefox ESR, Safari if supported | Final exact-SHA CI: Chromium 157+9, Firefox 56/56 and WebKit 56/56, all with zero nonpasses | Proven engine-level; real Edge and Safari hardware external |
| Accessibility | WCAG 2.2 AA automated and manual evidence; no critical/serious issue on critical journeys | Both automated accessibility ratchets pass on the final exact SHA after the four contrast defects were fixed | Automated proven; manual NVDA/JAWS/VoiceOver external |
| Usability and information architecture | Representative personas complete critical tasks; ≥90% completion, no critical usability failure, findings dispositioned | No moderated study evidence in repository | External—product research |
| Frontend performance | Page-class budgets and Core Web Vitals at p75 on corporate hardware; no memory growth in long sessions | Query-growth tests exist; no browser performance gate found | Gap—automation and test environment required |
| Application performance | Agreed p95/p99 latency, throughput and error-rate SLOs under production-shaped peak and soak load | Isolated 61,500-row ORM benchmark passed. Exact code then served 20 concurrent read-only users for 5 minutes: 1,463 requests, zero failures, aggregate p95 100ms/p99 220ms/max 779ms; every page/API p95 ≤140ms | Partial—baseline concurrency proven; production-sized peak and long soak still required |
| Security SAST | Secret scan, Bandit and dependency scan green; no unreviewed high/critical | Final exact-SHA full-history gitleaks, Bandit and dependency audit all green; zero new Bandit findings and zero dependency advisories | Proven—exact SHA |
| Dynamic security | Authenticated DAST, API fuzzing and independent penetration test; no open critical/high | No candidate-tied report | External/security environment |
| Genome HTML safety | Hostile model text cannot create executable elements or event attributes | DOM adversarial emitter tests and HTML-safety gates pass in the final full suite | Proven—exact SHA |
| AI safety | Direct/indirect prompt injection, cross-tenant retrieval, disclosure, approval bypass, malformed output and provider outage tested | Six AI/governance gates pass; delimiter-escape red team found F500-026, whose five regression tests pass independently and in final CI; deterministic executor identity audit is clean | Partial—deterministic controls proven; live conversational/provider red team external |
| Dependency and supply chain | Zero known shipped CVEs, immutable SBOM, verified vendor assets and provenance | Dependency audit zero; SRI/vendor gates pass; final PostgreSQL job emitted CycloneDX SBOM; OCI provenance/revision verified | Proven—exact SHA |
| PDF export | Security-fixed renderer generates a real PDF in production runtime | Pinned renderer versions and Linux production-PDF test pass in final CI | Proven automated—exact SHA |
| Schema and migrations | Fresh install and supported upgrades pass; no drift; production-shaped rehearsal records counts/checksums/locks | PostgreSQL 16 fresh schema/reconciliation and drift gate pass; two protected production cutovers completed schema/ACL phases and remained healthy | Proven for supported reconciliation path; Alembic migration strategy remains architectural debt |
| Data integrity | Referential, uniqueness, tenant and ArchiMate synchronization invariants survive retries/concurrency | Previously failing optimistic-conflict, decision-quality and capability-merge cases were remediated; complete 4,003-test PostgreSQL suite passes; live backup restore matched 789/789 tables | Proven automated; destructive production concurrency not exercised |
| Backup and restore | Encrypted off-host backup restored into isolation; integrity verified; measured RPO/RTO achieved | 4 Sep 2026 live-host drill: 75/75 archives decompressed; fresh 5.5 MB dump restored with zero errors; all 789 tables matched live row counts; scratch database removed | Partial—same-host restore proven; off-host loss scenario and measured RPO/RTO remain external |
| Resilience | Database/Redis/worker/provider/network/disk failure injection meets SLO and alerts correctly | No candidate-tied chaos result | Gap—production-like environment |
| Observability | Health/readiness, logs, metrics, traces and actionable alerts verified end-to-end with tenant-safe redaction | Production health, database, Redis, restart/OOM state and error-log scans verified; daily public monitor green. Metrics/traces/alert delivery have no end-to-end exercise | Partial—alerting exercise required |
| Privacy | Export, erasure, retention and audit requirements pass with legal-approved policy | GDPR authorization/export tests pass in the complete exact-SHA suite | Automated proven; retention/legal policy external |
| Licensing | Deployment model and AGPL/commercial obligations approved | ADR identifies unresolved commercial position | External—owner/legal decision |
| Deployment provenance | Exact green SHA and artifact digest promoted without rebuild; rollback rehearsal succeeds | CI run 33854737201 built once after 11 green prerequisites, emitted `release.json`, verified OCI revision/import; controlled failure restored legacy; final digest was promoted without source mounts or rebuild | Proven—exact SHA/digest |
| Production acceptance | Live health plus critical synthetic persona journeys green; monitoring stable through observation window | Exact digest/revision healthy in production mode; public checks repeatedly green; host error scan zero; production-watch run 33859974145 public check green and adversarial probes 11/11 | Proven for automated/public scope; authenticated live persona journey unavailable without production test identity |

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
