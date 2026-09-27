# Verification gates

`scripts/verify.py` is the executable quality gate. Run it before claiming work
is complete.

```bash
python scripts/verify.py                     # every gate that can run here
python scripts/verify.py --json              # machine-readable
python scripts/verify.py --gate lint-core    # one gate
python scripts/verify.py --tag static        # fast static gates only
python scripts/verify.py --require-db        # fail instead of skipping DB gates
python scripts/verify.py --update-baseline   # record current measurements
```

## Three outcomes, and the third is the point

| | meaning |
|---|---|
| `PASS` | the gate ran and was satisfied |
| `FAIL` | the gate ran and was not |
| `SKIP` | the gate **could not run** — no database, no toolchain, tool absent |

**A `SKIP` is never a pass.** It is listed separately in the summary and CI runs
with `--require-db`, which turns one into a failure. A gate that quietly skips is
how a project ends up believing it is covered when it is not.

## The gates

| Gate | Catches | Kind |
|---|---|---|
| `compile` | syntax errors | must pass |
| `undefined-exports` | `__all__` naming a symbol the module doesn't define | must be 0 |
| `undefined-names` | runtime `NameError` (ruff F821) | ratchet |
| `redefinitions` | shadowed definitions (ruff F811) | ratchet |
| `lint-core` | correctness lint (ruff `F,E4,E7,E9`) | ratchet |
| `design-tokens` | raw Tailwind colours instead of theme tokens | ratchet |
| `native-dialogs` | `alert()`/`confirm()` in templates | must be 0 |
| `sri` | `integrity=` hash not matching the file it guards | must be 0 |
| `boot-health` | blueprints failing to register | ratchet on route count |
| `schema-drift` | model/database column drift | must pass (needs DB) |
| `tests` | behavioural regression | must pass (needs DB) |

CI runs the static gates plus `boot-health` and `schema-drift` with
`--require-db`. The `tests` gate is deliberately excluded from that job because
the separate **Tests** job already runs pytest with coverage, and running the
suite twice doubles the slowest job in the pipeline.

## Ratchets, and why they are not "clean"

A ratchet compares a measurement against `verification_baseline.json` and fails
only when it gets **worse**. The tree carries real debt. A gate that can never go
green is a gate somebody deletes, so the honest contract is "no worse".

Lowering a baseline after a cleanup is routine — run `--update-baseline`.
Raising one is a regression and needs justifying in review.

## Measured, not asserted

Every number in `verification_baseline.json` was measured on this tree, not
carried over from documentation:

| Measurement | Value |
|---|---|
| undefined names (F821) | 293 |
| redefinitions (F811) | 73 |
| correctness lint findings | 4,508 |
| raw Tailwind colour uses | 6,300 |
| routes registered | 3,413 across 157 blueprints |

**These contradict the figures quoted in `CLAUDE.md`**, which describes the
undefined-name and lint debt as cleared and puts raw colours at 739. `CLAUDE.md`
currently lives on the `trial/merge-upstream` branch rather than `main`, so it
has not been corrected here — whoever merges that branch should reconcile it
against these numbers rather than the other way round. The baseline records what
the tree does; the documentation described what someone hoped it did, and that
gap is what let twenty banned native dialogs, four fabricated UI counts and two
dead widgets accumulate unnoticed.

## Two traps this runner walked into, so you don't

**Do not use `compileall` for the compile gate.** It writes a `.pyc`, and on
Windows that raises `FileNotFoundError` for deep paths — reported identically to
a syntax error. The first version failed 8 modules that `ast.parse` accepts
perfectly. Syntax is a property of the source, not of whether the filesystem
will accept a bytecode file beside it. The gate now compiles in memory.

**Watch word boundaries when counting call sites.** An early count of native
dialogs reported 52; the pattern was `\bconfirm\(`, and `.` is a word boundary,
so it matched `Platform.confirm(` — the replacement API — as if it were the
problem. The real number was 7. `tests/test_no_native_dialogs.py` uses
`(?<![.\w])` and says why.
