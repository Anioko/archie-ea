# Disaster recovery runbook

Drafted 4 Sep 2026. What exists today, what a genuine off-host DR drill needs
added, and the steps to run one — so provisioning a second environment is the
only remaining blocker, not figuring out the procedure.

## What already exists (on-host)

- `deploy/archie-backup.sh` (via `archie-backup.timer`) — daily `pg_dump -Fc`
  custom-format dump plus a `pg_dumpall --globals-only` (roles/permissions),
  age-pruned at 14 days, with a `pg_restore --list` sanity check and a
  `LAST_SUCCESS` marker so a silently-failing backup is detectable.
- `deploy/verify_backup.sh` — restores the latest dump into a scratch
  database on the **same host** and diffs row counts against the live
  database. This is the drill Codex's report calls "Full database restore
  comparison: 789/789 tables, zero row-count differences" (3 Sep 2026) — real,
  and already run.
- `scripts/pull_backup.py` — pulls a dump from the droplet to a local/other
  machine (`prod_pull/` per `.gitignore`).

## What is missing: genuine off-host recovery

Every backup above lives on the same droplet as the database it protects.
`archie-backup.timer` protects against a bad migration or a mistaken
`DELETE`; it does not protect against the droplet itself being lost — disk
failure, provider account issue, or region outage. `scripts/pull_backup.py`
exists to close this gap but pulling a file to a local machine is not the
same as proving Archie can be *brought back up* from it, on infrastructure
that was never touched by the incident.

**RPO/RTO have never been measured**, because nobody has run the fail-over.
This runbook is what to run once a second environment exists.

## Prerequisites for a real drill (provisioning — not automatable by an agent)

1. A second host/region — a droplet in a different DigitalOcean region, or a
   managed Postgres instance, genuinely isolated from the primary (different
   account/project if budget allows, at minimum a different region and no
   shared storage).
2. Automated off-host replication of the backup artifact — `scripts/
   pull_backup.py` run on a schedule from the second host (pull model, so a
   compromised primary cannot also delete the off-host copy), or object
   storage (DigitalOcean Spaces / S3-compatible) as the intermediate target.
3. A copy of the application image/release artifact reachable from the second
   host — the same immutable image `deploy/deploy.sh` promotes to primary.

None of this needs new code; `scripts/pull_backup.py` already does the pull
half. It needs a second piece of infrastructure to pull *to*, which is a
budget/provisioning decision (see `docs/qa/pentest-scope.md`'s note on the
same class of decision, and CLAUDE.md's "Own the decision" section on what
is the owner's to decide).

## Drill procedure, once the second environment exists

1. **T0 — declare the drill.** Record the exact backup artifact being used
   (filename, `LAST_SUCCESS` marker timestamp) and the primary's current git
   SHA (`git rev-parse HEAD` on the droplet) as the recovery target.
2. **Provision** the second environment fresh — do not reuse a
   previously-configured one, or the drill measures "restart a warm standby"
   rather than "recover from nothing," which is the actual failure mode.
3. **Deploy the application** to the second environment via the same
   `deploy/deploy.sh` immutable-image mechanism used on primary, pointed at
   the second host.
4. **Restore the database** from the off-host backup artifact using the same
   restore logic `verify_backup.sh` already exercises on-host — adapt its
   Section 2 (fresh dump + restore) to target the second host's database
   instead of a same-host scratch database.
5. **Row-count and checksum comparison** against the last known-good figures
   from the primary at T0 (reuse `verify_backup.sh`'s comparison logic).
6. **Run the full synthetic-journey suite** (`tests/smoke/`, per-persona)
   against the recovered environment — a database that restores with correct
   row counts but an application that cannot boot against it (schema drift,
   missing `reconcile-schema` run) is not a recovered service. Run `flask
   --app manage reconcile-schema` on the restored environment before the
   smoke suite, matching the documented boot chain.
7. **Record RTO** — wall-clock time from T0 to the smoke suite going green
   on the second environment. **Record RPO** — the gap between the backup
   artifact's timestamp and the incident declaration time (bounded above by
   the backup schedule interval; `archie-backup.timer`'s current cadence sets
   the RPO ceiling until it changes).
8. **Publish the result** as a `docs/qa/runs/` entry and, if it reveals a
   defect (a missing environment variable, a manual step that should be
   scripted, a schema-drift surprise), log it as an `F500-###` finding in
   `docs/qa/fortune-500-findings.json` rather than only fixing it quietly —
   the next drill needs to know the previous one found something.

## What this runbook deliberately does not decide

Which second environment to provision, and its ongoing cost, is a budget
decision — not attempted here. This runbook is the procedure to run the
moment that decision is made, so the 1-3 week "external assurance" clock
starts on provisioning, not on re-deriving the steps.
