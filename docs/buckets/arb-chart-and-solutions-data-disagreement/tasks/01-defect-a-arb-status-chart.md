# Task A — ARB "Review status" donut renders as a solid black, oversized ring

**Bucket:** `arb-chart-and-solutions-data-disagreement`
**Severity:** Critical (UX_IA_REVIEW.md finding #1)
**Handoff target:** `builder` → `refuter`

---

## Objective

Make the Architecture Review Board dashboard's "Review status" donut render with
its three real semantic colours (warning / success / destructive) at a capped
height, instead of the single solid-black ~700px ring seen on production at
every width and theme.

## Context

**Screen:** `/arb/` → `arb.dashboard` (`app/modules/architecture/routes/arb_routes.py:685`),
template `app/templates/arb/dashboard.html`.

**Evidence:** `UX_IA_REVIEW.md` finding #1 — screenshots
`16_review_board_light_1440.png`, `16_review_board_light_768.png`,
`16_review_board_dark_1440.png`, all identical (bug is neither theme- nor
width-dependent), in the review's scratchpad shots directory.

### Root cause — determined by code reading, not assumed

`app/templates/arb/dashboard.html` contains **two** copies of the same donut
initialiser in `{% block extra_head_js %}`, on mutually exclusive Jinja
branches:

- lines 155–204, rendered when `typed_queue` exists and its state is not
  `failed` (`{% if _typed and _typed.state != 'failed' %}`)
- lines 205–255, rendered when there is no typed queue (`{% if not _typed %}`)

They differ in exactly one respect — the `backgroundColor` array:

| Branch | line | `backgroundColor` |
|---|---|---|
| typed (**the one production serves**) | 181–186 | `['hsl(var(--warning))', 'hsl(var(--success))', 'hsl(var(--destructive))', 'hsl(var(--muted-foreground))']` |
| non-typed | 239 | `['#f59e0b', '#10b981', '#ef4444', '#9ca3af']` |

`hsl(var(--warning))` is a **CSS** expression. It is being handed to Chart.js as
a **JavaScript string**, where it is parsed by `@kurkle/color`, not by the CSS
engine. `var(...)` is not resolvable outside a CSS property value, so the parse
fails, and Chart.js falls back to its default fill — black. Every segment gets
the same unparseable value, so all four collapse to one black ring. That is a
precise match for the reported symptom, and it explains why the non-typed branch
(literal hex) has never been reported broken: **the typed branch is what the QA
tenant renders.**

The repo already has the correct pattern for this and it is not being used here.
`app/static/js/capability_map/maturity_radar.js:26-30` (and
`app/static/js/capability_map/investment_bubble.js:39`) define:

```js
function cssHSL(varName, alpha) {
    var raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
    if (!raw) return null;
    return alpha !== undefined ? 'hsl(' + raw + ' / ' + alpha + ')' : 'hsl(' + raw + ')';
}
```

That resolves the custom property to its raw `H S% L%` triplet at runtime and
builds a real colour string. Every other `hsl(var(--…))` occurrence in
`app/templates/` is inside a `<style>` block (valid CSS); the four in
`arb/dashboard.html` lines 182–185 are the only ones in a JS literal.

**Second, independent symptom — the ~700px height.** The canvas at line 114
carries `height="160"`, but the chart options set `responsive: true` with
`maintainAspectRatio: true` (lines 192–193). In responsive mode Chart.js
overrides the canvas `height` attribute and sizes from the container's width;
with `maintainAspectRatio: true` and a doughnut's default aspect ratio of 1, a
canvas in the `min-w-[200px] flex-1` container (line 113) becomes a square as
tall as it is wide — hence ~700px at 1440px and no narrowing at 768px. The
`height="160"` attribute is inert. Fixing the colours alone will leave a
correctly-coloured but still oversized ring; both must be fixed.

## Constraints

- **Extend the existing component, do not add a new one (ADR 0008).** The chart
  belongs to `app/templates/arb/dashboard.html`'s ARB dashboard. Reuse the
  existing `cssHSL` token-resolution pattern from
  `app/static/js/capability_map/maturity_radar.js` — preferably by lifting it to
  a shared helper both callers use, rather than pasting a third copy. If you
  lift it, both existing call sites must be repointed in the same change; do not
  leave two ways to resolve a chart token.
- **The two duplicated initialiser blocks are themselves an ADR 0008 defect** —
  one concept, two accessors that have already drifted (one has correct colours,
  one does not). Collapse them to a single block that renders on both branches,
  rather than fixing the typed copy and leaving the divergence in place. That
  divergence is the mechanism by which this shipped.
- **No raw Tailwind colour families** — the `design-tokens` /
  `design-tokens-extended` gates are ratcheted at 0. Resolve
  `--warning` / `--success` / `--destructive` / `--muted-foreground` from
  `app/static/css/shadcn_tokens.css`; do not replace them with hex literals. (The
  non-typed branch's hex array is pre-existing debt — converting it to tokens as
  part of collapsing the duplicate is in scope and preferred.)
- **Do not remove the `if (!ctx) return;` guard or the `DOMContentLoaded`
  wrapper.** Both carry in-file comments recording a real 11 Sep 2026 production
  defect (script runs in `<head>`, canvas is in `<body>`). Re-breaking that is a
  regression.
- **Do not invent data.** The `other` bucket (`total - pending - approved -
  rejected`) is already clamped at 0; leave that arithmetic alone.
- `app/static/vendor/chart.umd.min.js` is vendored and air-gapped — do not load
  Chart.js from a CDN (`air-gap` gate, ratcheted at 0). Note it is currently
  `<script src>`-ed twice across the two branches; collapsing the blocks should
  leave exactly one include (`asset-urls` gate flags a script included twice).
- No `console.*` in shipped templates (`console-reporting` ratchet at 0).

## Deliverable

1. `app/templates/arb/dashboard.html` — a single donut initialiser serving both
   the typed and non-typed branches, with segment colours resolved from CSS
   custom properties at runtime and a capped chart height.
2. Height cap: wrap the canvas in a fixed-height container (~`220px`, per the
   review's suggestion) **and** set `maintainAspectRatio: false`, so the chart
   fills that box rather than squaring off against its width. Setting only one of
   the two will not cap it.
3. Shared token-resolution helper (if lifted) with both capability_map call sites
   repointed.
4. Tests:
   - A unit/DOM-level test asserting the resolved `backgroundColor` array
     contains four **distinct, parseable** colour strings and no literal
     `var(` substring — this is the assertion that would have caught it.
   - Extend `tests/smoke/test_visual_regression.py`'s baseline matrix to include
     `/arb/`. The review notes this screen is not currently covered, and this
     defect class (DOM and accessibility tree intact, visually broken) is exactly
     what that gate was added on 13 Sep 2026 to catch. Accept the new baseline
     with `SMOKE_VISUAL_UPDATE_BASELINE=1` **only after** the fix is visually
     confirmed correct — never baseline the broken state.
5. `tests/smoke/` touch is mandatory anyway: the `smoke-coverage-on-change` gate
   fails a template change with no smoke test in the same diff.

## Acceptance criteria

- **Live browser repro captured before the fix** (standalone Playwright script,
  same approach as the UX review — the claude-in-chrome extension is
  unavailable): load `/arb/` as a persona whose tenant has
  `dashboard_data.metrics.total_items > 0`, capture the black ring, and record
  the browser console. Note that a `@kurkle/color` parse failure is **silent** —
  expect no console error; absence of an error does not disconfirm this root
  cause. The before-screenshot is the evidence, not the console.
- After the fix, the same script shows four visually distinct segments whose
  colours match the legend's semantic meaning (pending/approved/rejected/other),
  at 1440×900 and 768×1024, in both light and emulated dark `prefers-color-scheme`.
- Chart occupies no more than ~240px of vertical space at 1440px width, and the
  legend sits beside it at desktop and remains on-screen at tablet width.
- Verified on **both** template branches — a tenant with a typed ARB queue and
  one without. The typed branch is the one that was broken; do not verify only
  the branch that already worked.
- `python scripts/verify.py` (bare, not `--tag static`) green. Per CLAUDE.md, a
  filtered run prints `PARTIAL RUN` and its green does not mean clean.
- Zero-review tenants still render the server-side `empty_state` at
  `data-testid="arb-empty-status-chart"`, not an empty canvas.

## Handoff target

`builder`, then `refuter`. Refuter must independently re-run the browser check
rather than accepting the builder's screenshots — per CLAUDE.md, the builder is
never the sole verifier.
