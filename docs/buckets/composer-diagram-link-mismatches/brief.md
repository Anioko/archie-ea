# Task Brief: Composer Diagram-Opening Links Are Broken in Three Distinct Ways

## Objective
Fix every remaining place in the codebase where clicking to open a diagram
in the ArchiMate Composer fails to open the intended content. Founder
reported this a second time tonight after two prior fixes (PR #33, PR #36)
addressed only two of at least four broken entry points.

## Context
A full-codebase grep for every composer-opening link tonight found three
additional, previously-unknown, real defects — none introduced by tonight's
earlier fixes, all pre-existing:

**D1 — "Architecture Overview — Layered Viewpoint" card, dashboard overview.**
`app/templates/dashboards/overview.html:252` — a card literally titled
"Architecture Overview — Layered Viewpoint" showing "{elements} elements ·
{relationships} relationships across all ArchiMate layers" (the exact
wording/shape of the founder's original bug report — 444 elements, 159
relationships) has an "Open Composer" button with a bare, unscoped
`href="/archimate/composer"`. This is almost certainly the actual link the
founder has been clicking both times — it is the most prominent match to
the original report and was missed by both prior fixes (PR #33 fixed the
sidebar link, PR #36 fixed the per-layer tab buttons; neither touched this
card).
FIX: `href="/archimate/composer?viewpoint=layered"` — same pattern as the
other two already-fixed links tonight.

**D2 — canvas "sub-diagram drill-down" (GAP-CMP-011) opens the wrong viewpoint.**
`app/static/js/archimate/composer.js:5247-5257`, function `linkSubDiagram`.
Right-clicking a canvas element that has a linked sub-diagram and choosing
to navigate to it builds:
```js
window.open('/archimate/composer?viewpoint=' + existingId, '_blank');
```
`existingId` is `cell.get('linkedSubDiagramId')` — a numeric saved-diagram
id. But the composer route only recognizes `?viewpoint=<key>` for NAMED
viewpoint TYPES (`layered`, `basic`, `technology`, etc. — see
`STANDARD_VIEWPOINTS` in `app/services/archimate_viewpoint_service.py`).
A numeric string passed as `viewpoint` doesn't match any key, so
`get_viewpoint_data` silently falls back to `STANDARD_VIEWPOINTS['basic']`
— the user does not land on the sub-diagram they clicked, with no error
shown. The CORRECT mechanism for opening a specific saved diagram by id is
the separate `?viewpoint_id=<id>` parameter, read client-side in
`composer.js:2535-2543` (`loadSavedViewpoint`), which fetches from
`/archimate/api/saved-viewpoints/<id>` — a different code path entirely
from the `?viewpoint=` one.
FIX: change `linkSubDiagram` to build `?viewpoint_id=' + existingId`
instead of `?viewpoint=' + existingId`.

**D3 — every AI Chat "Open in Composer" link is broken, in TWO compounding ways.**
Four call sites in `app/modules/ai_chat/routes/chat_workflows.py` (search
for `composer_url`) and one in `app/services/archimate_composer_service.py`
build:
```python
f"/archimate/composer?viewpoint={view.id}"   # or diagram.id, or literal "0"/"42"
```
Same wrong-parameter defect as D2 (`viewpoint=<numeric>` instead of
`viewpoint_id=<numeric>`) — **compounded by a second, independent defect**:
the numeric id in `chat_workflows.py`'s case is a `ViewpointView.id` (a
different SQLAlchemy model, from `app/models/archimate_viewpoint.py`), NOT
a `SavedDiagram.id`. Even after fixing the parameter name, `loadSavedViewpoint`
would still 404/error, because it only ever fetches from
`/archimate/api/saved-viewpoints/<id>`, which reads `SavedDiagram` rows,
not `ViewpointView` rows. So every "Open in Composer" link the AI
assistant hands back after generating a stakeholder-viewpoint suggestion
opens a blank or wrong canvas today — this has likely been broken since
this AI feature shipped, independent of tonight's other fixes.
**Verify before fixing**: is `ViewpointView` meant to be a genuinely
separate concept from `SavedDiagram`, or should AI-chat-generated
viewpoints actually BE `SavedDiagram` rows so they can be opened the same
way as everything else? Read `app/models/archimate_viewpoint.py`'s
`ViewpointView` model and `app/models/saved_diagram.py` (or wherever
`SavedDiagram` lives) to determine whether: (a) the composer's
saved-viewpoint API should be extended to ALSO read `ViewpointView` rows
(e.g. a `?type=viewpoint_view` disambiguator, or trying both tables), or
(b) `chat_workflows.py` should create a `SavedDiagram` row instead of a
`ViewpointView` row so the existing mechanism just works, or (c) some
other resolution. Per ADR 0008 ("one accessor per concept"), prefer NOT
creating a second parallel "open a saved thing in the composer" code path
if it can be avoided — but do not force a wrong architectural choice under
time pressure either. State your reasoning.

## Constraints
- Do not regress any of tonight's three already-deployed composer fixes
  (sidebar link, dashboard per-layer tabs, and their `viewpointDirty`/
  autosave/tenant-isolation correctness — see
  `docs/buckets/composer-opens-layered-viewpoint/` and
  `docs/buckets/dashboard-composer-layer-links/` for that history and the
  regression classes already found and fixed there tonight).
- This is the fourth time tonight this exact class of bug (a composer link
  not opening the right content) has been found — treat the review with
  full adversarial rigor, and specifically grep AGAIN after your fix for
  any other `viewpoint=` (not `viewpoint_id=`) usage with a value that
  isn't a known STANDARD_VIEWPOINTS key, since D2/D3 show this exact
  mistake has been made independently at least 5 times across this
  codebase — assume there may be a 6th.
- Tenant isolation and the `viewpointDirty`/autosave correctness must hold
  on any code path you touch or add, matching tonight's established
  pattern.

## Deliverable
- D1, D2, D3 fixed per the analysis above (D3's exact fix shape determined
  by your own investigation, not assumed).
- Tests: a test confirming the "Architecture Overview" card's button
  carries `viewpoint=layered`; a test confirming `linkSubDiagram` builds
  the correct `viewpoint_id=` URL (JS-level test or equivalent); tests
  covering whichever D3 resolution you implement, including a real
  end-to-end proof that an AI-chat-generated viewpoint link actually opens
  showing real content, not a blank/wrong canvas.
- An exhaustive re-grep confirming no other `?viewpoint=<non-standard-key>`
  usage remains anywhere in the codebase (templates, JS, Python) — paste
  the grep output and its analysis into the build report.
- A live Playwright check for D1 (click the "Architecture Overview" card's
  button, confirm real elements render) and, if feasible, for D2/D3.

## Acceptance Criteria
- All three defects fixed and demonstrated, not just source-patched.
- The exhaustive re-grep finds zero remaining instances of this bug class.
- No regression to any of tonight's three already-deployed composer fixes.
- `python scripts/verify.py --tag static` clean.

## Handoff Target
`refuter` — given this is the fourth occurrence of this exact bug class
found tonight (three prior rounds each found "one more" instance after the
previous fix was believed complete), review with the assumption that a
fifth instance may still be lurking, not as a formality.
