# Business Architecture — what shipped overnight, and how to demo it

**Written 21 Aug 2026, overnight session.** Everything below is deployed to
production and verified there by loading the page in a real browser, not by
trusting tests. Where something is not done, it says so.

---

## The one-paragraph version

The evaluation concluded that capability maturity, gap analysis and
strategy-to-execution "do not exist". They do — **350 routes** already serve the
12 outputs asked for, and exactly **one** (organisation & ownership) was genuinely
missing, and even that turned out to exist. The real defect was that a business
architect's persona had **4 sidebar links** and the single maturity link pointed
at a page whose statistics query had been gutted, so it rendered blank. That is a
discoverability problem, not a capability gap, and it is now fixed: there is a
Business Architecture front door listing all twelve outputs, a capability
line-of-sight view that answers a leader's three questions, and revocable share
links so an artefact can reach people who will never log in.

---

## Demo path (production, ~5 minutes)

1. **`/business-architecture/`** — the front door. Twelve outputs, grouped as
   *what the business is / how well it runs / where it goes next*, each stated as
   the question it settles for a business leader. It is also in the sidebar under
   **My work → Business Architecture**.
2. **`/capability-maturity/heatmap`** — current vs target on the 1–5 scale.
   It opens honest: *"Assessed 0 / 219 · Not assessed 219 — shown as — below, not
   as Level 1"* and *"nothing on this page is inferred."*
3. **Click any capability name** → the **line-of-sight** view. Three questions
   above the fold: *How good are we? Who owns it? What are we doing about it?*
   Where there is no answer it says so — "No owner recorded. Nobody is
   accountable for closing its gap." / "No initiative is currently improving this
   capability."
4. **Assess two or three live** via *Edit assessment*. Verified end to end:
   submitting sets `current`, `target`, the computed `gap`, **and**
   `maturity_assessment_date`. Return to the heatmap and they light up on the
   colour scale with coverage moving off zero. **This is the moment of the demo.**
5. **`/share/artefacts`** — generate a read-only link, open it in a private
   window. No login, no sidebar, no edit controls. Revoke it and it 404s.

**Which organisation matters.** Org 1 holds 191 capabilities that are all
capability *tiers* (operational/tactical/supporting). Org 7 holds 51 that are all
business *domains* (Finance & Controlling, Sales & Channel Management,
Manufacturing Operations…). **For a commercial-leadership conversation, demo
org 7** — org 1 tells the wrong story.

---

## What was actually broken, and is now fixed

| | Found | State |
|---|---|---|
| Composer autosave | Duplicate `element_id` violated `uq_diagram_element`; unhandled `IntegrityError` → 500; the client retried the identical payload forever, so work was **never saved** while the UI said "retrying" | Fixed, 5 tests |
| PDF export | Existed already; past the browser canvas limit it embedded `"data:,"` and emitted a **blank PDF**; page size was the raw canvas in mm (a 635mm sheet) | Fixed; verified producing a real 61,728-byte A3 landscape PDF |
| Maturity data | **270 of 270** capabilities carried `current=1, target=3` from column defaults while **0** had ever been assessed — a gap analysis nobody performed | Defaults removed; production backfilled to NULL, backed up and reversible |
| Frameworks page | Statistics query gutted (built a placeholder string, discarded it) → blank page. Then reported "Avg Current **0.0**" — not a value on a 1–5 scale | Both fixed |
| Framework taxonomy | 41 capabilities across 8 business-named domains matched no framework — exactly the domains a commercial leader looks for | Mapped as aliases; **242/242** now resolve |
| Dashboard health score | Two of four components used fake denominators (`max(len(x), 1)`, `or 1`), so nothing-to-measure became a confident 0% feeding the headline "21 HEALTH SCORE" | Components are `None` when unmeasurable; composite re-weights over what remains |
| Business architect nav | 4 sidebar links vs 13 for enterprise architect; the one maturity link led to the blank page | 17 links; maturity points at the working heatmap |
| Sharing | No external sharing of any architecture artefact existed | Revocable read-only links, public page verified anonymously |

---

## Things to know

**The public share page is deliberately a summary.** With nothing assessed it
rendered 219 rows of em dashes over 12,000px. Accurate, unreadable. It now states
the position instead. When assessments exist, the tables render.

**`enterprise_architect` did not get the Business Architecture sidebar link.**
`sidebar-links` is a ratchet at 26 and that role was already exactly on it.
Raising a ratchet is a regression, so it was backed out. EA already reaches
capability map, gap analysis, work packages, traceability, capability health,
roadmaps and data architecture directly, and `platform_admin` — the default role
for anyone who never picked one — does carry the link. Give EA the link in the
same change that retires one of its 13 my-work links.

**`scripts/deploy.sh` now waits 30 minutes, not 15.** A perfectly healthy deploy
was auto-rolled-back mid-boot; the droplet logs showed it working through the
value-stream backfill with no error, and it served 200 about four minutes after
the old bound gave up. An auto-rollback reads as "the new code is broken", so
that false alarm was expensive.

**A temporary verification account exists on production, disabled.** User id 38,
`disabled+…@example.com`, password scrambled, `confirmed=false`, re-tested to
confirm it cannot log in. It was **disabled rather than deleted** because
`soc2_audit_log` holds a foreign key to it, and deleting audit rows to tidy up a
test account is the worse outcome.

---

## Not done — the honest list

- **`enterprise_architect` sidebar link** — see above; needs a link retired first.
- **AI write-approval (D1)** — the human approval UI already exists (approvals
  modal, persisted queue, `approve_and_execute` is the only write path). What is
  outstanding is making it universal: a session flag `agent_auto_execute` can
  bypass it, and coverage is per-tool. Before any AI writes maturity, close that.
- **Unscoped tenancy models** — `UnifiedCapability`, `BusinessDomain` and
  `UnifiedWorkPackage` have **no `organization_id` column at all**, so no
  predicate can scope them. The public share views deliberately avoid them and
  read `BusinessCapability`/`CapabilityRoadmap` instead, but the *logged-in*
  capability map and roadmap still read them. Pre-existing, and a real gap.
- **Five orphan blueprints** (`journey_v2_bp` at 91 routes leading) — register or
  delete, per the A3 scan in the diligence register.
- **`broken-surfaces` is red at 8** and is **not** in `--tag static`, so a green
  static run does not cover it. Pre-existing. `--update-baseline` tries to raise
  it 0 → 8; never accept that.
- **pytest-randomly ordering** surfaces a fixture teardown interaction. Tests pass
  individually and in deterministic order. Pre-existing.

---

## Guardrails added, so this cannot silently recur

- **`nav-coverage`** — a `verify.py` ratchet counting outputs that have routes but
  appear in no persona's sidebar. Baselined at the true measured **4**, not an
  aspirational 0. This is the gate that would have caught the original problem:
  nothing failed when the maturity module became unreachable.
- **`scripts/ba_output_audit.py`** — the 12-output audit, with `--count` feeding
  the gate.
- **`scripts/ba_design_audit.py`** — loads each screen in a browser and reports
  content fill, grids rendering fewer items than columns, overflow and near-empty
  pages. Thirty-one green gates said nothing about a card marooned in a
  four-column grid; this does.
- **`scripts/ba04_verify_pdf.py`** and **`scripts/ba02_verify_heatmap.py`** —
  browser verification of the PDF export and the heatmap against a running site.
