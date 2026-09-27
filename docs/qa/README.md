# Release qualification operating model

This directory is the shared QA channel for humans, Codex, Claude Code, CI, and
release automation. Chat transcripts are not release evidence. Repository files
are: they are reviewable, versioned, and tied to the code they describe.

## The loop

1. **Test** the immutable candidate commit in a named environment.
2. **Publish** the raw command, result, environment, and artifact paths in a run
   record under `docs/qa/runs/`. Update the readiness matrix and finding ledger.
3. **Triage** every failure as product defect, test defect, environment defect,
   or external evidence gap. Preserve the original failure evidence.
4. **Fix** on a separate branch/worktree. A repair must cite finding IDs and add
   or strengthen a regression test before changing production behavior.
5. **Verify independently**. The implementer may show a focused green test, but
   only the QA lead closes the finding after rerunning the original reproducer,
   the regression test, the affected suite, and the release gates against the
   resulting commit.
6. **Publish again**. Append a new run record; never rewrite a failed run into a
   pass. Record the verified commit and evidence. Repeat until the release rule
   in `fortune-500-readiness-matrix.md` is satisfied.

## Finding states

`open -> in_fix -> ready_for_retest -> verified`

`blocked_external` is allowed only where repository code cannot produce the
evidence. `wont_fix` requires an explicit product/risk decision and never counts
as Fortune 500 ready. A developer or coding agent can move a finding no further
than `ready_for_retest`; it cannot self-certify `verified`.

## Closure controls

A finding is verified only when all of these are recorded:

- the original reproducer now passes;
- an adversarial or regression test would fail if the defect returned;
- relevant neighboring tests and every applicable release gate pass;
- the evidence identifies the exact Git SHA and test environment;
- no test was weakened, skipped, xfailed, baseline-raised, or excluded to obtain
  green without a separately reviewed justification;
- security and tenant-isolation fixes are negative-tested from another role or
  tenant, not merely happy-path tested;
- frontend fixes are exercised in a real browser and, where relevant, at mobile
  and desktop widths with keyboard and accessibility checks.

CI artifacts are authoritative for Linux/PostgreSQL 16, full-history secret
scanning, SBOM generation, and browser runs. Local Windows/PostgreSQL 12 results
are useful diagnostic evidence but cannot substitute for those release gates.

## Concurrent-agent execution

Parallel agents may inspect code and implement independent findings at the same
time. Heavy verification is serialized per host unless each run has isolated
compute. Before starting a full verifier, browser suite, or load test, publish an
active-run record containing the agent, process/session handle, worktree, start
time, command, and database name. Remove it only after recording the outcome.

Every concurrent database-backed run must use its own disposable database. Two
agents must never point at the same `TEST_DATABASE_URL`: shared committed fixture
state, schema reconciliation, and destructive test cleanup make both results
untrustworthy even if both commands report green. A run that used a fallback or
a database shared with another live run is invalidated and must be repeated.

## Files

- `fortune-500-readiness-matrix.md` — release-level acceptance matrix.
- `fortune-500-findings.json` — machine-readable defect and evidence ledger.
- `runs/*.md` — append-only execution records, including failures.

Every agent should read these files before QA or remediation work. Claude Code
can consume them directly because they live in the repository; no proprietary
chat channel or session handoff is required.
