\set ON_ERROR_STOP on

BEGIN;
SELECT pg_advisory_xact_lock(1684220026);

-- Validate reversibility before making any catalogue change.  Any code or
-- ArchiMate identifier reused across tenants makes the old global uniqueness
-- impossible, so the reverse exits non-zero while all cutover objects remain.
DO $reversible$
BEGIN
    IF EXISTS (
        SELECT code
        FROM unified_capabilities
        WHERE code IS NOT NULL
        GROUP BY code
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION
            'capability tenancy reverse refused: tenant duplicate codes require reconciliation';
    END IF;
    IF EXISTS (
        SELECT archimate_id
        FROM unified_capabilities
        WHERE archimate_id IS NOT NULL
        GROUP BY archimate_id
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION
            'capability tenancy reverse refused: tenant duplicate ArchiMate IDs require reconciliation';
    END IF;
END
$reversible$;

DROP INDEX IF EXISTS ix_unified_capabilities_code;
DROP INDEX IF EXISTS ix_unified_capabilities_archimate_id;

CREATE UNIQUE INDEX ix_unified_capabilities_code
    ON unified_capabilities (code);
CREATE UNIQUE INDEX ix_unified_capabilities_archimate_id
    ON unified_capabilities (archimate_id);

DROP INDEX IF EXISTS uq_unified_capabilities_reference_code;
DROP INDEX IF EXISTS uq_unified_capabilities_tenant_code;
DROP INDEX IF EXISTS uq_unified_capabilities_reference_archimate_id;
DROP INDEX IF EXISTS uq_unified_capabilities_tenant_archimate_id;

DROP TRIGGER IF EXISTS trg_unified_capability_write_scope ON unified_capabilities;
DROP FUNCTION IF EXISTS enforce_unified_capability_write_scope();
ALTER TABLE unified_capabilities
    DROP CONSTRAINT IF EXISTS ck_unified_capabilities_scope_owner,
    DROP CONSTRAINT IF EXISTS fk_unified_capabilities_organization,
    DROP CONSTRAINT IF EXISTS fk_unified_capabilities_source_org,
    DROP CONSTRAINT IF EXISTS fk_unified_capabilities_reference,
    DROP CONSTRAINT IF EXISTS fk_unified_capabilities_retired_into;

COMMIT;
