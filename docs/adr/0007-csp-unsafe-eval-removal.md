# ADR 0007 — Removing `unsafe-eval` from the CSP (ARCH-070)

- **Status:** Accepted — strategy chosen and proven; implementation staged (see "Execution")
- **Date:** 2026-08-18
- **Owner decision:** delivery/tech lead (per the standing "own the decision" instruction)

## Context

`script-src` in the production CSP still carries `'unsafe-eval'`. It is the one
remaining injection-hardening gap for ARCH-070 (`script-src` already has a nonce +
`'strict-dynamic'` and no `'unsafe-inline'`; `style-src` dropped `'unsafe-inline'`).

`'unsafe-eval'` is required because Alpine.js 3's default expression evaluator
compiles every directive expression with `new Function(...)`. Remove the directive
and every Alpine expression stops evaluating — the entire interactivity layer goes
inert.

## The decision that was punted, and why it was wrong to punt it

The original finding framed the only fix as **swapping to the `alpinejs-csp`
build**, whose restricted evaluator accepts only bare identifiers and simple
calls. A static scan (`scripts/check_alpine_csp_compat.py`) measured **8,523 of
17,997 Alpine expressions (47%) as incompatible** with that build, so the swap was
recorded as "staged, not attempted" and pinned as a reviewed exception.

That framing made ARCH-070 look like a multi-week, 268-file rewrite with a
per-file browser check — so it kept being deferred. It was the wrong framing.

## The strategy: replace the evaluator, not the 8,523 expressions

Alpine 3.14.3 **exports `Alpine.setEvaluator`** (verified in the vendored
`app/static/vendor/alpine.min.js`). That lets us replace the `new Function`
evaluator with a **CSP-safe interpreter** — a small tokenizer + Pratt parser +
tree-walking evaluator that interprets the expression subset the templates use,
with no `eval`/`new Function` anywhere. With the evaluator replaced, `'unsafe-eval'`
can drop **with zero template rewrites**.

This turns "rewrite 8,523 expressions across 268 files" into "write and
exhaustively test one evaluator, then handle a handful of edge cases."

## Feasibility — proven with the real corpus, not asserted

The make-or-break risk is grammar coverage: can a bounded grammar parse every
expression the codebase actually uses? We extracted **all 17,543 Alpine
expression occurrences (11,856 unique)** from `app/templates` and `app/modules`
and ran them through a reference parser mirroring the intended evaluator grammar
(`scripts/check_alpine_csp_grammar.py`).

Result:

| Bucket | Count | Share |
|---|---|---|
| Parsed by the bounded grammar | 11,821 | **99.70%** |
| Tailwind `x-transition` class-strings (not JS, not evaluated) | 25 | 0.21% |
| True residual | **10** | **0.08%** |

Of the 10 residual: ~6 are corpus-extraction artifacts (template-literal
`${…}` fragments captured without their backticks; one regex-quote capture that
bleeds across an attribute boundary), and ~4 are genuinely complex inline
handlers (a `try/catch`, an object getter, one long multi-statement `@click`).
Those ~4 are either supported by extending the evaluator or moved into a
component method — a countable, trivial rewrite, versus 8,523.

The grammar the evaluator must cover (all present in the corpus): member access
incl. optional chaining `?.` and `?.[`, calls incl. spread, unary/prefix, the
full binary operator set, ternary, assignment (`=`, `+=`, …), array/object
literals, arrow functions, `function` expressions, template literals, regex
literals, `new`, and statement-level `if`/`return`/`let`/`const` for `@click`
handlers.

## Execution (staged)

1. **[done] Prove feasibility** — this ADR + `scripts/check_alpine_csp_grammar.py`
   (the reference parser, run against the live corpus in CI-style).
2. **[next] Write the JS evaluator** mirroring the proven grammar, registered via
   `Alpine.setEvaluator`, using the reference parser as the executable spec.
3. **[next] Verify in a browser** — the evaluator changes how *every* expression
   evaluates, so a real browser pass across representative pages is mandatory
   before it goes live. (Blocked only on a paired browser session.)
4. **[next] Handle the ~4 residual handlers** (extend evaluator or move to method).
5. **[last] Drop `'unsafe-eval'`** from `app/_bootstrap/security.py` and flip the
   `test_unsafe_eval_still_present_and_documented` test to assert its absence.

`'unsafe-eval'` stays in the CSP until steps 2–4 are complete and browser-verified.
Nothing in this ADR changes the running policy yet — it records the chosen path
and the evidence that it is viable.

## Why not just do the 8,523 rewrites anyway

Because it is strictly worse on every axis: ~100× the change surface, 268 files
each needing a browser check, and a real regression risk (this branch has a
history of structural-template edits detaching Alpine scopes). One audited
evaluator is a smaller, safer, and reviewable change.
