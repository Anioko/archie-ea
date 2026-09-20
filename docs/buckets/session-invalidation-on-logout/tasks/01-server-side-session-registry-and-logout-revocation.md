# Task 01 — Server-side session registry + logout revocation

**Handoff target:** `builder` → `refuter` (mandatory, exploit-reproduction review)
**Bucket:** `docs/buckets/session-invalidation-on-logout/`
**Depends on:** nothing. Task 02 depends on this one.

---

## Objective

Make a session cookie captured before logout stop authenticating the moment
logout runs. Today it keeps working until natural expiry (confirmed live
against production; see `../brief.md`). Close that by giving every login a
server-side session record that the request path checks and that logout
deletes.

---

## Context — verified against this worktree, not assumed

Read these before writing anything; the findings below are the design inputs.

**There is no server-side session store.** Flask's default client-side signed
cookie is all there is. `config.py` sets only cookie attributes
(`SESSION_COOKIE_HTTPONLY`/`SAMESITE`/`SECURE`, `PERMANENT_SESSION_LIFETIME =
8h`, `REMEMBER_COOKIE_DURATION = 30d`, `SESSION_REFRESH_EACH_REQUEST = True`).
`Flask-Session` is **not** in `requirements.txt`. So the cookie IS the
credential and nothing server-side can revoke it.

**Logout only clears the client's copy.** Three logout paths exist, all
equivalent and all insufficient:
- `app/modules/account/routes/account_routes.py:146` `logout()` → `_svc.logout()`
- `app/modules/account/v2/routes/account_routes.py:138` `logout()` → `_svc.logout()`
- `app/_bootstrap/routes.py:504` `api_logout()` → bare `logout_user()`

`AccountService.logout()` (`app/modules/account/services/account_service.py:56`)
is exactly `logout_user()`. Flask-Login's `logout_user()` pops `_user_id` /
`_fresh` / `_id` from the *current* session and asks the browser to drop the
remember cookie. A copy of the cookie taken earlier is untouched and still
verifies against `SECRET_KEY`. That is the whole bug.

**Flask-Login is in use** (`Flask-Login>=0.6.3`, `app/extensions/__init__.py`),
with `login_manager.session_protection = "basic"`. `"basic"` only marks a
session non-fresh when the client identifier changes — it never rejects, so it
does nothing for this finding. `"strong"` would clear the session on identifier
mismatch but is still client-derived (User-Agent + IP hash), is trivially
matched by an attacker replaying from the same context, and breaks users behind
rotating egress IPs. **Do not "fix" this by switching to `strong`.**

`@login_manager.user_loader` is `load_user` in `app/models/user.py:429` — a
plain `db.session.get(User, int(user_id))`. `User.get_id()` is Flask-Login's
default (`UserMixin`), returning `str(self.id)`.

**Nine `login_user(...)` call sites** must all mint a session record:
```
app/_bootstrap/routes.py:481                                 (POST /api/auth/login)
app/modules/auth/sso_routes.py:116                           (SSO/OIDC callback)
app/modules/account/services/account_service.py:53, 104      (form login; auto-login after register)
app/modules/account/v2/routes/account_routes.py:521, 594
app/modules/account/routes/account_routes.py:530, 607        (login_user(user, remember=True))
```
Centralise — do not patch nine sites with copy-pasted logic (ADR 0008: one
accessor per concept).

**An idle-timeout `before_request` hook already exists and is the component
this task extends** — `app/_bootstrap/session_policy.py`, `init_session_policy(app)`.
It already: stores `_last_activity_at` in the signed session, runs on every
request, exempts `static`/`/health`/`/version`/`csp_report`, distinguishes
JSON callers (401 JSON body) from browser callers (redirect to
`account.login`), and calls `logout_user()` + `session.clear()` on expiry.
**Per ADR 0008 the revocation check goes in this module, reusing that exemption
list and that response-shaping branch — do not add a second
authentication `before_request` hook elsewhere.**

**Redis is NOT genuinely wired here.** `app/services/core/cache_service.py`
connects only when `ENABLE_REDIS_CACHE=true` (default `"false"`), never pings,
and logs `"Redis caching disabled"` otherwise. `config.py` defines `REDIS_URL`
defaulting to `redis://localhost:6379/0` for RQ/Celery. Treat Redis as an
optional accelerator that is currently off, not as available infrastructure.

---

## Decision — session registry table in PostgreSQL. Justified.

Build **a per-session server-side record in the existing PostgreSQL database**,
keyed by a random session id (`sid`) carried inside the signed session cookie.

**Rejected: Flask-Session + Redis (brief option 1).** It makes authentication
hard-dependent on a service that, as measured above, is *off by default in this
codebase* and degrades silently everywhere else it is used. If Redis is
unreachable, every user is either locked out (fail-closed) or the fix is void
(fail-open). The brief explicitly forbids that trade. It also adds a dependency
and moves session storage out of the store we already back up.

**Rejected: a single per-user `session_version` column (brief option 2).** It
cannot express "log this device out" — logging out of a laptop silently kills
the phone. It also needs a new column on `users`, and `reconcile-schema` only
adds *nullable* columns, so every existing row arrives `NULL` and needs
NULL-tolerant comparison logic forever. A **new table**, by contrast, is created
cleanly by `flask init-db` (`create_all` creates missing tables), which sidesteps
the drift hazard in `CLAUDE.md`'s schema section entirely.

**Chosen approach's degradation story:** the database is already a hard
dependency — if Postgres is down, no page renders and no user is logged in
regardless. So this fix adds no new single point of failure. Redis is not
involved. Cost is one indexed primary-key lookup per authenticated request, in
a `before_request` that already runs.

---

## Deliverable

### 1. Model — `app/models/user_session.py`

```python
class UserSession(db.Model):
    __tablename__ = "user_sessions"
    sid            = db.Column(db.String(64), primary_key=True)   # secrets.token_urlsafe(32)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    organization_id= db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    created_at     = db.Column(db.DateTime, nullable=False, default=<utcnow>)
    last_seen_at   = db.Column(db.DateTime, nullable=True)
    revoked_at     = db.Column(db.DateTime, nullable=True, index=True)
    revoked_reason = db.Column(db.String(32), nullable=True)   # 'logout' | 'password_change' | 'idle_timeout' | 'admin'
    ip             = db.Column(db.String(45), nullable=True)
    user_agent     = db.Column(db.String(255), nullable=True)
```

- **Do NOT add `TenantMixin`.** This table is read in the pre-authentication
  part of the request, before `g.current_org_id` is meaningful; a
  `do_orm_execute` filter here would break login. `organization_id` is stored
  as data for later admin surfacing, and every query in this task is keyed by
  `sid` or `user_id`, both of which are already user-scoped. Put a comment on
  the class saying exactly this, so the next reader does not "fix" it.
- Export from `app/models/__init__.py` so `create_all()` sees it.

### 2. Service — `app/services/session_registry.py` (the single accessor)

```python
def issue(user, remember=False) -> str      # mint sid, insert row, session["_sid"] = sid, commit
def is_active(sid) -> bool                  # row exists and revoked_at is None
def revoke(sid, reason)                     # set revoked_at/revoked_reason (idempotent)
def revoke_all_for_user(user_id, reason, except_sid=None)
def touch(sid)                              # best-effort last_seen_at (see throttling below)
def purge_expired(older_than)               # for the CLI in §6
```

`revoke` sets `revoked_at` rather than deleting, so "when and why did this
session end" is answerable by query (ADR 0008 rule 4: retire, never lose).

### 3. Mint on login — one wrapper, nine call sites

Add `app/services/session_registry.py::login_and_register(user, remember=False)`
that does `session.clear()` (session-fixation hygiene — `_bootstrap/routes.py:479`
already does this manually), `login_user(user, remember)`, `session.permanent =
True`, then `issue(user, remember)`. Replace **all nine** `login_user(...)` call
sites listed above with it, preserving each site's existing `remember` argument.

### 4. Enforce — extend `app/_bootstrap/session_policy.py`

Inside the existing `_enforce_idle_timeout` hook (rename it to reflect it now
enforces both, e.g. `_enforce_session_policy`), after the `authenticated` check
and **before** the idle comparison:

```
sid = session.get("_sid")
if not sid or not session_registry.is_active(sid):
    logout_user(); session.clear()
    -> reuse the EXISTING wants_json branch: 401 JSON {"code": "session_revoked"}
       or redirect(url_for("account.login", timeout="revoked"))
```

Fail **closed**: a missing `_sid` is a rejection. Consequence, and it is
intended: at deploy every currently-live session is logged out once — including
the cookies the pentester captured. Say so in the release note.

Guard the DB read with `try/except` → on `OperationalError`, log and reject
(fail closed); do not swallow into a pass. The DB being down means the page
cannot render anyway.

**`last_seen_at` write throttling:** only `touch(sid)` when `last_seen_at` is
older than 60s, so this is not a write on every request.

### 5. Revoke on logout — all three logout paths

- `AccountService.logout()` → `revoke(session.get("_sid"), "logout")` before
  `logout_user()`, then `logout_user()` (which also clears the remember cookie).
- `app/_bootstrap/routes.py::api_logout` → same, via the service, not inline.
- Idle timeout in `session_policy.py` → `revoke(sid, "idle_timeout")`.

**Remember-me:** `REMEMBER_COOKIE_DURATION` is 30 days and `login_user(user,
remember=True)` is used at `account_routes.py:530,607`. A captured *remember*
cookie re-authenticates with no `_sid`, so §4 rejects it — correct and
fail-closed. But that also breaks legitimate remember-me. Resolve it
explicitly: on logout call `revoke_all_for_user(user_id, "logout")` **and** rely
on `logout_user()` clearing the remember cookie; on a fresh remember-cookie
login (Flask-Login sets `session["_fresh"] = False` and no `_sid` exists),
`login_and_register` is not invoked, so instead have the `session_policy` hook
mint a new record for a non-fresh authenticated session **only if the user has
no `revoked_at IS NULL` record revoked in the last `REMEMBER_COOKIE_DURATION`
by reason `logout`** — if the simplest correct implementation of that proves
convoluted, the acceptable alternative is to **disable remember-me** (drop the
`remember=True` at those two call sites and the login form's checkbox) and note
it. Security beats convenience here; state which option you took and why.

### 6. Housekeeping CLI

`flask --app manage purge-sessions [--older-than-days 30]` calling
`purge_expired`, so the table does not grow without bound. Register in
`app/_bootstrap/cli.py` alongside the existing commands.

### 7. Tests — `tests/test_session_invalidation.py`

Use the **shared** fixtures in `tests/conftest.py` (`app`, `db_session`,
`make_org`, `tenant_ctx`) — follow `tests/test_tenant_isolation.py`, not the
hand-rolled module-scoped pattern in older files.

Required cases:
1. **The exploit, as a regression test.** Log in via `/account/login` with a
   test client; capture the raw `session` cookie value; hit
   `/dashboard/overview` → 200; `GET /account/logout`; build a **fresh client**,
   set the captured cookie, hit `/dashboard/overview` → expect 302→login (or
   401 for a JSON caller), **not** 200. This test must fail on `main`.
2. Same for `POST /api/auth/logout` (JSON path, expects 401 + `session_revoked`).
3. Happy path: a normal session survives many requests and is not
   falsely invalidated; `last_seen_at` advances.
4. Idle-timeout path still behaves as `tests/` currently asserts, and now also
   writes `revoked_reason='idle_timeout'`.

Plus a `tests/smoke/` journey (required by the `smoke-coverage-on-change`
gate if templates change; add it regardless): a Playwright persona logs in,
logs out, and the back-button/replayed navigation lands on the login page.

---

## Constraints

- **Extend `app/_bootstrap/session_policy.py`**; do not create a second
  auth-enforcing `before_request`.
- One accessor: all revocation/minting goes through
  `app/services/session_registry.py`. No inline `UserSession.query` in routes.
- New **table** only — do not add a column to `users` in this task.
  `flask init-db` creates it; do not write an Alembic migration (`migrations/`
  is historical, deploys do not run `db upgrade`).
- No new dependency. No Redis requirement on the auth path.
- Do not change `session_protection` to `"strong"`.
- No `console.*`, no `print()` in handlers; log via the module logger.
- Authoring goes through Aider per `CLAUDE.md`
  (`aider --model coder --no-auto-commits --yes --no-stream --message "..." <files>`);
  `export PYTHONIOENCODING=utf-8` first, and re-read every touched file after
  Aider reports success.

---

## Acceptance criteria

- The pre-fix exploit reproduces on `main` and the new test proves it
  (demonstrate both directions — a test that passes before the fix proves
  nothing).
- `pytest tests/test_session_invalidation.py` green; no regression in
  `tests/test_tenant_isolation.py`, `app/modules/account/tests/`, or existing
  session/CSRF/login tests.
- `python scripts/verify.py` (bare, not `--tag static`) green.
- A logged-in user's session works for its full lifetime — no false
  invalidation across ≥20 consecutive requests including API calls.
- Postgres-down behaviour is fail-closed and produces a logged error, not a
  silent pass.
- Release-note line stating that deploying this logs every current user out
  once, by design.

## Handoff target

`builder`, then **`refuter` (Claude subagent, not the Aider reviewer alias — this
is a live auth fix, the final gate class `CLAUDE.md` reserves for real refuter
rounds)**. Refuter must independently run the capture-cookie → logout → replay
sequence against a local instance, before and after, and must specifically probe:
replay of the *remember* cookie after logout, replay after an idle timeout,
and whether any `login_user(` call site was missed (`grep` for it).
