\set ON_ERROR_STOP on

-- Run only after `cutover-capability-tenancy --apply` has classified and
-- deduplicated the maintenance copy.  The maintenance window deliberately uses
-- one transaction: a late validation failure must restore every legacy guard.
BEGIN;
SELECT pg_advisory_xact_lock(1684220026);

ALTER TABLE unified_capabilities
    ADD COLUMN IF NOT EXISTS organization_id INTEGER,
    ADD COLUMN IF NOT EXISTS scope VARCHAR(16),
    ADD COLUMN IF NOT EXISTS reference_capability_id BIGINT,
    ADD COLUMN IF NOT EXISTS source_table VARCHAR(128),
    ADD COLUMN IF NOT EXISTS source_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS source_org_id INTEGER,
    ADD COLUMN IF NOT EXISTS source_checksum VARCHAR(64),
    ADD COLUMN IF NOT EXISTS retired_into_id BIGINT;

DO $classification$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM unified_capabilities
        WHERE scope IS NULL
           OR scope NOT IN ('reference', 'tenant')
           OR (scope = 'reference' AND organization_id IS NOT NULL)
           OR (scope = 'tenant' AND organization_id IS NULL)
    ) THEN
        RAISE EXCEPTION
            'capability tenancy constraint swap refused: classification is incomplete or inconsistent';
    END IF;
END
$classification$;

-- Remove any invalid remnants from an interrupted historical concurrent build,
-- then build all replacements while the old global guards still exist.  These
-- drops/rebuilds are failure-atomic because they are in this transaction.
DROP INDEX IF EXISTS uq_unified_capabilities_reference_code;
DROP INDEX IF EXISTS uq_unified_capabilities_tenant_code;
DROP INDEX IF EXISTS uq_unified_capabilities_reference_archimate_id;
DROP INDEX IF EXISTS uq_unified_capabilities_tenant_archimate_id;

CREATE UNIQUE INDEX uq_unified_capabilities_reference_code
    ON unified_capabilities (code)
    WHERE organization_id IS NULL;
CREATE UNIQUE INDEX uq_unified_capabilities_tenant_code
    ON unified_capabilities (organization_id, code)
    WHERE organization_id IS NOT NULL;
CREATE UNIQUE INDEX uq_unified_capabilities_reference_archimate_id
    ON unified_capabilities (archimate_id)
    WHERE organization_id IS NULL AND archimate_id IS NOT NULL;
CREATE UNIQUE INDEX uq_unified_capabilities_tenant_archimate_id
    ON unified_capabilities (organization_id, archimate_id)
    WHERE organization_id IS NOT NULL AND archimate_id IS NOT NULL;

ALTER TABLE unified_capabilities
    DROP CONSTRAINT IF EXISTS unified_capabilities_code_key,
    DROP CONSTRAINT IF EXISTS unified_capabilities_archimate_id_key;
DROP INDEX IF EXISTS ix_unified_capabilities_code;
DROP INDEX IF EXISTS ix_unified_capabilities_archimate_id;

ALTER TABLE unified_capabilities
    DROP CONSTRAINT IF EXISTS ck_unified_capabilities_scope_owner;
ALTER TABLE unified_capabilities
    ADD CONSTRAINT ck_unified_capabilities_scope_owner CHECK (
        scope IS NOT NULL
        AND (
            (scope = 'reference' AND organization_id IS NULL)
            OR (scope = 'tenant' AND organization_id IS NOT NULL)
        )
    );

DO $constraints$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'unified_capabilities'::regclass
          AND conname = 'fk_unified_capabilities_organization'
    ) THEN
        ALTER TABLE unified_capabilities
            ADD CONSTRAINT fk_unified_capabilities_organization
            FOREIGN KEY (organization_id) REFERENCES organizations(id)
            ON DELETE CASCADE NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'unified_capabilities'::regclass
          AND conname = 'fk_unified_capabilities_source_org'
    ) THEN
        ALTER TABLE unified_capabilities
            ADD CONSTRAINT fk_unified_capabilities_source_org
            FOREIGN KEY (source_org_id) REFERENCES organizations(id)
            ON DELETE SET NULL NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'unified_capabilities'::regclass
          AND conname = 'fk_unified_capabilities_reference'
    ) THEN
        ALTER TABLE unified_capabilities
            ADD CONSTRAINT fk_unified_capabilities_reference
            FOREIGN KEY (reference_capability_id) REFERENCES unified_capabilities(id)
            ON DELETE SET NULL NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'unified_capabilities'::regclass
          AND conname = 'fk_unified_capabilities_retired_into'
    ) THEN
        ALTER TABLE unified_capabilities
            ADD CONSTRAINT fk_unified_capabilities_retired_into
            FOREIGN KEY (retired_into_id) REFERENCES unified_capabilities(id)
            ON DELETE SET NULL NOT VALID;
    END IF;
END
$constraints$;

ALTER TABLE unified_capabilities VALIDATE CONSTRAINT fk_unified_capabilities_organization;
ALTER TABLE unified_capabilities VALIDATE CONSTRAINT fk_unified_capabilities_source_org;
ALTER TABLE unified_capabilities VALIDATE CONSTRAINT fk_unified_capabilities_reference;
ALTER TABLE unified_capabilities VALIDATE CONSTRAINT fk_unified_capabilities_retired_into;

CREATE OR REPLACE FUNCTION enforce_unified_capability_write_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $write_guard$
DECLARE
    actor_org_text text := current_setting('archie.organization_id', true);
    actor_org integer;
BEGIN
    IF TG_OP <> 'DELETE' AND (
        NEW.scope IS NULL
        OR NEW.scope NOT IN ('reference', 'tenant')
        OR (NEW.scope = 'reference' AND NEW.organization_id IS NOT NULL)
        OR (NEW.scope = 'tenant' AND NEW.organization_id IS NULL)
    ) THEN
        RAISE EXCEPTION 'capability scope and ownership are invalid';
    END IF;
    IF TG_OP <> 'DELETE' AND NEW.reference_capability_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM unified_capabilities AS reference
        WHERE reference.id = NEW.reference_capability_id
          AND reference.scope = 'reference'
          AND reference.organization_id IS NULL
    ) THEN
        RAISE EXCEPTION 'reference_capability_id must identify a reference capability';
    END IF;
    IF actor_org_text IS NOT NULL AND actor_org_text <> '' THEN
        actor_org := actor_org_text::integer;
        IF TG_OP = 'DELETE' THEN
            IF OLD.scope = 'reference' OR OLD.organization_id IS NULL THEN
                RAISE EXCEPTION 'reference capabilities are read-only for tenant sessions';
            END IF;
            IF OLD.organization_id IS DISTINCT FROM actor_org THEN
                RAISE EXCEPTION 'capability delete crosses tenant boundary';
            END IF;
            RETURN OLD;
        END IF;
        IF TG_OP = 'UPDATE' AND (
            OLD.scope = 'reference' OR OLD.organization_id IS NULL
        ) THEN
            RAISE EXCEPTION 'reference capabilities are read-only for tenant sessions';
        END IF;
        IF TG_OP = 'UPDATE' AND OLD.organization_id IS DISTINCT FROM actor_org THEN
            RAISE EXCEPTION 'capability update crosses tenant boundary';
        END IF;
        IF NEW.organization_id IS DISTINCT FROM actor_org THEN
            RAISE EXCEPTION 'capability write crosses tenant boundary';
        END IF;
    END IF;
    RETURN NEW;
END
$write_guard$;

DROP TRIGGER IF EXISTS trg_unified_capability_write_scope ON unified_capabilities;
CREATE TRIGGER trg_unified_capability_write_scope
    BEFORE INSERT OR UPDATE OR DELETE ON unified_capabilities
    FOR EACH ROW EXECUTE FUNCTION enforce_unified_capability_write_scope();

DO $verify$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE contype = 'f'
          AND NOT convalidated
          AND (
              conrelid = 'unified_capabilities'::regclass
              OR confrelid = 'unified_capabilities'::regclass
          )
    ) THEN
        RAISE EXCEPTION 'capability tenancy cutover left an unvalidated foreign key';
    END IF;
END
$verify$;

COMMIT;
