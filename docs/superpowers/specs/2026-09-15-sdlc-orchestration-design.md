# Multi-Agent SDLC Orchestration — v1 Design

## Goal
Replace solo-LLM development with role-based Claude Code subagents that hand off
work through explicit artifacts, plus Aider wired to OpenRouter for focused
coding sessions. Kilo Code and the browser QA agent are deferred (Node.js/npm
not installed on this machine).

## Scope (v1)
- Core SDLC subagent roster (13 roles) in `.claude/agents/`
- Aider + OpenRouter model aliases in `~/.aider.conf.yml`, `.env` for the key
- Handoff protocol: `docs/handoffs/handoff-schema.json` + rules in root `CLAUDE.md`
- Slash commands: `/task`, `/handoff`, `/qa` (the last documents its own dependency)
- `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` in `.claude/settings.local.json`
- `SETUP-REPORT.md` with real validation results

## Out of scope (v1) — deferred
- Kilo Code config (`kilo.jsonc`) — requires the Kilo Code extension, not detected
- Browser QA agent (Playwright/qa_agent) — requires Node.js/npm, not installed
- Extended roster (Enterprise Architect, SRE, Accessibility, Compliance, etc.)
- BMAD method import

## Components

### 1. Directory structure
```
.claude/agents/           (13 role files)
.claude/commands/         (task.md, handoff.md, qa.md)
.claude/settings.local.json  (spawn depth env var)
docs/artifacts/
docs/handoffs/handoff-schema.json
docs/buckets/
qa/qa-config.yml           (config only; agent itself not installed)
```

### 2. Agent roster and permissions
| Agent | Model | Tools |
|---|---|---|
| business-analyst | sonnet | Read, Write(docs/), Task |
| product-manager | sonnet | Read, Write(docs/) |
| solution-architect | opus | Read, Write(docs/), Task |
| data-architect | sonnet | Read, Write(docs/) |
| integration-architect | sonnet | Read, Write(docs/) |
| security-architect | opus | Read, Write(docs/) |
| tech-lead | opus | Read, Write(docs/), Task |
| builder | sonnet | Read, Edit, Write, Bash, Task |
| refuter | opus | Read only |
| qa-lead | sonnet | Read, Write(docs/), Task |
| devops-engineer | sonnet | Read, Write(docs/), Bash |
| release-manager | sonnet | Read, Write(docs/) |
| technical-writer | haiku | Read, Write(docs/) |

Only `builder` gets Edit/Write on source code; every other agent writes only
under `docs/`. `refuter` is read-only by construction (no Edit/Write in its
tool list).

### 3. Aider / OpenRouter
`~/.aider.conf.yml` aliases point at real OpenRouter model slugs (verified
against openrouter.ai naming, not the placeholder names in the original
prompt, e.g. `anthropic/claude-sonnet-4.5` not `claude-sonnet-4`). Validated
by running `aider --model orchestrator --message "Say OK" --yes` against the
repo and confirming a non-error response (requires `OPENROUTER_API_KEY` to be
set — if the user hasn't supplied a key yet, this step reports SKIPPED with
the exact command to run once the key exists, not a fabricated PASS).

### 4. Handoff protocol
JSON schema file plus orchestration rules appended (not replacing) archie-oss's
existing `CLAUDE.md`. Gate check is a real script check (`docs/handoffs/*.json`
`approval_status` field), demonstrated with one mock BA→SA handoff record that
is deliberately left unapproved to prove the gate blocks.

### 5. Validation
`SETUP-REPORT.md` lists each checklist item from the original prompt as
PASS/FAIL/SKIPPED with the literal command run and its output, never an
unverified claim.
