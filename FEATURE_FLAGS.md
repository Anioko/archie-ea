# Feature-flag inventory — your line of sight

**Rule:** product features ship **ON** and wired. Nothing user-facing hides behind a
switch. This file is the single place you can see the on/off state of everything.
The `no-dark-features` guardrail (pre-commit + CI) blocks any new product feature
that defaults OFF. Regenerate/verify with `python scripts/guardrails/no_dark_features.py --all`.

_Last verified: 2026-07-14 against the deployed instance (134.122.105.56)._

## Product features — MUST be ON

| Flag | Gates | Where | State |
|---|---|---|---|
| `ENABLE_NORTH_STAR_NAV` | ArchiMate layered navigation (Phase 1) | config (default ON) | 🟢 ON |
| `north_star_navigation` | ↑ same, DB switch | DB feature_flags | 🟢 ON |
| `ENABLE_NORTH_STAR_PHASE2` / `north_star_phase2` | Full 55-element ArchiMate nav (Phase 2) | DB feature_flags | 🟢 ON |
| `AI_PAGE_GUIDE_ENABLED` | In-app "Ask the guide" AI helper | `.env` | 🟢 ON |
| `ENABLE_LOCAL_EMBEDDINGS` | Semantic search via bundled local model | `.env` | 🟢 ON |
| `USE_PGVECTOR` | Indexed vector search | `.env` | 🟢 ON |
| `USE_BLUEPRINT_PAGE` | Blueprint solution UI + proactive AI | env (default OFF) | 🔴 **OFF — dark; turning on** |
| `ABACUS_ENABLED` | Abacus/Avolution portfolio import | env + creds | 🔴 OFF (needs Abacus credentials) |

## Operational config — allowed to be off (not features)

| Flag | Purpose | State |
|---|---|---|
| `FLASK_CONFIG` | deploy-env selector | `production` |
| `TRUST_PROXY` / `PREFERRED_URL_SCHEME` | reverse-proxy / HTTPS | on / https |
| `CELERY_ENABLED` | async worker (perf) | 🔴 off (imports run inline) |
| `ENABLE_REDIS_CACHE` | cache (perf) | 🔴 off |
| `USE_READ_REPLICA_FOR_DASHBOARD` | read replica (perf) | 🔴 off |
| `OTEL_ENABLED` | observability | 🔴 off |
| `USE_*_GUARDRAILS` / `USE_NEW_*` | v2 module routing (architectural) | 🟢 on (forced) |

## External secrets/keys — you supply these

| Key | State | Impact if unset |
|---|---|---|
| `SECRET_KEY` | 🟢 set | — |
| `DEEPSEEK_API_KEY` | 🟢 set | AI chat works |
| `CREDENTIAL_ENCRYPTION_KEY` | 🟢 set | connectors can save creds |
| `OPENAI/ANTHROPIC/GEMINI/OPENROUTER_API_KEY` | 🔴 unset | optional extra providers (DeepSeek covers chat) |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | 🔴 **unset** | **password-reset & teammate invites silently do nothing** — the one thing blocking self-serve team onboarding |

> **The only thing dark and actionable right now:** `MAIL_*` (needs your SMTP
> credentials) and `USE_BLUEPRINT_PAGE` (a product feature — being turned on).
> Everything else product-facing is ON.
