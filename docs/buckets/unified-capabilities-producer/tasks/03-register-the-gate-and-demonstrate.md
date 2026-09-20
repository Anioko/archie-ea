# Task 03 — Register `store-agreement` as a real gate, and demonstrate the fix

Handoff target: `builder` → `refuter` → `qa-lead`
Depends on: Tasks 01 and 02 merged.

## Objective

Make the disagreement this bucket closes permanently detectable, and prove in a
real browser that `/api/v1/capabilities/` now answers with the estate's actual
capabilities rather than silence.

## Context — read this carefully, the brief is wrong on this point

The bucket brief and CLAUDE.md both state that the `store-agreement` gate is
"registered 31 Aug 2026 and ratcheted at 1", and the brief's headline acceptance
criterion is that the ratchet drops from 1 to 0. **Neither is true in this tree,
verified 17 Sep 2026:**

- `scripts/check_store_agreement.py` exists and works.
- `grep -oE 'Gate\("[a-z-]+"' scripts/verify.py` returns 56 names.
  `store-agreement` is not among them. Neither is `canonical-store`, whose
  checker (`scripts/check_canonical_store.py`) also exists.
- `verification_baseline.json` has **no** `store-agreement` key. There is no
  ratchet of 1 to drop. Nothing enforces store agreement today.

So the checker is one of the entries counted by the `unregistered-checks` ratchet
(@41) — a count, not an enforcement. Closing the capability disagreement without
registering the gate would leave the estate exactly as blind to a recurrence as
it is now, which is the failure mode CLAUDE.md's `docs/known-issues/` section
describes: a documented condition that nothing measures.

The component you extend is `build_gates()` in `scripts/verify.py` (registering a
gate is a `scripts/`-only change and is exempt from the evidence-contract
trailer requirement per `docs/DELIVERY_CONTRACT.md`).

## Constraints

- Register `store-agreement` in `build_gates()` following the shape of the
  existing boot-requiring gates (`broken-surfaces`, `dynamic-link-prefixes`) —
  it boots Flask and needs a database, so it must carry the same tag treatment
  those do and must **not** be reachable from `--tag static`, which cannot boot.
- Baseline it at the number it actually measures **after** Tasks 01 and 02 land,
  and state that number in the commit message with the command that produced it.
  If it measures 0, baseline 0. If it measures more than 0 because of a
  *different* concept (`applications` or `gaps` in the registry), do not baseline
  the capability finding away — report it and hand it back; a baseline that
  absorbs an unfixed disagreement defeats the gate.
- Do **not** add a `store-agreement-ok:` waiver for the capabilities concept.
  The brief is explicit and correct on this.
- The gate's own `[no-evidence]` path is not a pass. If the run reports
  `capabilities [no-evidence] every surface answered 0`, the gate has proven
  nothing and the task is not done — seed the tenant.
- Do not add `technical_capabilities` or `capabilities` (`Capability`) to the
  `CONCEPTS` registry. `technical_capabilities` answers a different question;
  `capabilities` is a separate, out-of-scope, half-built projection target.
- Registering a gate whose measurement is red on main is a regression. Verify
  before committing.

## Deliverable

1. `store-agreement` registered in `scripts/verify.py`'s `build_gates()`, with a
   `verification_baseline.json` entry set to the measured value.
2. A row for it in CLAUDE.md's gate table **and** `docs/DELIVERY_CONTRACT.md`'s
   role-to-gate map — the `docs-drift` gate is must-be-0 and compares those
   claims against `build_gates()`, so this is not optional.
3. A Playwright demonstration in `tests/smoke/` (extend
   `test_archetype_journeys.py`, and add the route to the authorisation matrix in
   `test_authorisation_matrix.py` if a new persona-visible surface is touched):
   logged in as `enterprise_architect` or `solution_architect`, a
   capability-listing screen backed by `/api/v1/capabilities/` renders a
   non-empty list, and the number it shows equals the number the
   `business_capability`-backed surface shows for the same organization on the
   same page load.
4. A deploy to production and a post-deploy verification per
   `scripts/deploy_verified.sh`, with the live `/api/v1/capabilities/` count
   recorded next to the live `business_capability` count.

## Acceptance Criteria

- `python scripts/verify.py --gate store-agreement` runs, reports the
  `capabilities` concept with **four surfaces all answering the same non-zero
  number**, and is not `[no-evidence]`.
- `python scripts/verify.py` (bare) is green.
- The Playwright test fails if the projection is reverted — demonstrate this by
  temporarily reverting Task 01's chain step locally and showing the test red.
  A test that passes both ways measures nothing.
- Production `/version` reports the deployed commit, and the live capability
  count matches `business_capability`'s live count.

## Handoff target

`refuter`, then `qa-lead` for the browser walkthrough. The refuter should
specifically confirm the baseline number was measured rather than chosen, and
that the gate is reachable from a bare `python scripts/verify.py` rather than
only from `--gate`.
