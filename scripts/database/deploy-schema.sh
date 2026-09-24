#!/bin/sh
# One-shot schema-owner container. Runtime web/worker containers never receive
# DATABASE_ADMIN_URL or DATABASE_DEPLOY_PASSWORD.
set -eu

flask --app manage init-db
flask --app manage reconcile-schema
flask --app manage backfill-ai-chat-approval-org || echo 'WARN AI chat approval tenancy backfill skipped - legacy approvals remain unavailable for review until requester organization ownership is restored'
flask --app manage backfill-review-queue-org || echo 'WARN review queue backfill skipped - existing review items stay hidden until they are attributed to an organization'
flask --app manage backfill-archimate-layer-casing || echo 'WARN archimate layer casing backfill skipped - ArchiMate elements stored with a capitalised layer will not match any query until it runs'
flask --app manage backfill-layer-tenancy || echo 'WARN layer tenancy backfill skipped - newly tenant-scoped tables keep nullable organization_id until it runs; rows left NULL are invisible to every org'
flask --app manage backfill-value-stream-tenancy || echo 'WARN value-stream tenancy backfill skipped - run manually with --org-id'
flask --app manage backfill-principle-org || echo 'WARN principle tenancy backfill skipped - run manually with --org-id'
flask --app manage backfill-initiative-org || echo 'WARN initiative tenancy backfill skipped - run manually with --org-id'
flask --app manage backfill-kanban-card-org || echo 'WARN kanban card tenancy backfill skipped'
flask --app manage backfill-saved-diagram-tenancy || echo 'WARN saved-diagram tenancy backfill skipped - composer diagrams keep nullable organization_id until it runs; rows left NULL are invisible to every org (CMP-01)'
flask --app manage drop-audit-log-viewpoint-fk || echo 'WARN audit-log viewpoint-FK drop skipped - composer audit writes keep failing with a FK violation until it runs (CMP-03)'
flask --app manage backfill-architect-role

# ADR 0008 -- give unified_capabilities (the canonical capability store, per
# app/models/unified_capability.py and docs/adr/0008-one-system-of-record.md) a
# producer. Must run after reconcile-schema (provenance columns) and after every
# backfill-*-tenancy step above (an ownerless business_capability row is
# blocker 1 in app/commands/project_capabilities.py and would abort the
# projection). The migration step is NOT suppressed: it only creates an index
# (CREATE UNIQUE INDEX IF NOT EXISTS), is a no-op on a database where it already
# ran, and project-capabilities cannot run without it -- silencing a failure
# here would silently leave the projection permanently blocked with no signal.
flask --app manage apply-unified-capability-provenance-migration
# Corrected 17 Sep 2026 -- this comment previously said project-capabilities
# was deliberately NOT suppressed. That was wrong: run_projection() can raise
# ProjectionBlocked for any one of five reasons (app/commands/project_capabilities.py),
# several of which are a SINGLE tenant's bad data (a tenant_code_collision or
# archimate_id_collision belonging to one org), not a global schema problem. With
# `set -eu` and this line unsuppressed, that one tenant's bad row aborted schema
# deploy for EVERY tenant on the box -- the exact blast-radius mistake the other
# backfill-* lines above already avoid with `|| echo WARN`. Matching that
# convention here: a blocked projection is loud (stderr WARN + whatever
# project-capabilities itself already logs) but non-fatal, so unrelated tenants
# still get a working boot while the blocked tenant's projection is fixed
# separately. `unified_capabilities` staying stale for one tenant is a `store-agreement`/
# `canonical-store` finding to chase down, not a reason to 503 the whole platform.
# Corrected again 17 Sep 2026 (round 3) -- `owner_or_code_changed_since_projection`
# is no longer one of the reasons this command aborts its whole run: it is now a
# per-row skip (report["skipped"]), not a hard blocker, so THIS WARN firing means
# one of the four remaining hard blockers (ownerless_source_rows,
# tenant_code_collision, archimate_id_collision, source_hierarchy_cycle) or a lock
# conflict / missing index, not a moved row.
flask --app manage project-capabilities --apply --report /tmp/project-capabilities-report.json \
    && echo 'project-capabilities --apply succeeded' \
    || echo 'WARN capability projection blocked (see logs / /tmp/project-capabilities-report.json) - unified_capabilities may be stale for one or more tenants until the blocker (ownerless_source_rows, tenant_code_collision, archimate_id_collision, source_hierarchy_cycle, missing provenance index, or a competing cutover/projection lock) is resolved and project-capabilities --apply is re-run. A moved/re-parented row (owner_or_code_changed_since_projection) is no longer a reason this fires -- it is skipped per-row and reported in the report JSON, not blocked.' >&2
if [ -f /tmp/project-capabilities-report.json ]; then
    echo '--- project-capabilities report ---'
    cat /tmp/project-capabilities-report.json
    echo '--- end report ---'
fi
