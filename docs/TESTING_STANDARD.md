# Archie testing standard

This is the bar every change is held to, and the reason each level exists. It is
written because a wave shipped with 47 green gates and a page that a user
immediately found broken — the gates were all true and none of them were looking
at what he was looking at.

**The distinction this document exists to enforce:** *quality assurance* asks
"does this break?", *product testing* asks "can a person achieve their goal, and
does the path make sense?" A screen can pass every gate in levels 0–7 and still
be a workflow nobody can use. Levels 8–10 are where that is caught. A wave that
reports only levels 0–7 is reporting half the truth, however green it is.

## The levels

| L | Question | Enforced by |
|---|---|---|
| 0 | Does the code load at all? | `compile`, `undefined-exports`, `boot-health` |
| 1 | Will it raise at runtime? | `undefined-names`, `redefinitions`, `lint-core`, `macro-kwargs` |
| 2 | Does every surface render? | `template-syntax`, `template-references`, `broken-surfaces` |
| 3 | Does the front end actually run? | `js-syntax`, `alpine-await`, `attr-quoting`, `console-reporting` |
| 4 | Does it look right at a real viewport? | `production_readiness_audit.py` L4 (dead space, overflow) |
| 5 | Can the controls be used, by anyone? | `control-labels`, `input-labels`, `csrf-coverage`, axe in CI |
| 6 | Is the data honest? | `fabricated-data`, `null-filters`, `silent-data`, `error-signalling` |
| 7 | Is it safe and tenant-correct? | `tenant-scoping`, `raw-sql-tenancy`, `dependency-cves`, `sri`, `air-gap` |
| 8 | Does a unit of behaviour do what it claims? | `pytest` — 3300+ tests |
| 9 | **Can each archetype complete their real job?** | `tests/journeys/`, archetype walkthroughs |
| 10 | **Is the journey worth completing?** | human/agent product review — see below |

Levels 0–8 are machine-checkable and gate every commit. **Levels 9 and 10 are the
ones that get skipped under time pressure, and they are the ones the owner
notices.**

## What Level 9 requires

A journey test asserts an **outcome**, not a status code. The difference:

```python
# NOT a journey test. This passes while the feature is unusable.
resp = client.get("/capability-analysis/unmapped")
assert resp.status_code == 200

# A journey test: the user's goal actually happened, and is visible afterwards.
client.post("/capabilities/create", data={...})          # do the work
row = db.session.scalar(select(Capability).filter_by(name=NAME))
assert row is not None                                    # it persisted
page = client.get("/capability-analysis/unmapped")        # and it shows up
assert NAME in page.get_data(as_text=True)                # where the user looks
```

Every archetype in `PERSONAS` (see `scripts/production_readiness_audit.py`) needs
at least one journey covering: **find the surface → do the work → confirm it
persisted → confirm it is visible where the user would look next.**

## What Level 10 requires

Judgement a machine cannot make. Run as an archetype walkthrough, in a browser,
answering:

- **Discoverability.** Could the user find this *without reading the source*? If
  finding a page required grepping for a URL, it is broken for real users, even
  though every gate is green.
- **Coherence.** Does the sequence follow, or does it jump between unrelated
  screens? Is there a next action on every screen, or does it dead-end?
- **Honesty of numbers.** Cross-check displayed figures against the database. A
  plausible-but-wrong number is worse than a blank: the user cannot tell, and
  acts on it.
- **Verdict per step**: WORKS WELL / WORKS BUT POOR / BROKEN, with evidence.

## Rules that are not negotiable

1. **A `SKIP` is not a `PASS`.** Skipped gates are printed separately precisely so
   they cannot be read as green.
2. **Only a bare `python scripts/verify.py` means clean.** Any `--tag` or `--gate`
   run prints `PARTIAL RUN` and lists what it did not run. A tag subset was how
   `broken-surfaces` sat red on deployed main.
3. **Measure, do not photograph.** A screenshot that grows to fit its content
   cannot show a page with dead space below it — that is how a layout defect
   reached the owner. Assert geometry at a fixed viewport.
4. **Test as a non-admin.** An admin session masks every authorisation defect.
   Two 403s that broke real pages were invisible until the walkthrough re-ran as
   a normal architect.
5. **Re-measure after every fix.** Three times in one session a fix introduced a
   new defect — a repaired query exposed raw `None`s, a new search control killed
   its own page. The audit caught all three; assumption caught none.
6. **A found defect is fixed, not documented.** See the `docs/known-issues/`
   section of `CLAUDE.md`: writing it down converts a bug into a bug *plus* a note
   that the next person reads as a deliberate decision.
7. **Every new gate is proven against known-bad input.** Reintroduce the defect,
   watch the gate go red, restore, watch it go green. A checker nobody has seen
   fail is just a number.
8. **A gate with false positives is worse than no gate**, because it gets ignored.
   Teach the rule (a control named by `x-text` at runtime *is* named); never
   hardcode a filename allowlist, which rots silently.

## Adding a gate

New defect class found in production or review → add the gate in the same wave,
not the next one. Follow `scripts/check_macro_kwargs.py` as the model: docstring
citing the concrete defect, `--count` with the count as the trailing line,
`--root`, and a per-line escape hatch so an exception is reviewable rather than
silent. Register it in `scripts/verify.py`'s `build_gates` as a ratchet, and add
its baseline to **both** `DEFAULT_BASELINE` and `verification_baseline.json` —
a gate missing from the JSON passes locally and enforces nothing in CI.

Note `.gitignore` blankets `scripts/check_*.py`; stage a new checker with
`git add -f`.

## Running levels 9 and 10

Level 9 is a gate. `journey-coverage` reads the persona list out of
`app/models/user.py`'s `VALID_ROLES`, so adding a persona to the product
automatically demands a journey for it rather than silently passing:

```bash
python scripts/check_journey_coverage.py     # which personas are uncovered
pytest -m journey                            # run the journeys themselves
```

Level 10 is not a gate — it needs a running server and a seeded tenant, and
its output is a judgement per step, not a number. Run it against the
deployment you are about to ship:

```bash
python scripts/walkthrough_archetypes.py                     # :5001 by default
WALKTHROUGH_BASE_URL=https://... python scripts/walkthrough_archetypes.py
```

It drives real Chromium at a fixed 1440x900 viewport as a **non-admin** user
per archetype, measures geometry rather than photographing it, fails a step on
any console error, and — the part no gate covers — checks that the archetype
could have **found** the page. On its first run every gate was green and the
CTO still had no link to the technology radar they are authorised to set.
