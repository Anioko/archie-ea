# ADR 0001 — Verification strategy: executable gates, not compiler enforcement

- **Status:** Accepted
- **Date:** 2026-07-30
- **Context:** A proposal to require that all code produced by LLM agents working on
  Archie be "tested, verified and validated at the compiler level", on the grounds
  that this is mandatory and prevents any errors.

## Decision

Reject compiler-level enforcement as the primary mechanism. Adopt **layered
executable gates**, each targeting a failure class that has actually occurred in
this repository, fronted by a single command (`python scripts/verify.py`) and
enforced by CI.

Keep the *intent* of the proposal in full: enforcement must be machine-checked,
non-negotiable, and impossible to satisfy by self-certification.

## Why not compiler-level enforcement

### 1. It would have caught none of our actual failures

Every incident this repository has documented lives in the gap between source code
and runtime environment — exactly where a compiler has no visibility:

| Documented failure | Compiler-detectable? | Why not |
|---|---|---|
| 47 drifted columns → `UndefinedColumn` → `InFailedSqlTransaction` cascade (`docs/known-issues/schema-drift-on-existing-databases.md`) | No | Live database state |
| `BuildError` 500s from unresolved `url_for()` | No | Jinja template strings resolved against a runtime registry |
| Blueprint silently fails to register (~100 `try/except` handlers) | No | Deliberate dynamic import tolerance |
| Missing `soc2_audit_log` table blocking all user inserts | No | Runtime DDL state |
| Bulk `UPDATE`/`DELETE` bypassing tenant isolation (ADR 0003) | No | SQLAlchemy event-listener coverage gap |

A perfect type checker changes none of these outcomes.

### 2. "Prevents any errors" is not attainable

No type system eliminates semantic error. Archie's defect profile is semantic —
wrong disposition score, wrong tenant scope, wrong ADM phase. Strongly-typed
languages do not prevent these either.

### 3. Python's dynamism here is load-bearing, not incidental

Blueprint registration is intentionally dynamic so one broken module degrades one
feature. Tenant isolation is intentionally implicit, applied by ORM events keyed on
request-scoped `g`. Templates are compiled at runtime. Making this codebase
statically checkable end-to-end would mean removing the properties it is built on.

### 4. We already ran the "mandatory protocol" experiment

`app/templates/macros/ZERO_TOLERANCE_PROTOCOL.md` is 177 lines of exactly this
approach — "NO EXCEPTIONS", "MANDATORY, NOT OPTIONAL", automated bans after three
violations. Measured state of the repository while that document was in force:

- 8 test files against ~200 models, ~340 services, 27 modules
- CI lint step reading `ruff check . || true` inside `continue-on-error: true`
- 1255 violations of DESIGN.md's "mandatory" colour-token rule, whose enforcing
  pre-commit hook did not exist
- 296 `F821` undefined-name findings across 68 files, including a module calling
  `datetime.utcnow()` without importing `datetime`

The lesson is not that the protocol was too weak. It is that **a document cannot
enforce itself.** Only a failing build can.

### 5. A big-bang static-typing retrofit produces the appearance of rigour

`mypy --strict` across ~500 Python files yields tens of thousands of errors. The
inevitable pressure valve is blanket `# type: ignore`, producing a gate that passes
while checking nothing — strictly worse than no gate, because it also
misinforms.

## What we adopted instead

Gates run cheapest-first; each targets a specific failure class.

| # | Gate | Failure class | Kind |
|---|---|---|---|
| 1 | `compile` — bytecode-compile every module | syntax errors | must pass |
| 2 | `undefined-exports` — ruff `F822` | `__all__` naming missing symbols | zero |
| 3 | `undefined-names` — ruff `F821` | `NameError` at runtime | ratchet |
| 4 | `redefinitions` — ruff `F811` | shadowed definitions | ratchet |
| 5 | `lint-core` — ruff `F,E4,E7,E9` | general correctness | ratchet |
| 6 | `design-tokens` | DESIGN.md colour rule | ratchet |
| 7 | `boot-health` | unregistered blueprints, unresolved `url_for` | must pass |
| 8 | `schema-drift` | ORM/database column drift | must pass (needs DB) |
| 9 | `tests` | behavioural regression | must pass (needs DB) |

**This is the compiler-equivalent, delivered where it is achievable.** Gate 1 is
literally an ahead-of-time compile step. Gate 3 is compiler-grade name resolution —
and it found real defects on the first run.

### Three design choices that matter more than the gate list

**Ratchets, not big bangs.** A gate whose baseline is the *currently measured*
value is enforceable today; one requiring a clean tree first is enforceable never.
Baselines live in `verification_baseline.json`. Lowering one is routine; raising one
is a visible diff that must be justified in review. Verified working: injecting a
single undefined name moved 296 → 297 and 4465 → 4466 and failed the build with
exit 1.

**One command.** An agent handed a protocol document drifts. An agent handed
`python scripts/verify.py`, which prints `FAIL: undefined-names [297 > 296]` plus a
remediation line, self-corrects in-loop. `--json` makes it consumable
programmatically; pre-commit gives the same feedback at commit time.

**Skips are loud.** A gate that cannot run reports `SKIP` with a reason, is listed
in the summary, and never counts as a pass. CI passes `--require-db` so an absent
database fails the build instead of quietly shrinking the gate set. The failure mode
being designed against is a suite that reports green because it did not run.

### Gate on evidence, not on authorship

The proposal framed this as an LLM-specific control. We reject that framing: a human
introducing the same missing import causes the identical `NameError`. Gates apply to
all changes regardless of origin. What LLM involvement justifies is *tighter
in-loop feedback* (pre-commit, `--json`), not a separate standard.

## Consequences

- CI has four hard gates where it previously had one (`secret-scan`).
- The advisory `lint` job is deleted; advisory gates train people to ignore output.
- Static gates complete in ~5s, so the fast signal precedes the slow ones.
- Style rule families (`UP`, `BLE`, `DTZ`, `I`, `RUF`) stay out of the gate — ~30k
  findings on this tree, and gating them buys no correctness. They remain available
  ad hoc as a cleanup backlog.
- Ratchet baselines must be re-measured when `ruff.toml`'s `select` changes; the
  config says so, since changing it silently invalidates the numbers.
- The 296 `F821` findings are now capped but not fixed. Burning them down is
  tracked separately; each fix lowers the baseline.

## Alternatives considered

- **`mypy --strict` tree-wide** — rejected, see §5.
- **Incremental `mypy` on an allowlist of new modules** — deferred, not rejected.
  Defensible once the module layout consolidates (ADR 0004); today the annotation
  burden lands on `app/models/` and `app/services/`, where the dynamic
  Flask-SQLAlchemy patterns give the poorest typing return.
- **Coverage percentage gate** — deferred. Coverage is measured and published now;
  gating on a number before a baseline exists on `main` invites gaming with
  low-value tests.
