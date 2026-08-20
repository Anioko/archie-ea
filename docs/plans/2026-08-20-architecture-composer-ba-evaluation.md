# Architecture Composer vs Iain's Business Architecture ask — evaluation, 20 Aug 2026

Hands-on evaluation of Architecture Composer against the artifacts Iain Burgess
asked for. Context: Iain has two artifacts already built by hand (a capability
map and a maturity assessment); the goal is a framework leadership can self-serve,
starting with those two, ahead of a **September meeting with Andy and the
commercial leadership team**.

**Verdict: strong ArchiMate modelling engine, not yet a leadership-facing product.**

## What genuinely works

- A first-class **Capability Map starter template** already chaining
  Goals → Capabilities → Courses of Action → supporting systems — close to the
  strategy-to-execution view asked for.
- **AI "Generate Architecture" is genuinely capable**: prompted for a "Commercial
  Ops capability map with maturity levels for Sales, Marketing, Customer Success
  and Pricing", it produced **33 elements and 42 relationships in ~10 seconds**,
  including goals, stakeholders, capabilities, business services and systems.
- Dedicated templates for data/information architecture, stakeholder concerns and
  service realization.
- **Relationship Matrix** with a built-in "potential gap" category, giving basic
  model-wide traceability.

## Two corrections found in the code — these shrink the work substantially

The evaluation reported maturity as absent. **It is not absent from the model.**

`app/models/business_capabilities.py:60-63` already carries a real 1–5 scale:

    current_maturity_level = db.Column(db.Integer, default=1)   # 1 - 5 scale
    target_maturity_level  = db.Column(db.Integer, default=3)   # 1 - 5 scale
    maturity_gap           = db.Column(db.Integer)              # calculated

So current state, target state and a computed gap all exist as first-class
columns. What is missing is **surfacing**: the Composer's capability element
exposes only the ArchiMate implementation `Status`
(Planned/Assigned/In Progress/Realized/Deprecated), the "Maturity" view toggle
renders nothing from these columns, and the AI generator never populates them —
which is why every capability came back "not set" even when maturity was
explicitly requested. This is a UI + generator-prompt job, **not** a modelling
job, and current-vs-target is exactly the "simple current-state-vs-target-state
view" the evaluation found missing elsewhere.

Similarly, `WorkPackage` **does** exist (`app/models/archimate_core.py`,
`archimate_element_types.py`) and is referenced by
`app/static/js/archimate/composer.js`. So "no Initiative/Work Package elements"
is likely a palette *discoverability* problem rather than a missing concept —
confirm before building anything new.

## Register

Owner-decision items are marked **OWNER** — per CLAUDE.md these are
product-direction questions with no technically-correct answer, and are Iain's
and the owner's to settle, not engineering's.

| ID | Task | Kind | Status |
|---|---|---|---|
| BA-01 | **Autosave fails on a freshly generated diagram** — `composer_persistence.js:255` raises "Auto-save failed after multiple attempts" after retry exhaustion. Data loss on exactly the AI-generated diagrams this workflow depends on. Reproduce, find the failing write, fix. | **P0 bug** | TODO |
| BA-02 | Surface `current_maturity_level` / `target_maturity_level` / `maturity_gap` on the capability element and make the existing "Maturity" view toggle render them (colour-coded heatmap). Columns already exist — this is presentation. | Engineering | TODO |
| BA-03 | Teach the AI generator to populate the maturity columns when asked. Today it silently ignores an explicit maturity request, which reads as "the tool cannot do it". | Engineering | TODO |
| BA-04 | **PDF export.** Toolbar offers PNG/SVG and a "Print Friendly" mode needing a manual browser print. A leadership artifact needs one button. | Engineering | TODO |
| BA-05 | **A shareable read-only link.** Today the only "share" is submitting to the ARB — a governance workflow, not a way to circulate a view. Needs an authz decision on scope (org-only vs tokened link). | Engineering + **OWNER** on scope | TODO |
| BA-06 | Confirm whether Work Package / Initiative is genuinely missing from the palette or merely undiscoverable, then fix accordingly. Do not build a new element type before checking. | Engineering | TODO |
| BA-07 | Business-audience generation mode: the generator pulled a database cluster and integration services into a commercial-ops capability map. Useful to an architect, noise to a sales leader. Constrain layers by audience. | Engineering | TODO |
| BA-08 | A one-page capability-to-strategy view and a curated "all Business Architecture" library view — today there is only a per-diagram canvas plus global element search. | **OWNER** (what leadership needs) | TODO |
| BA-09 | KPI/metric dashboard concept — no dashboard or tile view exists. Note `Metric` is already an ArchiMate motivation entity in this codebase, so check the model before designing. | **OWNER** then engineering | TODO |
| BA-10 | Products & services catalogue and policy/governance register views — only partially covered today (a `Service` element; a "Security Architecture" template touching constraints/policies). | **OWNER** on scope | TODO |

## Recommendation

Do not put the ArchiMate canvas in front of Andy and the commercial leadership
team in September. Use Archie as the **system of record** — it is genuinely good
at holding the structure and relationships — and put a **thin curated
presentation layer** on top for what leadership actually consumes: a maturity
heatmap on the real 1–5 scale, a one-page capability-to-strategy view, and a
clean PDF export.

Sequenced for the September deadline, the critical path is **BA-01 → BA-02 →
BA-03 → BA-04**: fix the data-loss bug, then light up the maturity data that is
already in the database, then make it exportable. That alone reproduces both of
Iain's hand-built artifacts inside the tool, which is the stated near-term goal.
Everything below BA-04 should wait for leadership to say what is useful — which
is Iain's own proposed sequence.
