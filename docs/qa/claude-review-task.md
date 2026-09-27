# Independent repair-batch review

Act as an independent reviewer. Read AGENTS.md and DESIGN.md before assessing frontend changes. This worktree has shared, uncommitted fixes; review the current git diff and the named new tests. Do not modify source, tests or the ledger; do not commit, push, deploy, access credentials/production, install packages, or spawn agents. Write only docs/qa/claude-repair-review.md. Report concrete blockers with path/line/evidence and a suggested regression. Do not claim tests passed without executing them. Avoid duplicating the full/static suite already running under Codex.

Prioritize:
1. phase checklist explicit Alpine initialization and stacked blueprint header/actions, plus new initial-load and responsive browser tests;
2. ArchiMate picker safe limits preserving tenant/type predicates;
3. deployment disk preflight, private candidate logs, common watchdog lock (production rollback occurred after five unknown error signals; do not waive them);
4. dashboard smoke selector/tab corrections preserving original intended outcomes.

Codex is concurrently modifying only architecture_crud_routes.py and tests/test_architecture_export_response.py for export cleanup; exclude those two from review to avoid moving-target findings. Export/import service changes may be reviewed separately if time remains. See docs/qa/COORDINATION.md for ownership. Read untracked tests named in git status as needed, but do not inspect raw downloaded artifact directories or secrets. Return a focused verdict: blocking issues, nonblocking issues, and required CI/browser verification. Passing local tests do not establish deployment or whole-product readiness. Stop after this bounded review.
