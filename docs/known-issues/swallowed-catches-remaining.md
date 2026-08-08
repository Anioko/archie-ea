# Catch blocks that still tell nobody

**Measured:** 2026-08-08, by `scripts/check_broken_surfaces.py --kind swallowed`

A four-agent triage took the `broken-surfaces` count from **442 to 167**. This
records what is left, so the ratchet number is not mistaken for completion.

## Where the 167 sit

| Class | Count | Status |
|---|---|---|
| `dead-link` | 0 | fixed |
| `dead-fetch` | 1 | a documented placeholder endpoint |
| `forbidden-ui` | 0 | fixed |
| `orphan-page` | 13 | product decision — see [unreachable-pages.md](unreachable-pages.md) |
| `swallowed` | 153 | **80 triaged and annotated, 73 still bare** |

## The 80 annotated ones

These were examined and deliberately left silent: Alpine `$store('loading')`
start/stop toggles, `$store.announcer` mirrors, `localStorage` reads and writes
(which throw in private mode), debounced search-as-you-type, optional AI and
telemetry enrichment, and defensive `JSON.parse` of our own server-rendered
data. Each now carries a comment saying why.

**The checker cannot tell these from neglect, so they still count.** The repo's
convention for exactly this is a reviewable per-line marker — `fabricated-ok:`,
`air-gap-ok`, `tenancy-ok:`. A `swallow-ok: <reason>` hatch would let these 80
be excluded on purpose and give the gate a route to zero. That is the next
piece of work, and it is deliberately not done here: adding the hatch without
converting the comment sites would change nothing, and converting ~80 sites is
its own reviewable change rather than a rider on a deploy.

## The 73 bare ones

No comment, no toast, no log. Each is either a real silent failure or a
deliberate one nobody has written down — and from the outside those look
identical, which is the whole problem. The concentrations:

| File | Count |
|---|---|
| `app/static/js/archimate/composer.js` | 20 |
| `app/static/js/archimate/composer_persistence.js` | 16 |
| `app/static/js/codegen/workbench.js` | 14 |
| `app/static/js/architecture_assistant/journey_v2.js` | 8 |
| `app/static/js/architecture_assistant/architecture_journey.js` | 8 |

(Counts are per-file totals across both groups; the composer and workbench
files were triaged, so most of their remaining hits are annotated.)

Three in `app/static/js/vendor/jquery.min.js` are third-party and will never be
fixed here; they are a further argument for the `swallow-ok:` hatch, or for
excluding `vendor/` from this class outright.

## Why this is ratcheted rather than gated at zero

Triage is real work and it is judgement work — the wrong fix is to toast every
one of them, which buries the failures that matter under noise from
`localStorage` probes. The ratchet in `verification_baseline.json` means the
number cannot **grow** while the rest is worked through.
