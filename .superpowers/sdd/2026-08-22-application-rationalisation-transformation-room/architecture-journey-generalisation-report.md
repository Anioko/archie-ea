# Architecture Journey generalisation report

## Product decision

The rejected `/business-architecture/` card directory is discontinued. Its URL now permanently redirects, with business-transformation intent preserved, to the canonical Architecture Journey.

Architecture work now has a tenant-scoped identity independent of `Solution`. A journey records its owner, purpose, selected architecture layers, evidence, working deliverables, current stage and optional outcome links. `Solution` remains a compatible specialised outcome, not the aggregate root or assumed destination.

## Visible experience

- Purpose-first launch across business transformation, operating model, strategy-to-execution, portfolio change, risk/regulation, assessment and solution design.
- Scope selection across motivation, strategy, business, data, application, technology, implementation and governance.
- Explicit outcomes include architecture-only, decision, roadmap, programme, solution, undecided and no-change-recommended.
- A resumable Frame → Discover → Shape → Decide → Deliver workspace.
- Evidence register supporting validated references and canonical uploaded-document IDs.
- Existing Business Architecture capabilities retained as selectable working deliverables with links built only from registered Flask endpoints.
- Business Architect and Platform Admin navigation now points directly to Architecture Journey.
- The obsolete static template, twelve-card catalogue and its old tests were removed.

## Verification

- TDD RED observed: legacy page returned 200 rather than the required intent-preserving 301.
- Focused suite: 11 passing, then the remaining administrator-authorisation test passing after using the canonical `is_platform_admin` authority flag (12 behavioural contracts covered in total).
- All 540 templates parsed before obsolete-template removal; all references resolved.
- Targeted Ruff correctness checks: green.
- Design-token and fabricated-data checks: green.
- Fetch-guard check: 0 unguarded fetches.
- Tailwind CSS rebuilt; `scripts/build_css.py --check`: green.
- `git diff --check`: green.

The lead agent will run integrated full-suite/CI verification after combining parallel visible-product branches.
