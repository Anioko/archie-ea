# What would earn a yes from a demanding product reviewer

Written 21 Aug 2026. Every number here is measured against **production**, not
estimated.

---

## The one number that decides it

```
748  tables in the schema
 64  tables that contain a single row        (8.6%)
684  tables that have never held data        (91%)

3,466 routes
1,110 GET pages with no parameters
   24 users
    5 organisations
```

Real content across the whole estate: **603 ArchiMate elements, 270 capabilities,
44 applications, 12 solutions.** And **0 of 270 capabilities have ever been
assessed.**

A demanding reviewer does not ask "what else does it do". They ask *"why does a
product with 24 users need 1,110 pages?"* — and there is no good answer. Breadth
is not the asset here; it is the liability. Every unvalidated page is surface
that has to be maintained, secured, and explained, and this session proved the
cost: three features the evaluating architect declared missing were built and
unreachable, two unauthenticated blueprints sat undeleted, and the largest number
on the landing page was computed from denominators that did not exist.

**The yes does not come from adding. It comes from deleting, then proving one
loop end to end.**

---

## The five tests, and what good looks like

### 1. One job, done better than the alternative it replaces

The alternative is not a competitor. It is **PowerPoint and Excel** — Iain built
his capability map and maturity assessment by hand, and they work.

| | Bad | Good |
|---|---|---|
| Test | "It has capability maps" | A named user does their real job here and will not go back |
| Measure | features shipped | **Iain produces his next capability review in Archie, from scratch, in under an hour, without asking for help** |

**Tasks**
- **T1** Sit with the real workflow end to end: import or enter capabilities →
  assess → produce the artefact leadership sees. Time it. Every step that takes
  longer than the Excel equivalent is a defect, recorded as one.
- **T2** Bulk assessment that a human can actually finish. 270 capabilities at
  one form each is not a workflow. `/capability-maturity/batch-update` exists —
  prove it handles 50 in one pass, or fix it.
- **T3** Import the estate from a spreadsheet, because that is where every real
  capability model already lives. **Good = a CSV of 270 capabilities lands
  correctly in under a minute, with a dry-run diff shown before commit.**

### 2. Nothing on screen that is not true

This is the one where a sceptical executive kills the product in a single
glance, and it is the closest to being met.

| | Bad | Good |
|---|---|---|
| Test | "the numbers look plausible" | Every unknown is visibly unknown, and the reader can tell why |
| Measure | no fabrication gate | **`broken-surfaces` at 0 and inside `--tag static`; no `or 0`, `or 1` or `.get(k, 0)` in any metric path** |

**Tasks**
- **T4** Fix the 8 `broken-surfaces` findings and **add the gate to
  `--tag static`**. Today it is red at 8 and outside the tag, so every "31 gates
  green" this session did not cover it. `--update-baseline` tries to raise it
  0 → 8; never accept that.
- **T5** Sweep every remaining fake denominator. The pattern `or 1`, `max(x, 1)`,
  `.get(key, 0)` in a metric path is a fabricated measurement. Three were found
  by hand this session; a checker would find the rest.
- **T6** Close the AI write-approval bypass (`agent_auto_execute`). An AI writing
  maturity scores autonomously reproduces the 270-fabricated-rows failure at
  machine speed, into the system leadership is being asked to trust.

### 3. It is explainable in one sentence

| | Bad | Good |
|---|---|---|
| Test | "TOGAF/ArchiMate platform with portfolio, ARB, codegen, AI…" | **"It keeps your capability model honest and shows leadership what to fix."** |
| Measure | 12 modules on the landing page | A new user reaches their first real answer in **under 3 minutes, unaided** |

**Tasks**
- **T7** Quarantine the unvalidated half. `codegen` (41,065 lines) and
  `solutions_product` (17,549) sit behind no flag and are supported by no user.
  Move them behind an experimental flag or into a separate repository.
  **Good = routes drop from 3,466 to under 1,000 and no user notices.**
- **T8** Delete or register the 5 orphan blueprints (`journey_v2_bp` alone owns
  91 unreachable routes).
- **T9** Retire the 7 duplicated v1/v2 domains per ADR-0004.

### 4. It survives being handed to someone else

| | Bad | Good |
|---|---|---|
| Test | it demos well when you drive | **A stranger with the link reaches the answer with no training and no account** |
| Measure | "we'll walk them through it" | Leadership consumes the artefact without ever logging in |

**Tasks**
- **T10** Share links exist and are verified. Next: **the artefact has to be
  worth receiving.** A one-page view per business area — how good are we, who
  owns it, what are we doing — not a table dump.
- **T11** Scheduled delivery. A capability review that arrives monthly beats one
  someone has to remember to open.
- **T12** First-run experience. **684 empty tables means empty is the default
  first impression.** A seeded demo tenant, so a new org sees a working model in
  10 seconds rather than a blank grid.

### 5. It is fast, and it does not lose work

| | Bad | Good |
|---|---|---|
| Test | "it works on my machine" | p95 page render **< 500ms** with 10× the current data |
| Measure | no numbers | Published latency budget, enforced by a gate |

**Tasks**
- **T13** Load-test at 10× (2,700 capabilities, 6,000 elements). The N+1 at
  `application_fact_sheet.py` and the `lazy="dynamic"` relationships will surface
  here before a customer finds them.
- **T14** Move imports and LLM generation onto the RQ worker. Inline execution on
  3 gunicorn workers means three concurrent imports take the site down — on a
  2-vCPU box that is not hypothetical.
- **T15** Autosave data loss is fixed; **prove it stays fixed** with a browser
  test in CI, not a source-shape assertion. That bug shipped for months and no
  gate saw it.

---

## The honest answer to "when"

Not at a feature count. The yes comes when **one named user does one real job
here, faster than the tool they use today, and the output travels to their
leadership without them.** That is T1–T3 plus T10.

Everything else on this list is what makes that credible rather than a demo:
truth (T4–T6), simplicity (T7–T9), and speed (T13–T15).

On current evidence the fastest route is:

1. **T3** import — because 270 hand-typed assessments is where this dies
2. **T2** bulk assess — the same reason
3. **T10** the one-page leadership artefact — the thing that leaves the building
4. **T7** delete the unvalidated half — because 1,110 pages for 24 users is the
   first question a serious reviewer asks, and there is currently no answer

Those four, in that order. The rest is maintenance of the promise.
