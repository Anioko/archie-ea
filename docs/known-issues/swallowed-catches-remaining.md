# Catch blocks that told nobody — resolved

**Measured:** 2026-08-08. **Closed:** 2026-08-08.
Checker: `scripts/check_broken_surfaces.py`.

`broken-surfaces` went **442 → 0**. Every class is now zero and the ratchet in
`verification_baseline.json` is set to 0, so this is a must-be-clean gate rather
than a "no worse" one.

| Class | Start | End |
|---|---|---|
| `dead-link` | 5 | 0 |
| `dead-fetch` | 9 | 0 |
| `forbidden-ui` | 2 | 0 |
| `orphan-page` | 13 | 0 — see [unreachable-pages.md](unreachable-pages.md) |
| `swallowed` | 413 | 0 |

## What "zero" means here, precisely

It does **not** mean every catch block now shows a toast. Toasting a
`localStorage` probe or a collaboration presence ping would bury the failures
that matter under noise, which is the failure mode that makes a checker useless.

Of the catches examined, **115** were judged deliberately silent and carry a
`swallow-ok: <reason>` marker — the same reviewable per-line hatch the repo uses
for `fabricated-ok:`, `air-gap-ok:` and `tenancy-ok:`. The reason must sit on
the marker's own line and begin with a word character; an empty marker is
rejected, so the hatch cannot be used as a silent mute.

Legitimate categories, each represented in the markers: cosmetic JointJS
highlight/unhighlight calls, `localStorage`/`sessionStorage` access that throws
in private mode, defensive `JSON.parse` of our own server-rendered data,
collaboration presence pings and background auto-detect the user never
requested, advisory copilot hints, debounced search-as-you-type, and parsing an
error body that may legitimately be HTML or empty where the real failure is
already reported on the next line.

The markers were audited rather than trusted: every one whose surrounding code
contained a `POST`/`PUT`/`PATCH`/`DELETE` was read individually. All were
fire-and-forget advisories or error-body parses, none a user's save.

## Why the gate could not previously reach zero

A deliberately silent catch and one nobody looked at are indistinguishable from
outside — which is the entire defect this class exists to find. Before the
hatch existed, a fully triaged file still counted, so 85 already-annotated
catches sat in the number looking like debt and the gate could only ever be a
ratchet. Prose in a comment reads as intent to a human and as neglect to a
checker; a marker reads as intent to both.

## Two exclusions, both deliberate

- **`app/static/js/vendor/`** is not scanned for this class. Editing a vendored
  minified bundle to satisfy our own checker would change its SRI hash, which
  the `sri` gate would then fail — the fix and the gate in direct conflict.
- **`components/modal_standardized.html`** is reference documentation for the
  `Platform.modal` pattern and no page includes it. Its example endpoint was the
  string `'/api/endpoint'`, indistinguishable from a real call to a route that
  does not exist, and it held `dead-fetch` open at 1 — a gap a genuine dead
  fetch could have hidden behind. It is now an undefined constant, so copying
  the pattern without substituting a real endpoint fails loudly.

## What this did not cover

The checker finds catch blocks that are *empty* (or console-only). It cannot see
a catch with a non-empty body that still reports nothing to the user — for
example `catch (e) { this.items = []; this.loaded = true; }`, which renders a
failure as a legitimately empty list. Several of those were found and fixed by
hand during this work, but they were found by reading, not by the gate.

Known remaining instances of that shape, none of them in the checker's finding
set: `application_mgmt/vendor_analysis_detail.js` (3), `solutions/composition_wizard.js`,
`solutions/blueprint.js`, `capability_map/index.js`, `capability_map/nested_map.js`,
`framework_management/dashboard.js`, `applications/rationalization.js`.

Each needs a per-panel decision about where the error state renders rather than
a mechanical rewrite. That is the next slice, and extending the checker to catch
the shape is what would keep it from returning.
