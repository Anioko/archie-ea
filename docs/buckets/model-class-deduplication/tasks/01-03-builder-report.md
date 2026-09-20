# Builder report — Tasks 1-3 (fast-init tenancy asymmetry)

## What changed

1. `app/models/archimate_core.py` — `ArchiMateRelationship` now inherits `TenantMixin`.
2. `app/models/motivation_extended.py` — `Principle` now inherits `TenantMixin`, with `organization_id` overridden nullable (matches `models.py:1649-1660`'s existing pattern — reconcile-schema is ADD-only).
3. `app/models/application_component_fast.py` — `ApplicationComponent` now inherits `TenantMixin` (no nullable override needed; the canonical class already requires it NOT NULL).

All three are one-mixin additions, no schema change, no touch to `models.py` or any file owned by a concurrent worktree.

## Evidence

- `tests/test_fast_init_model_tenancy.py` — 4 tests, each demonstrated red-then-green by hand (fix stashed, test run red, fix restored, test run green) for the three tenancy fixes; the fourth test documents a newly discovered, separate defect (see below) as a known-red assertion.
- Full acceptance-criteria regression subset: `tests/test_double_mapped_tenancy.py tests/test_fast_init_model_tenancy.py tests/test_model_boot_registration.py tests/test_tenant_isolation.py` — 27 passed, 0 failed (bare run, then `test_fast_init_model_tenancy.py` re-run standalone for order-independence — also green).
- Bare `python scripts/verify.py` (not `--tag static`) run in progress at time of writing.

## Honest scope notes (per investigation.md §7)

- The fast-init branch is unreachable under every runner in this repo today (no CI job, no test, no compose profile sets the flag). These are latent-trap fixes, not observed-leak fixes. Framed that way in each test's docstring.
- No browser/Playwright regression check was run against a live deploy for this change specifically: the edited code paths only execute when `APP_FAST_INIT=1`, which nothing in normal runtime (including `tests/smoke/`) sets — so a browser check would exercise unchanged code and prove nothing about this fix, consistent with investigation.md §7's own caution against overclaiming that evidence.

## Two new findings, not fixed here (see investigation.md builder addendum)

- **Finding A**: `models.py`'s own fast-init alias branch crashes today on a pre-existing `TechnologyStack` double-mapping (unrelated file, out of Task 1-3 scope). Documented as a known-red test rather than silently dropped.
- **Finding B** (higher priority): `Outcome` has no `TenantMixin` in *either* branch — a live, currently-active tenant-scoping gap on an actively-written model, not a dormant fast-init trap. Recommended as its own separate, higher-priority bucket given it needs the same nullable-override + backfill-command treatment as `Principle`, not a quick mixin add.

## Handoff target

**refuter** — per the original brief: (a) is each new test genuinely capable of failing (demonstrated: yes, shown red above); (b) is severity framed honestly in both directions (yes — explicit "trap not leak" language, and Finding B is explicitly flagged as more severe, not downplayed); (c) did each change stay inside its one-class scope (yes — `ApplicationComponent` explicitly did not receive `OptimisticLockMixin`).
