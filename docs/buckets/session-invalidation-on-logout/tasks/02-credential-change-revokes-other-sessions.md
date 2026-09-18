# Task 02 — Password change / reset revokes all other sessions

**Handoff target:** `builder` → `refuter`
**Bucket:** `docs/buckets/session-invalidation-on-logout/`
**Depends on:** Task 01 (uses `app/services/session_registry.py`). Do not start
until Task 01's handoff is `approved`.

---

## Objective

Make changing or resetting a password terminate every *other* active session
for that account. This is the same class of defect as the logout finding: a
user who suspects compromise changes their password and the attacker's stolen
cookie keeps working.

---

## Context — verified in this worktree

The gap is confirmed, not suspected. All four credential-change paths write the
new hash and return; none touches the session:

- `app/modules/account/services/account_service.py:147` `change_password(user,
  old_password, new_password)` — `verify_password` → `user.password = new` →
  `db.session.commit()` → return. Nothing else.
- `app/modules/account/services/account_service.py:134` `reset_password(token,
  email, new_password)` — delegates to `User.reset_password`; same shape.
- `app/modules/account/services/account_service.py:249` `set_password(user,
  password)` — the join-from-invite path.
- `User.password` setter (`app/models/user.py:273`) is a plain
  `generate_password_hash`; there is no model-level hook to piggyback on.

Routes reaching these: `/account/manage/change-password` in **both**
`app/modules/account/routes/account_routes.py:266` and
`app/modules/account/v2/routes/account_routes.py:241` (the `USE_*_GUARDRAILS`
duplicate pair — both must be correct, and both call the same
`AccountService`, so fixing the **service** fixes both).

**This is why the fix belongs in `AccountService`, not in the routes**
(ADR 0008: one accessor per concept). The `v2` and non-`v2` route files are a
known duplicate pair; putting the revocation in either route file guarantees
the other is wrong.

---

## Deliverable

1. In `AccountService.change_password`, after the successful `db.session.commit()`:
   ```
   session_registry.revoke_all_for_user(
       user.id, reason="password_change", except_sid=flask.session.get("_sid")
   )
   ```
   `except_sid` keeps the acting user logged in on the device they just used —
   otherwise a routine password change bounces them to the login screen, which
   trains users to distrust the feature. Every *other* device is terminated.

2. Same call in `AccountService.reset_password` on success — but with
   **`except_sid=None`**. A reset is the "I've lost control of this account"
   path; kill everything, including any session on the machine doing the reset.
   The user is not logged in during a token-based reset anyway.

3. Same call in `AccountService.set_password` (join-from-invite),
   `except_sid=None` — defensive; there should be no prior session.

4. If an admin-initiated password reset or user-disable path exists
   (`grep -rn "is_active\|disable" app/modules/admin app/admin`), wire it too
   with `reason="admin"`. If one does not exist, say so in the report rather
   than inventing one.

5. Surface it: the account page (`app/templates/account/manage.html`, which
   already renders `recent_auth_events` from `app/services/auth_audit.py`)
   should show a line stating how many other sessions were ended, via the
   existing flash on success — e.g. *"Your password has been updated. 3 other
   signed-in devices were signed out."* Use `—` conventions and the existing
   flash categories; no new macro. Count comes from
   `revoke_all_for_user`'s return value (make it return the count).

6. Record the event through the existing `app/services/auth_audit.py`
   (the same module `record_logout` / `record_login_failure` live in) so
   `/admin/audit-log` shows it. Do not add a second audit store.

---

## Tests — extend `tests/test_session_invalidation.py` (created in Task 01)

- Two clients logged in as the same user; client A changes its password;
  client B's replayed cookie → redirect to login; client A still 200.
- Token reset path: client A logged in, password reset via token from a
  different client → A's cookie rejected.
- The flash count matches the number of sessions actually revoked (this is a
  displayed number — it must come from the query, never a literal; the
  `fabricated-data` gate covers exactly this).
- Wrong-old-password attempt revokes **nothing**.

---

## Constraints

- Fix in `AccountService`, not in either route file.
- No new table, no new column — Task 01's `user_sessions` carries this.
- `revoke_all_for_user` must be idempotent and must not raise into the request
  path if the DB write fails after the password commit succeeded: the password
  change has already happened, so log an error and flash a warning telling the
  user to sign out of other devices manually. Never report "3 devices signed
  out" when the revocation failed.
- Authoring via Aider per `CLAUDE.md`; re-read files after each reported edit.

## Acceptance criteria

- All four credential paths revoke; tests above pass.
- `python scripts/verify.py` (bare) green.
- Changing your own password does **not** log you out of the browser you did it
  in.
- Deployed to production in the same session as Task 01, per "Done means
  DEMONSTRATED, and deployed" — with a browser walkthrough as a real persona
  (`archie-prod-demo-account-credentials`): log in on two browsers, change the
  password in one, confirm the other is signed out on next navigation.

## Handoff target

`builder`, then `refuter` (Claude subagent — auth class). Refuter should
specifically check the `v2` / non-`v2` duplicate route pair both behave
identically, and that `except_sid` logic cannot be manipulated by a client-set
value.
