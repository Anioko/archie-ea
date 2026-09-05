# Bounded availability-contract task (F500-053)

Implement tests and a concise findings report only. Own only tests/test_availability_response_contracts.py and docs/qa/claude-availability-result.md. Do not modify application code, smoke probes, baselines, CI, ledger, or any other files. Do not commit/push/deploy, read credentials, call external providers, install dependencies, or spawn agents. Codex owns integration and independent browser verification. No full-suite duplicate run.

CI adversarial probes report deliberate 503 responses from:
- app/modules/ai_chat/routes/legacy_compat.py llm_health: LLM unconfigured;
- app/modules/ai_chat/routes/page_guide_routes.py _feature_guard/get_page_guide_history: page guide disabled or missing AI;
- app/application_mgmt/template_api_routes.py get_frameworks: no framework seed rows.

Read the actual functions and service contracts. Add focused tests executing the actual handlers/guards through Flask with clearly disclosed boundary doubles for configured/unconfigured/empty/error states. Do not fabricate a healthy provider or claim external LLM calls were verified. Prefer actual route imports if feasible; avoid booting an unconfigured database just for tests. If extracting real function AST, document precisely that auth/database/browser behavior is not covered. Invalid request context validation must remain visible when enabled. No blanket 503 allowlist or baseline increase. Report a concrete next integration plan distinguishing expected unavailable states from genuine backend failures, and what real configured browser tests are still needed.

Run only the new test file with python -m pytest tests/test_availability_response_contracts.py -q -p no:cacheprovider. Report exact pass/fail/skip counts, and stop. If tools are denied, report the denial rather than claiming execution. Apply repository conventions: no invented UI data, no secrets, no production writes, and preserve other workers' files.
