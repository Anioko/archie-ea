# Task Brief: Invalidate Sessions Server-Side on Logout

## Objective
Close a confirmed, live High-severity security finding: logging out does not
invalidate the user's session token. A session cookie captured before logout
(XSS, shared machine, proxy log, browser history sync) continues to
authenticate successfully after the legitimate user has logged out, until
the cookie's natural ~8h expiry.

## Context
Found and reproduced by an authorized security pentest tonight against
production (`https://165-22-125-156.sslip.io`), scoped to read-only/
non-destructive techniques since only production is reachable (no staging
instance exists):

1. Logged in as `qa-solution-architect@example.com`, saved session cookie A.
2. `GET /dashboard/overview` with cookie A → 200 (authenticated).
3. Logged out via `GET /account/logout`.
4. Replayed the original, pre-logout cookie A against
   `GET /dashboard/overview` → **still 200, still authenticated.**

Root cause: this repo uses Flask's default client-side signed session
cookie, with no server-side session store or session-version/nonce check.
Logout presumably clears the client's own cookie, but the cookie's contents
(if captured independently) remain a valid, verifiable token indefinitely
until expiry — there is nothing server-side to revoke.

The pentest also confirmed tenant isolation held under direct-object-
reference testing across two real orgs, and CSRF/SQLi/header checks passed
clean — this bucket is scoped to the logout/session-invalidation finding
only, not a general auth audit.

## Constraints
- This repo already depends on Redis (`app/services/cache_service.py`,
  rate limiting, job queue) — prefer using it rather than introducing a new
  dependency.
- Two viable approaches, pick one and justify:
  1. **Server-side session store** (Flask-Session backed by Redis) — sessions
     become server-tracked records; logout deletes the record; a stolen
     cookie becomes worthless the instant logout runs.
  2. **Per-user session/token version** — add a `session_version` (or
     similar) column to `User`, embed it in the signed session payload at
     login, bump it on logout (and ideally on password change, which may
     have the same gap — check), and reject any request whose session
     payload's version doesn't match the current DB value.
  Consider: Redis is already a soft dependency (code degrades gracefully
  when Redis is unavailable, per `cache_service.py`'s "Redis caching
  disabled" pattern) — a session-store approach that HARD-requires Redis
  for auth to function would be a regression if Redis is down. Whichever
  approach is chosen must degrade safely, not lock out all users, if Redis
  becomes unavailable mid-operation.
- Must not break "Sessions will NOT persist across restarts" behavior
  already documented for missing `SECRET_KEY` (dev-mode warning) — that's
  a separate, known, accepted limitation, not in scope to fix here.
- Apply the same fix consistency to password-change: if a user changes
  their password (e.g. after a suspected compromise), old sessions should
  also stop working — verify current behavior and fix if it has the same
  gap.
- This touches authentication for every user of a live production system.
  No shortcuts on review rigor — full builder → refuter cycle, refuter
  should independently reproduce the pre-fix exploit against a local/test
  instance AND confirm the fix closes it (log in, capture cookie, log out,
  replay cookie, expect 401/redirect-to-login).

## Deliverable
1. Chosen approach (server-side session store or per-user token version),
   implemented.
2. Logout invalidates the session cookie so a captured pre-logout cookie no
   longer authenticates.
3. Password change also invalidates other active sessions for that user
   (verify current behavior first; fix if broken).
4. A regression test proving: login → capture session → logout → replay
   session → expect rejection (401 or redirect to login), not the
   previously-authenticated response.
5. Confirm Redis-unavailable degradation doesn't lock out all users (test
   or reasoned justification either way).

## Acceptance Criteria
- Reproduce the exact pentest steps above against a local/test instance:
  confirm the pre-fix exploit reproduces, then confirm the fix closes it.
- A logged-in user's normal session continues to work correctly for its
  full lifetime (no false-positive invalidation).
- `python scripts/verify.py --tag static` clean.
- `pytest` covering the new regression test passes.
- No regression to existing session/CSRF/login tests.

## Handoff Target
`tech-lead` first — pick the session-store vs. token-version approach and
justify it against this repo's existing Redis-degradation pattern — then
`builder` → `refuter`. This is a live security fix; refuter must
independently re-run the exploit reproduction steps, not just read the
diff. Deploy to production the same session once refuter approves, per
this repo's "Done means DEMONSTRATED, and deployed" standing instruction.
