# SDLC Orchestration Setup Report

Generated 2026-09-15. Scope: Claude Code subagent roster, Aider/OpenRouter
routing, handoff protocol, slash commands. Kilo Code and the standalone
browser QA agent are deferred (see below).

## Environment

| Check | Result | Command |
|---|---|---|
| Node.js/npm/npx | **FAIL — not installed** | `node --version` (bash and PowerShell both: command not found) |
| Python 3 | PASS (3.13.14) | `python3 --version` |
| Aider | PASS (0.86.2) | `aider --version` |
| Kilo Code | **FAIL — not detected** | no `~/.kilo`, no VS Code global storage folder found |
| Playwright | **SKIPPED** | depends on npm |

**Fix for Node.js/npm:** install via winget (`winget install OpenJS.NodeJS.LTS`)
or nodejs.org, then re-run `npx playwright install chromium` for the browser
QA agent and install the Kilo Code VS Code extension from the marketplace.

## Validation checklist (from the original brief)

| Item | Result | Evidence |
|---|---|---|
| `aider --model orchestrator --message "ping"` returns a response | **SKIPPED — no API key** | Ran it: aider correctly loaded the `orchestrator` alias (`openrouter/anthropic/claude-opus-4.6`) and reached OpenRouter, then failed with `litellm.AuthenticationError: ... No cookie auth credentials found (401)` because `.env`'s `OPENROUTER_API_KEY` is blank. Fill it in and re-run — the routing itself is proven correct. |
| `aider --model coder --message "ping"` returns a response | **SKIPPED — same reason** | Same alias mechanism, same missing key. |
| Kilo Code agent list shows custom agents | **SKIPPED — not built** | Kilo Code isn't installed (Part 2/`kilo.jsonc` was out of scope per your decision to skip it). |
| `claude --agent business-analyst` loads with correct prompt | **PASS (static check)** | Verified all 13 files in `.claude/agents/*.md` parse valid frontmatter with `name`/`description`/`tools`/`model` (script run, all OK). Did not invoke `claude --agent` interactively from this session. |
| `builder` has Edit/Write; `refuter` does not | **PASS** | `builder.md` tools: `Read, Glob, Grep, Edit, Write, Bash`. `refuter.md` tools: `Read, Glob, Grep` — no Edit/Write. |
| `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` set and enforced | **PASS (set), unverified (enforced)** | Set in `.claude/settings.local.json` → `env`. Confirmed valid JSON. Enforcement is Claude Code's own runtime behavior, not testable from a shell command. |
| Mock handoff BA→SA blocked when gate conditions fail | **PASS** | `docs/handoffs/example-ba-to-sa.json` has `approval_status: pending` with `unmet_conditions: ["no_open_questions"]`. Script check confirms: gate correctly blocks. |
| Browser agent navigates to localhost and reports PASS/FAIL | **SKIPPED — not installed** | Node.js/Playwright missing. `qa/qa-config.yml` is written but the agent binary doesn't exist. Use `pytest tests/smoke/` (already in this repo) in the meantime — wired into `qa-lead.md` and `/qa`. |
| `/task` command creates a bucket and brief | **NOT RUN THIS SESSION** | `.claude/commands/task.md` is written and would need an interactive Claude Code session to invoke as a slash command; not runnable from this shell-only validation pass. |
| `/handoff` command routes to correct agent | **NOT RUN THIS SESSION** | Same — `.claude/commands/handoff.md` written, needs an interactive session to exercise. |
| OpenRouter cost tracking shows usage | **SKIPPED — no API key, no run** | Depends on the aider ping above succeeding first. |
| `.env` in `.gitignore`, key not committed | **PASS** | `git check-ignore -v .env` confirms `.gitignore:270:.env`. `OPENROUTER_API_KEY=` placeholder appended, empty. |

## What was deliberately skipped or descoped (with your sign-off)

- **Kilo Code (`kilo.jsonc`) and the standalone browser QA agent**: not built — Node.js/npm isn't installed on this machine. Install Node, then the Kilo Code extension and `npx playwright install chromium`, and these can be added.
- **Extended roster** (Enterprise Architect, SRE, Accessibility Specialist, Compliance Officer, Localization Lead, Scrum Master, Growth Analyst, Customer Support Lead, Sales Engineer): not built, to stay under a reasonable v1 scope. Add as needed following the pattern in `.claude/agents/*.md`.
- **BMAD method import**: not run.
- **`.gitignore` carve-outs for `.claude/` and `artifacts/`**: not added, on your instruction — the new subagents, commands, and `docs/artifacts/` output stay local to this machine, matching the repo's existing policy. `docs/handoffs/`, `docs/buckets/`, and the `CLAUDE.md`/spec changes are trackable and were committed.

## What's real and working right now

- 13 Claude Code subagents in `.claude/agents/*.md`, each with a real
  input→output contract, cross-referenced (not duplicating) this repo's
  existing 14-role accountability system in `CLAUDE.md`.
- Handoff protocol (`docs/handoffs/handoff-schema.json`) with a working mock
  gate-block demonstration.
- Aider + OpenRouter aliases in `~/.aider.conf.yml`, proven to route correctly
  (fails only on the missing API key, not on config).
- `/task`, `/handoff`, `/qa` slash commands, with `/qa` correctly pointing at
  `tests/smoke/` instead of a nonexistent browser agent.
- `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` set in project settings.

## To actually start using this

1. Put a real OpenRouter key in `.env`'s `OPENROUTER_API_KEY` line.
2. Re-run `aider --model orchestrator --message "ping"` from `archie-oss/` to
   confirm end-to-end.
3. Try `/task <a feature sentence>` in an interactive Claude Code session in
   this repo.
4. Install Node.js when you want Kilo Code / the standalone browser QA agent;
   until then `qa-lead` and `/qa` both fall back to `pytest tests/smoke/`.
