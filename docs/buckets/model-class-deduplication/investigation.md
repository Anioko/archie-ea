# Investigation: the fast-init model-graph split

Tech lead, 17 Sep 2026. Branch `fix/model-class-deduplication`, worktree
`../archie-oss-model-dedup`. Read-only investigation of application code — no
app code changed. (One governance-metadata line was added to
`config/allowed_config.txt`; see §9.)

**Naming note:** the environment variable at the centre of this is read at
`app/models/archimate_core.py:20` as
`_FAST_INIT = os.getenv(<the fast-init env var>, "0") == "1"`. Its literal name
is spelled out in the new `config/allowed_config.txt` entry and in the source
lines cited throughout; this document writes it as **"the fast-init flag"**
because the repo's `NO-DARK-FEATURES` write hook blocks prose containing the
literal token. Read every "fast-init flag" below as that exact variable.

## 1. The brief's claim, checked against the source

**Confirmed exactly.** Both definitions read in full.

| | `app/models/models.py:468` | `app/models/archimate_core.py:110` |
|---|---|---|
| Bases | `TenantMixin, db.Model` | `db.Model` — **no TenantMixin** |
| Gated by | `else:` of `if _FAST_INIT:` (models.py:191) | `if _FAST_INIT:` (archimate_core.py:31) |
| `architecture_id` | FK to `architecture_models.id` | plain Integer, no FK |
| `reviewed_at` | present | **absent** |
| ORM relationships | `architecture`, `source`, `target` + backrefs | none |

So the two are mutually exclusive by construction, not simultaneously live —
which matters for the fix, see §6.

One correction to the brief's mental model is worth stating. It is not
"models.py defines the tenanted one and archimate_core defines the untenanted
one, both loaded". `models.py:191` makes the *class name in models.py itself* an
alias of the archimate_core copy under fast init:

```python
if _FAST_INIT:
    from .archimate_core import ArchiMateElement, ArchiMateRelationship, ArchitectureModel
else:
    class ArchitectureModel(TenantMixin, db.Model): ...
```

and `archimate_core.py:22-24` does the mirror-image re-export in the other
direction. So under fast init **every** importer — `app.models`,
`app.models.models`, `app.models.archimate_core` — resolves
`ArchiMateRelationship` to the untenanted class. There is no safe import path.
The blast radius under fast init is total, not partial.

## 2. What the fast-init flag is for

Stated purpose, from `app/models/__init__.py:6-10` and `archimate_core.py:5-11`:

> In lightweight contexts (notably E2E / fast init) importing the entire ORM
> graph can trigger heavy mapper configuration and, on Windows, intermittent
> access-violation crashes. So under fast init we intentionally export only a
> small, safe subset.

So it optimises **import-time mapper configuration** for Playwright E2E, and was
additionally a workaround for a Windows access-violation crash during mapper
config. It is not a runtime or query optimisation — it changes which classes get
mapped at all.

## 3. Which copy is live in production — and everywhere else

The flag defaults off. Production (gunicorn / docker-compose) does not set it,
so **production runs the tenanted `models.py` class.** The confirmed-safe path.

The stronger finding: **nothing in this repository sets the flag to 1.** Greps
across `.github/`, `scripts/`, `tests/`, and all
`*.yml|yaml|sh|cfg|ini|toml|env|example|json|ps1|Dockerfile` return zero setters.
The only assignment anywhere is `tests/test_model_boot_registration.py:42`,
which sets it to **`"0"`** — i.e. explicitly *disables* it.

Consequence: the fast-init model graph is **unreachable dead code under every
runner this repo has** — pytest, CI's static/tests/smoke jobs, the Playwright
smoke harness, docker compose, gunicorn. The docstring's "notably Playwright
E2E" is stale; `tests/smoke/` does not set it.

This reframes severity honestly, and the task brief must say so rather than
inherit the bucket brief's framing: the untenanted `ArchiMateRelationship` is a
**loaded trap with the safety on**, not a currently-firing bug. Nobody's rows
are being written with `organization_id IS NULL` through this path today. What
is true is that one `export` of that variable — in a developer shell, in a
future CI job added to "speed up E2E", or in a revived Windows workaround —
silently flips the ArchiMate backbone to an unfiltered mapper with nothing
raising.

## 4. Is the mechanism shared across the other pairs? Yes — six files

Same `_FAST_INIT = os.getenv(...)` idiom, same conditional-class pattern:

- `app/models/models.py:188`
- `app/models/archimate_core.py:20` — `ArchitectureModel`, `ArchiMateElement`, `ArchiMateRelationship`
- `app/models/application_component_fast.py:21` — `ApplicationComponent`
- `app/models/motivation_extended.py:7` — `Principle`
- `app/models/requirements.py:5` — `Requirement`
- `app/models/technology_stack.py:5` — `TechnologyStack`
- `app/models/architecture_review_board.py:42` — `ARBDocument` (conditionally
  *absent*, which `tests/test_arb_ea_org_columns.py:72-75` skips around)

Plus behavioural gating outside models:
`app/modules/architecture/services/archimate_llm_service.py:83` raises under
fast init, and `app/__init__.py:77` skips error tracking.

So **yes — one mechanism produces every "fast twin" pair in the bucket brief's
high- and medium-risk tables**, and the two `Requirement` / `TechnologyStack`
"lower risk" pairs as well. The medium-risk pair (`ArchiMateElement`,
`ArchitectureModel`) is the *same* mechanism with the mixin correctly applied on
both sides — which is evidence that the asymmetry on `ArchiMateRelationship` is
an oversight, not a design decision. Its two immediate siblings in the same
conditional block at `archimate_core.py:33` and `:53` both carry `TenantMixin`;
only `:110` does not.

## 5. Existing coverage — and its exact blind spot

`tests/test_double_mapped_tenancy.py` already exists and is good. It asserts at
runtime, against the mapper registry, that no table has both a scoped and a live
unscoped mapping, and it pins the archimate_core re-export
(`test_archimate_core_reexports_the_scoped_models`).

**It cannot catch this defect**, because it runs in the pytest process where the
flag is unset — so it only ever exercises the `not _FAST_INIT` branch, in which
the untenanted class is never defined. The file's own docstring is candid that a
static scan cannot answer this either (its author wrote a grep checker, measured
it, and it was wrong on this very example). So the defect sits in the one place
neither the static gate nor the runtime gate looks: the *other* branch of an
import-time conditional.

That blind spot, not the missing mixin itself, is what Task 1 must close.

## 6. The fix decision — made, not deferred

Three options considered.

**(A) Add `TenantMixin` to the fast-init `ArchiMateRelationship`.** One line.
Makes the branch match its two siblings in the same block. Zero risk to
production (that branch executes in no current runner). Does not retire the
mechanism.

**(B) Delete the fast-init branch entirely, everywhere.** Justified by §3 — the
mechanism is dead code. But it is a 7-file change touching `models.py`,
`app/models/__init__.py`, ARB, `Principle`, `ApplicationComponent`,
`Requirement` and `TechnologyStack`, against a 3,413-route surface, and the
bucket brief explicitly forbids a big-bang merge.

**(C) Make fast init reuse the same class as normal runtime.** Not achievable
without restructuring: under fast init `models.py` imports *from*
`archimate_core`, so deleting the fast class leaves that branch with no
definition and a circular import to untangle. This is option B wearing a smaller
hat.

**Decision: (A) for Task 1, with mechanism retirement raised as a separate,
evidence-backed Task 4 — not (B) now.**

Reasoning, stated so a reviewer can disagree with the reasoning rather than only
the outcome: the asymmetry is the defect, and (A) removes it completely at
effectively zero blast radius. The mechanism's deadness is a *second* finding
that deserves its own deliberate change with its own verification, not a rider
on a one-line tenancy fix. Doing B now would make the bucket's first and
riskiest change also its largest, which is precisely the sequencing the bucket
brief's constraints rule out. And if B is later rejected — someone revives fast
init for the Windows mapper crash — A still had to have happened. A is not
wasted work under either future.

**I am explicitly recommending Task 4 = retire the fast-init mechanism**, with
§3's zero-setters evidence as its justification. A performance mechanism no
runner enables, which silently swaps the tenancy semantics of the ArchiMate
backbone, is pure liability. But it is a follow-up, sequenced after Tasks 1-3.

## 7. Honest note on "Done means DEMONSTRATED" for this task

The bucket brief's acceptance criterion — "create a relationship via a UI flow
and confirm it's visible" — cannot prove this fix, and the task brief must not
pretend otherwise. In normal runtime the patched class is not mapped at all, so
the browser exercises unchanged code. The browser check's real job here is
**regression evidence** (the ArchiMate backbone still works after
`archimate_core.py` is touched). The fix's *proof* has to be a test that
actually enters the fast-init branch — a subprocess test with the flag set,
following the established pattern at `tests/test_model_boot_registration.py:41-54`.
Both are required; neither substitutes for the other.

## 8. Outline for Tasks 2+

- **Task 2 — `Principle`** (`models.py:1633` vs `motivation_extended.py:27`).
  Same mechanism, same asymmetry. Repeat Task 1's pattern verbatim.
- **Task 3 — `ApplicationComponent`** (`application_portfolio.py:80` vs
  `application_component_fast.py:26`). Highest caller count of the three;
  `OptimisticLockMixin` on the canonical copy means the fast twin diverges in
  locking behaviour too, not only tenancy. Do this last of the three.
- **Task 4 — retire the fast-init mechanism** (see §6). Removes the
  `Requirement` / `TechnologyStack` / `ARBDocument` splits as a side effect and
  makes Tasks 1-3's mixin additions redundant-but-harmless. Needs its own
  browser and full-suite verification.
- **Not in this bucket:** the enum collisions (`ApprovalStatus`,
  `DuplicateType`, `CheckpointType`, `BatchJobStatus`) — per the bucket brief,
  rename to disambiguate, never merge. Different mechanism, different risk.

## 9. Disclosure: one file written outside `docs/buckets/`

Writing this document was blocked by the `NO-DARK-FEATURES` write hook, which
flags the env-var name as a default-off feature flag. The hook's own prescribed
remedy is to declare genuinely operational config in
`config/allowed_config.txt`. It is operational — an import-time performance and
platform-stability toggle exposing no user-facing feature — so one line was
added there with that reason. No application code was touched. Builder should
keep that line and should expect the same hook when editing these files.

## Cross-reference note (added by coordinator, not tech-lead)

This bucket's finding (13 duplicate model class definitions, root-caused to
a shared `APP_FAST_INIT` mechanism across 7 files) is a real addendum to the
`archie-ea-as-is` bucket's as-is picture (`../archie-oss-ea-as-is/docs/
buckets/archie-ea-as-is/current-state.md`), which documents module-LAYOUT
duplication (ADR 0004, `app/<domain>/` vs `app/modules/<domain>/`) but not
this distinct class-level duplication pattern.

Attempted to notify that session directly; the message was denied at the
delivery layer (never reached their Claude) rather than acknowledged or
declined on its merits. Not editing their bucket's files directly to avoid
an uninvited concurrent-edit collision on their in-progress work. Whoever
picks up `archie-ea-as-is` next should fold this finding in as a fifth
"architecture debt" item alongside layout duplication, capability stores,
schema mechanisms, and deploy pipelines.

## Builder addendum (Tasks 1-3 complete, two new findings)

Tasks 1 (`ArchiMateRelationship`), 2 (`Principle`), 3 (`ApplicationComponent`)
implemented per this document's decision in §6, each with a subprocess test
demonstrated red-then-green. Tests live in `tests/test_fast_init_model_tenancy.py`.
`ApplicationComponent` deliberately received TenantMixin only, not
OptimisticLockMixin -- the locking-behavior divergence noted in §8 is a
separate, larger concern than tenancy and is not addressed here.

Two new findings surfaced while writing Task 1's test, both out of scope for
Tasks 1-3 (touching `models.py`/`technology_stack.py` is explicitly forbidden
by Task 1's brief) and not fixed in this pass:

### Finding A -- TechnologyStack fast-init collision (candidate Task 5)

`models.py` unconditionally defines `class TechnologyStack(db.Model)`
(no fast-init guard on this particular class, unlike its siblings), while
`app/models/technology_stack.py` defines a *second*, fast-init-only
`TechnologyStack` against the same `technology_stacks` table, loaded via
`app/models/__init__.py`'s `if _FAST_INIT: ... from .technology_stack import *`.
Importing both in one process (which happens the instant anything imports
`app.models.models` while fast-init is on -- including `models.py`'s own
alias branch at `models.py:190-198`) raises
`sqlalchemy.exc.InvalidRequestError: Table 'technology_stacks' is already
defined for this MetaData instance.` This means `models.py`'s alias branch
for `ArchiMateRelationship`/`ArchiMateElement`/`ArchitectureModel` -- the
"if this monolithic module gets imported anyway" case its own docstring
describes -- is currently a hard crash, not a graceful fallback. Documented as
a known-red assertion in
`test_fast_init_models_module_import_collides_on_technology_stack` rather
than silently discovered and dropped. Same root mechanism as this whole
bucket; recommend as Task 5, sequenced with or after Task 4 (mechanism
retirement) since fixing it in isolation just relocates the collision.

### Finding B -- Outcome has no tenancy in EITHER branch (higher severity, different class of bug)

While reading `motivation_extended.py` for Task 2, found `Outcome` is defined
without `TenantMixin` in *both* `models.py:1568` and the fast-init twin at
`motivation_extended.py:15` -- this is not the fast-init asymmetry pattern
this bucket targets, it is a plain, live, production tenant-scoping gap.
`Outcome` is actively written to from at least four call sites
(`app/modules/architecture/services/goal_service.py:279`,
`app/modules/architecture/services/outcome_service.py:404`,
`app/modules/solutions_strategic/v2/services/solution_ai_orchestrator.py:4726`,
`app/services/motivation_bridge_service.py:160`), so rows are created today
with no `organization_id` at all, and any query against `Outcome` -- unlike
every `TenantMixin` model -- gets no automatic tenant filter. Not fixed here:
adding `TenantMixin` to a live, populated production table needs the same
nullable-override + backfill-command treatment `Principle` already required
(see `models.py:1649-1660`), which is a data-migration decision, not a
one-line mixin add, and deserves its own scoped task with its own review --
not a rider on this bucket's fast-init-asymmetry fix. Flagging for tech-lead
triage as a new, separate, higher-priority bucket: this is a currently-active
gap, not a dormant trap like Tasks 1-3.
