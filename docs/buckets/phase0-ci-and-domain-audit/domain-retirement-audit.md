# Domain retirement audit (Phase 0 of the archie-ea to-be plan)

Answers the as-is/to-be bucket's open question 3. Surveyed each of the 7
overlapping domains directly (file counts, actual import graph, flag
wiring) rather than assuming they're symmetric duplicates.

## Finding: the 7 domains are not one uniform category

| Domain | Legacy files | Modules files | Flag-switched? | Real importers of legacy | Category |
|---|---|---|---|---|---|
| `account` | 3 | 16 | Yes (`USE_ACCOUNT_GUARDRAILS`) | n/a — routes | **A: clean flip** |
| `admin` | 4 | 37 | Yes (`USE_ADMIN_GUARDRAILS`) | n/a — routes | **A: clean flip** |
| `dashboard` | 1 | 25 | Yes (`USE_DASHBOARD_GUARDRAILS`) | n/a — routes | **A: clean flip** |
| `ai_chat` | 2 | 81 | Yes (`USE_AI_CHAT_GUARDRAILS`) | n/a — routes | **A: clean flip, but thin smoke coverage (qa-gap-list Gap 2)** |
| `auth` | 3 | 2 | **No flag found** | 1 (`app.auth.decorators`) | **B: shared utility, not a route duplicate** |
| `monitoring` | 5 | 15 | **No flag found** | 7 | **B: shared utility, not a route duplicate** |
| `integrations` | 1 | 4 | **No flag found** | **0** | **C: dead code** |

**Category A (`account`, `admin`, `dashboard`, `ai_chat`)** — genuine
flag-switched route duplicates, exactly what ADR 0004 describes: flip the
default off, confirm nothing regresses, delete the legacy blueprint. Small
legacy file counts (1-4 files) mean the retirement diff itself is small in
each case.

**Category B (`auth`, `monitoring`)** — CLAUDE.md's list of "7 domains that
exist in both" is imprecise for these two: `app/auth/` holds
`decorators.py`/`sso.py`, genuinely imported elsewhere (1 and 7 real
importers respectively) — these are shared utility modules that happen to
share a directory name with a `app/modules/` counterpart, not a second
implementation of the same routes. `app/modules/auth/` is SSO *routes*;
`app/auth/` is auth *decorators*. Retiring these means migrating each
importer to the `app/modules/` path, not flipping a boot-time flag — a
different, more invasive kind of change than Category A.

**Category C (`integrations`)** — `app/integrations/roadmap_integration.py`
has **zero** real importers anywhere in the codebase. This is dead code,
not a live duplicate. Safe to delete outright, no flag, no migration, no
regression risk — the lowest-risk item in this entire audit.

## Recommended retirement order

Combining this audit with `qa-gap-list.md`'s test-coverage signal
(`ai_chat`/`integrations`/`monitoring` have the thinnest `tests/smoke/`
coverage: 2/1/1 files respectively, vs. 15-51 for the others):

1. **`integrations`** — delete now. Dead code, zero importers, zero flag,
   zero test-coverage risk because there's nothing live to regress.
2. **`account`, `dashboard`, `admin`** (in this order — increasing legacy
   file count, all well-covered by smoke tests) — Category A clean flips.
3. **`ai_chat`** — Category A clean flip, but per `qa-gap-list.md` Gap 2,
   write additional smoke coverage *before* retiring, since only 2 files
   currently touch it despite it being the largest `app/modules/` domain
   (81 files) — the most functionality with the thinnest safety net.
4. **`auth`, `monitoring`** — Category B, not simple flag flips. Each needs
   its own small bucket: find every real importer (1 for auth, 7 for
   monitoring), migrate each to the `app/modules/` path, verify, then
   delete the legacy file. `monitoring`'s thin smoke coverage (qa-gap-list
   Gap 2) means write coverage for its 7 importers' behavior first.

## What this changes about the to-be plan

`to-be-plan.md`'s Phase 1 step 1 said "retire the 7 overlapping legacy
domains, one at a time, in the order Phase 0's audit produces" — this audit
is that output. It also revises the plan's own framing: this isn't 7
uniform retirements, it's 1 trivial deletion + 4 clean flag-flips + 2 small
import-migration tasks. The refuter's Finding 2 (sequencing was stated too
firmly) is resolved by this data: `auth`/`monitoring` genuinely are a
different kind of work than the other 5, not just a different priority
within the same kind of work.
