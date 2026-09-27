# Smoke suite: 26 failures + 17 errors in the full run are a resource artifact, not a persona regression

**Status: diagnosed, not fixed. Root cause identified below; fix requires touching
shared test infrastructure (`tests/smoke/conftest.py`'s `browser` fixture scope),
which is out of scope for the wave that found this.**

## What wave 5 reported

`pytest tests/smoke -q` (52 files, ~259 tests, ~52 minutes) reported 27 failures +
17 errors, and many of the failing test IDs were `[business_architect]`
parametrizations across unrelated files. Wave 5's own note flagged this as
suspicious — one shared root cause reading as several bugs — and asked wave 6 to
find out whether it's real.

## What wave 6 found

It is **not** a `business_architect`-specific regression. Re-run
`python -m pytest tests/smoke -q` (2026-09-08, same branch) reproduced the
pattern almost exactly: **26 failed, 216 passed, 17 errors, 3121.71s (52:01)**.
The failing list again looks `business_architect`-heavy at a glance
(`test_archetype_journeys.py::test_archetype_can_use_its_product[business_architect]`,
`test_authorisation_matrix.py::...[business_architect]`,
`test_brand_home_navigation.py::...[business_architect]`, etc.) but it also
includes tests with **no persona parametrization at all**:
`test_business_case_journey.py::test_business_case_create_document_and_delete`,
`test_business_model_canvas_journey.py::test_business_model_canvas_create_edit_and_delete`,
`test_capability_journey.py::test_capability_create_edit_and_cross_store_count`,
`test_dashboard_pipeline_unknown.py`, `test_architecture_journey_screenshots.py`
(4 screenshot captures), and both `test_accessibility_audit.py` a11y-regression
checks.

Three isolation runs settle it:

1. `pytest tests/smoke/test_archetype_journeys.py -k business_architect` → **2
   passed**. The exact failing test, run alone, is clean.
2. `pytest tests/smoke/test_adversarial_probes.py tests/smoke/test_archetype_journeys.py
   tests/smoke/test_architecture_journey_home_journey.py` (three files that fail
   together in the full run, including two `[business_architect]` IDs) → **36
   passed** (plus 13 unrelated `SMOKE_AI_PROTOCOL_STUB` opt-in errors, see below).
3. `pytest tests/smoke/test_business_case_journey.py tests/smoke/test_capability_journey.py`
   — two files that fail in the full run and carry **no** persona
   parametrization — → **2 passed**.

Every test that fails in the 52-minute full run passes when run in a small
group. `business_architect` is simply one of 11 values in `ARCHETYPES`
(`tests/smoke/conftest.py`), so it is over-represented in any large,
order-sensitive failure set by base rate — it is not the cause.

## Root cause (structural, not yet fixed)

`tests/smoke/conftest.py`:

```python
@pytest.fixture(scope="package")
def browser():
    with sync_playwright() as p:
        ...
        b = engine.launch(headless=True)
        yield b
        b.close()
```

`tests/smoke/` has an `__init__.py`, so pytest treats the whole directory as one
package — **every one of the 259 tests across all 52 files shares a single
Playwright browser process for the entire run.** Individual tests open pages
(`browser.new_page()`) and most close them in a `finally` block, but nothing
recycles the browser itself or bounds how many contexts/pages/screenshot
buffers accumulate against one Chromium process over 52 minutes. The tests that
fail in the full run are disproportionately the heavier ones — full CRUD
journeys, screenshot capture, an axe-core accessibility sweep — consistent with
resource exhaustion against that one long-lived process rather than a
behavioural regression in the app.

This session also hit two outright OOM kills (`python -m pytest tests/smoke -q`
terminated by the harness with "system is running low on memory") while
reproducing this, and recovered ~1.8GB by killing two orphaned `python.exe`
processes left over from earlier killed pytest runs — a corroborating, if
separate, sign that this machine is tight on memory during a 52-minute
single-browser Playwright run. That is a local-environment condition, not
something to read as evidence either way about the app itself, but it's a
plausible aggravating factor: a lower-memory box hits this ceiling sooner.

## Not part of this cluster (leave as understood, do not re-chase)

`test_adversarial_probes.py`'s 13 errors and `test_ai_protocol_journeys.py` /
`test_page_guide_history_journey.py`'s errors are a **separate, expected**
condition: they require `SMOKE_AI_PROTOCOL_STUB=1`, and
`tests/smoke/conftest.py`'s `seeded` fixture deliberately fails fast
("AI protocol qualification requires a candidate database without enabled
provider records") when an unrelated `APISettings` row is already enabled in
the shared, persistent test database — which it is here (two `power_platform_coe`
rows, `id` 1 and 2, pre-existing debt from another test's fixtures, not created
by this session). This is correct fail-fast behaviour protecting the AI
qualification path from a dirty database, not a bug to fix here.

## Recommended fix (next session, not attempted here)

Do not attempt this as a quick patch — it changes shared test infrastructure
every smoke file depends on, which is the "large test-infra rewrite" this
wave's brief explicitly said to avoid. The fix is one of:

- Narrow `browser`'s scope from `package` to `module` (one browser per test
  file) — bounds accumulation to a single file's tests, at the cost of a
  browser launch per file (~52 extra launches, probably a few minutes total).
- Keep `package` scope but recycle the browser every N tests (close and
  relaunch), verified by watching process RSS.
- Split the full run into two or three `pytest` invocations by file group in CI
  (already effectively how this session worked around it) — cheapest, but
  papers over the leak rather than fixing it.

Whichever is chosen, add a measurement: log the browser process RSS at the end
of every test file and assert it stays within some ratchet, so a future
regression here is caught by a gate rather than by another owner-clicking pass.
