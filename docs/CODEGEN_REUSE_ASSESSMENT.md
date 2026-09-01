# Codegen / Genome pattern — reuse assessment (1 Sep 2026)

Investigated to answer: can the codegen "genome" approach be reused, and is it
a good idea? Findings corrected an initial over-rosy take.

## What it is
ArchiMate model → AABL compiler → **genome** (versioned IR dict) → generators →
bundle → deployed → Playwright acceptance tests. A compiler architecture over
models; the genome is the IR, ArchiMate the source language, generators the
backends.

## What testing the code revealed
- **Generators are LLM-based, not deterministic.** `code_generation_service.generate_all`
  calls the LLM per models/schemas/routes/services/tests. Same genome → different
  code each run.
- **Traceability is unreliable.** `code_generation_service.py:262` comment: the LLM
  "output is unreliable (often stays 123 or ?)" for element IDs, so provenance is
  **post-injected**, not carried through the IR.
- **Zero test coverage.** No `*codegen*`/`*genome*`/`*aabl*` test exists. Generated
  code is syntax-*warned* (`_check_python_syntax`), never proven to compile/run.
- **BUT there is a deterministic core.** `genome_to_bundle.py` has **0 LLM calls** —
  genome → file/folder structure is deterministic. Docs are Jinja, not LLM
  ("Documentation (Jinja template, not LLM)"). aabl_compiler and
  genome_extraction do use the LLM.

## Reuse verdict
- **Genome IR concept: sound.** A validated, versioned representation the AI can
  emit and be checked against. Keep.
- **Deterministic core (genome→bundle, docs via Jinja): SAFE to reuse.** Extend to
  new backends that don't exist yet — genome → documentation / ADRs / ArchiMate
  views. Reproducible, low blast radius. **This is the reuse to go ahead with.**
- **LLM code-generation path: DO NOT reuse until proven.** Non-deterministic +
  unreliable traceability + unverified = the MDE "graveyard" failure mode. First
  prove it works end-to-end on one real solution (code compiles, its own
  acceptance tests pass) before betting anything on it.

## The one test that settles it (post-demo wave)
Run `generate_code`/`generate_all` on one real solution end to end and confirm:
1. it produces a bundle, 2. the code compiles/imports, 3. the generated Playwright
acceptance tests actually run and pass. If yes → differentiating asset. If no →
an 80%-built subsystem, same shape as the UI was before this session.
