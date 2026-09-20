# Task Brief: Fix Two Critical UX/Data-Integrity Defects Found in Live Review

## Objective
Fix two Critical-severity defects found tonight by a real browser-driven UX
review of production (`https://165-22-125-156.sslip.io`, logged in as
`qa-solution-architect@example.com`), documented with screenshots in
`UX_IA_REVIEW.md` (main checkout root). These are two independent defects
with different root causes — scope them as separate tasks, not one fix.

## Context

### Defect A — ARB dashboard status chart renders as a broken black ring
The Architecture Review Board dashboard's status chart renders as an
oversized, solid-black, unstyled ring at every width and theme tested
(desktop/tablet, light/dark). This is a rendering failure, not a data
problem — the chart component itself is broken. Screenshot evidence in
`UX_IA_REVIEW.md`; locate the actual chart component (likely Chart.js or
similar, check ARB dashboard route + template) and determine root cause —
candidates to check first: a missing/malformed dataset causing every
segment to collapse into one color, a CSS conflict overriding chart
colors, or a JS error preventing the chart library from initializing
correctly (check browser console via a Playwright script reproduction,
same tooling the review used since the chrome extension is unavailable).

### Defect B — Health Scorecard and Solutions list disagree
The Health Scorecard reports "Total Solutions: 2" while the Solutions list
page says "No solutions found" for the same logged-in user/org. This is
the exact "one system of record per concept" bug class this repo's own
ADR-0008 and CLAUDE.md repeatedly flag (cites prior examples: "Total
Capabilities 191" above "Showing 1-10 of 0 results", a roadmap counting
"173 gaps" beside a Gap Analysis reading "0"). Find what query/store backs
each of these two numbers — they are very likely reading from two
different tables/queries or applying inconsistent tenant/status filtering.
Per ADR-0008's rule: **name the system of record, don't just repoint one
reader at whatever the other already shows** — determine which number is
actually correct (query the DB directly to check ground truth) and fix the
WRONG one to match reality, not just make the two agree by coincidence.

## Constraints
- These are two separate root causes in two separate parts of the
  codebase — Defect A is a front-end rendering bug (ARB chart), Defect B
  is very likely a backend query/service bug (health scorecard aggregation
  vs. solutions list query). Do not conflate fixes.
- Defect B specifically: check whether this is exactly the kind of
  disagreement the `store-agreement` gate is designed to catch (see
  CLAUDE.md's "One system of record per concept" section) — if so, this
  may already be visible via `python scripts/verify.py --gate
  store-agreement`, or may reveal the gate doesn't yet cover this specific
  pair of surfaces (in which case, consider whether extending the gate is
  in scope, per your judgement — flag either way).
- Follow "Done means DEMONSTRATED": a browser-driven check (Playwright
  script, same approach the review used) confirming both numbers now agree
  AND are correct (verified against a direct DB query), and confirming the
  chart renders with actual distinct colors/segments, not just that the
  code compiles.
- The chrome extension (claude-in-chrome) may still be disconnected —
  use a standalone Playwright Python script against production or a local
  dev instance to visually verify the fix, same pattern as tonight's UX
  review.

## Deliverable
1. Defect A fixed: ARB status chart renders correctly with real
   per-status colors/segments at both light/dark and desktop/tablet.
2. Defect B fixed: Health Scorecard and Solutions list agree, and the
   agreed-upon number is verified correct against the database directly
   (not just "the two screens now match" — they must both be right).
3. A regression test for each: one confirming the chart data/config is
   correct (unit/service-level, can't easily pixel-test a chart, but can
   test the data going into it), one confirming Health Scorecard and
   Solutions list return consistent, tenant-correct counts (extend
   `tests/test_tenant_isolation.py`-style pattern if relevant, or a new
   dedicated test).
4. Screenshot evidence (via Playwright script) of both fixes rendered
   correctly, referenced in the task's result.md.

## Acceptance Criteria
- ARB dashboard chart shows real, distinct, correctly-colored segments —
  screenshot proof, both themes, both widths.
- Health Scorecard "Total Solutions" count matches the Solutions list's
  actual result count for the same user/org, and both match a direct
  `SELECT count(*) FROM solutions WHERE organization_id = ...`-style
  ground-truth query.
- `python scripts/verify.py --tag static` clean; if `store-agreement`
  gate is touched/extended, that gate specifically must be green (or its
  baseline correctly ratcheted with justification, never silently raised).
- No regression to any other ARB or Solutions-related test.

## Handoff Target
`tech-lead` first — scope into two separate task files (Defect A, Defect
B) since they're independent root causes, verify current live behavior
against `main`'s actual code before assuming root cause. Then `builder` →
`refuter` per task. Deploy to production once refuter approves both, per
this repo's "Done means DEMONSTRATED, and deployed" standing instruction.
