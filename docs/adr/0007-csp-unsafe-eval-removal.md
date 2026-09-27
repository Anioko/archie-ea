# ADR 0007 — Removing `unsafe-eval` from the CSP (ARCH-070)

- **Status:** Accepted — strategy proven, evaluator built and verified against the real app; only the atomic production cutover remains (see "Execution" step 5)
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

1. **[done] Prove feasibility** — `scripts/check_alpine_csp_grammar.py` parses
   99.9% of the live corpus with a bounded grammar.
2. **[done] Write the JS evaluator** — `app/static/js/csp/csp-evaluator.js`
   (tokenizer + Pratt parser + tree-walking interpreter, no eval/new Function)
   and `app/static/js/csp/alpine-csp-adapter.js` (registers it via
   `Alpine.setEvaluator`, rebuilds the data stack via `Alpine.$data`, and
   reimplements the built-in magics `$el $refs $store $data $root $nextTick
   $dispatch $id $watch`).
3. **[done] Verify headlessly** — `tests/csp/` (run in real chromium via
   Playwright, gated by `tests/csp/test_csp_evaluator.py`):
   - `verify_evaluator.py`: **100% of authored expressions parse** (the only
     3 misses are JS-generated template-literal fragments whose runtime form
     parses); a 33-case correctness battery and a 6-case stateful battery pass;
     and a **differential test finds 0 divergences on 10,819 pure expressions**
     compared to the browser's own native `eval`.
   - `verify_alpine_integration.py`: three controlled configs served under a
     genuine `Content-Security-Policy` **HTTP header** — (A) stock Alpine with
     eval blocked is **broken** (16 violations, proving the header enforces),
     (B) Alpine + this evaluator with eval blocked **works** (all directives +
     `$refs/$dispatch/$watch/$root/$el` + x-for/x-model/@click compound & method
     handlers, **0 CSP violations, 0 page errors**), (C) stock Alpine with eval
     allowed works (sanity). **RESULT: PASS.**
4. **[done] Real-app-page smoke** — `tests/csp/verify_real_pages.py` boots the
   REAL Flask app, authenticates, loads composer + dashboard + capability-map,
   and checks **every Alpine expression in the live rendered DOM**. It found and
   fixed three genuine evaluator gaps the corpus tests missed (multi-statement
   `if`-handler terminators, object `get`/`set` accessors, `//` and `/* */`
   comments in method bodies), then went green: **1,099 live-DOM expressions, 0
   parse failures, 0 divergences vs native eval.** Gated by
   `tests/csp/test_csp_evaluator.py::test_real_app_pages_parse_and_evaluate`.
5. **[next — the cutover] Single atomic change** (no dark flag): wire the two
   `app/static/js/csp/` scripts into the page load order in
   `app/templates/partials/_head.html` (deferred, before `alpine.min.js`) AND
   **drop `'unsafe-eval'`** from `app/_bootstrap/security.py`, flipping
   `test_unsafe_eval_still_present_and_documented` to assert absence. One commit,
   because a half-state (evaluator active but eval still allowed, or vice-versa)
   is exactly the dark intermediate the repo's no-dark-features gate forbids.
6. **[last] Deploy + verify live** — reload real pages on the droplet and confirm
   0 CSP violations, 0 Alpine errors, interactivity intact.

`'unsafe-eval'` stays in the running CSP until step 5. The evaluator, adapter and
all three verification layers are committed; they are **not yet wired into the
page load order**, so production is unaffected. Step 5 is the outward-facing
cutover — done as one deliberate, monitored deploy.

## Why not just do the 8,523 rewrites anyway

Because it is strictly worse on every axis: ~100× the change surface, 268 files
each needing a browser check, and a real regression risk (this branch has a
history of structural-template edits detaching Alpine scopes). One audited
evaluator is a smaller, safer, and reviewable change.
