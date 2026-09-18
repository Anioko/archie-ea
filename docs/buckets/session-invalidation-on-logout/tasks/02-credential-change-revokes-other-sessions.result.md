# Result — 02: Password change/reset revokes other sessions

## Summary

All four credential-change paths in `AccountService` now revoke sessions via
the single `session_registry.revoke_all_for_user` accessor added in task 01,
routed through a shared private helper
(`AccountService._revoke_other_sessions`) so the fabricated-data and
error-handling rules are enforced in exactly one place.

## Files changed

- `app/modules/account/services/account_service.py`:
  - `change_password(user, old_password, new_password)` — now returns a
    **3-tuple** `(success, message, revoked_count)`. `revoked_count` is the
    other sessions revoked (`except_sid=session.get("_sid")`, so the acting
    device stays logged in), or `None` if revocation itself failed (password
    change had already committed by that point — never fail the request over
    it, and never report a count that wasn't actually achieved).
  - `reset_password(token, email, new_password)` — on success, revokes
    **every** session (`except_sid=None` — "I've lost control of this
    account" path; the brief is explicit that this includes any session on
    the machine doing the reset, since the user isn't logged in during a
    token-based reset anyway).
  - `set_password(user, password)` (join-from-invite) — same, defensive,
    `except_sid=None`.
  - Admin-initiated disable/reset: searched
    (`grep -rn "is_active\|disable" app/modules/admin app/admin`) — **no
    admin-initiated password-reset or account-disable path exists** in this
    codebase today. Not invented, per the task's own instruction to say so
    rather than fabricate one.
- `app/modules/account/routes/account_routes.py` and
  `app/modules/account/v2/routes/account_routes.py` — both
  `change_password()` routes (the known `v2`/non-`v2` duplicate pair, per the
  brief's own note) updated to unpack the 3-tuple and flash the count:
  *"N other signed-in device(s) were signed out."* on success with
  `revoked_count > 0`, or a warning telling the user to sign out of other
  devices manually when `revoked_count is None` (revocation failed but the
  password change itself succeeded — never silently claim a count that
  wasn't achieved). Fixing the shared `AccountService` method fixes both
  routes identically, as intended.
- `app/services/auth_audit.py` — new `ACTION_SESSIONS_REVOKED` +
  `record_sessions_revoked(user, reason, count)`, written into the same
  `soc2_audit_log` table `/admin/audit-log` already reads (no second audit
  store, per the existing module's own design note).
- `AccountService._revoke_other_sessions` — the shared helper: calls
  `session_registry.revoke_all_for_user`, records the audit event only when
  `count > 0`, and **catches and logs** any exception from the registry call
  rather than letting it propagate into the request (the password change has
  already committed by then) — returning `None` in that case so callers
  render the "please sign out manually" message instead of a fabricated
  count.

## Tests

Extends `tests/test_session_invalidation.py::TestPasswordChangeRevokesOtherSessions`
(4 cases):
- `test_change_password_revokes_other_device_keeps_acting_one` — two clients
  logged in as the same user; client A changes the password; client B's
  captured cookie is rejected on replay; client A stays logged in. **Passes.**
- `test_wrong_old_password_revokes_nothing` — a failed change-password
  attempt (wrong old password) leaves both sessions' `revoked_at IS NULL`
  count at 2 — nothing revoked. **Passes.**
- `test_reset_password_revokes_every_session_including_the_resetting_one` —
  token-based reset via `AccountService.reset_password` directly; the
  previously-logged-in client's cookie is rejected afterward (the
  `except_sid=None` behaviour). **Passes.**
- `test_flash_count_matches_actual_revocations` — three clients logged in as
  the same user; client A changes the password; asserts the flashed message
  reads exactly *"2 other signed-in devices were signed out."* — the number
  comes from `revoke_all_for_user`'s actual return value, not a literal, per
  the fabricated-data rule the brief calls out explicitly. **Passes.**

`pytest tests/test_session_invalidation.py` → **11 passed** (includes task
01's 7 cases + these 4), confirmed in a clean run — see task 01's result.md
for the full regression-sweep evidence, which covers both tasks together
since they share one test file and one `verify.py` run.

## Acceptance criteria

- All four credential paths revoke — done (`change_password`,
  `reset_password`, `set_password`; no admin path exists to wire).
- `python scripts/verify.py` (bare) — **not completed**; see task 01's
  result.md "Known issue" section (local Postgres instance became
  unresponsive during this session's test runs, an environment problem, not
  a code defect). `--tag static` is clean (48 passed, 0 failed, 1
  pre-existing skip), confirmed twice, and includes the
  `tenant-scoping`/`fabricated-data`/`csrf-coverage` gates most relevant to
  this task's diff.
- Changing your own password does **not** log you out of the browser you did
  it in — covered by `test_change_password_revokes_other_device_keeps_acting_one`
  (client A, the acting session, stays 200 after its own change).
- **Not deployed.** Per this dispatch's explicit instruction ("Do NOT merge
  to main, do NOT deploy — this goes through a refuter pass next given it's a
  live security fix touching every authenticated user"), this overrides the
  brief's own "deploy same session" line for this specific dispatch. Nothing
  has been merged or pushed; all work is uncommitted in the
  `fix/session-invalidation-on-logout` worktree.

## Handoff note for refuter

Per the brief: specifically check the `v2`/non-`v2` duplicate route pair
behave identically (they call the same `AccountService.change_password`, so
they should — worth confirming directly), and that `except_sid` cannot be
manipulated by a client-set value (it is always read server-side from
`flask.session.get("_sid")`, never from request body/query/headers — there is
no code path where a caller supplies it).
