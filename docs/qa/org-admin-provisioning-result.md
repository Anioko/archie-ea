# F500-086 — new organization-administrator provisioning

Candidate only, 2026-09-05. No production data access, role grants, schema
changes, backfill, package installation, commit or deployment.

## Cause and repair

`/admin/team` requires `RBACService.require_role('org_admin')`. That service
reads the explicit `OrgRole` assignment for the authenticated user's own
organization and defaults missing assignments to viewer. Administrator
permission, `is_org_admin`, `is_platform_admin` and the `enterprise_role`
persona do not replace this assignment.

Both `create_admin.py` and `AccountService.register_user` previously created
new organization administrators without that row. Each now flushes the new
user, assigns `org_admin` in the same organization (recording the new owner as
grantor), then commits the user and assignment together. A role-write or final
commit failure rolls back and propagates; registration login and script
success output occur only after successful commit.

The initial-admin existing-user branch is unchanged. Missing assignments and
explicit viewer/architect demotions on existing users are not repaired or
promoted. No request-time grants, guard changes or foreign-organization grants
were introduced. Existing `Role.insert_roles()` behavior remains unchanged.

## Verification

- Initial focused red: **five failed, four passed in 3.19s**. New-owner
  committed snapshots lacked the assignment; the role-failure branch was
  never reached; the existing-user no-op cases already passed.
- Final focused run: **11 passed in 6.11s**, exit 0. Covers both creation
  paths, same-org assignment before commit, existing default organization,
  untouched foreign assignment, missing/viewer/architect/org_admin existing
  identities, and separately injected role-write versus final-commit failure.
  Failure cases assert rollback, no login, no committed partial state and no
  misleading script success output.
- Focused tests execute complete shipped modules with `runpy`, not copied or
  extracted functions. Persistence/model and login boundaries are explicit
  in-memory fixtures; this does **not** prove PostgreSQL transaction behavior.
- `tests/test_org_admin_provisioning_database.py` contains ten shared-rollback
  PostgreSQL cases: persisted owner/assignment, foreign negative and foreign
  assignment preservation, real ORM role-insert failure, final commit failure
  after the role has been flushed, and existing-user assignment preservation.
  Script bootstrap/configuration are fixture-controlled to keep the real
  operation inside the shared rollback session. No SQL/model operations are
  doubled in these database cases. They are **collected only**, not executed
  locally because PostgreSQL is unavailable.

## Remaining qualification and remediation

Existing administrators missing `OrgRole` remain denied, intentionally. They
need a separately scoped, identity-reviewed remediation; rerunning the initial
admin script is not a backfill. Likewise, the current smoke platform-admin
fixture's missing assignment is not silently repaired by this patch.

The prior read-only Chromium investigation proved the current deny-by-default
guard behavior with fixture-controlled role reads. It is not browser evidence
for this new provisioning repair. Real-database CI and a full-app browser
provisioning/team-access journey remain required before deployment acceptance.
Team UI mutations and the explicitly stubbed invite email are separate,
unqualified scope; this change does not claim they work.
