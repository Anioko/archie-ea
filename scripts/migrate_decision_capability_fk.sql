-- Repoint decision_capability_links at the capability store that has data.
--
-- Measured in production, 31 Aug 2026:
--   business_capability      461 rows
--   capabilities               0 rows
--   decision_capability_links  0 rows
--
-- The link table's foreign key pointed at `capabilities`, so the feature that
-- links an architecture decision to the capabilities it affects referenced a
-- store nothing populates. The endpoint's existence guard was consistent with
-- that FK and therefore returned 404 for every capability a user actually has.
--
-- Safe because the link table is empty: no rows are migrated, nothing is
-- deleted. Idempotent, and safe to run where the constraint was never created.
--
-- Reversal, should this prove wrong:
--   ALTER TABLE decision_capability_links
--     DROP CONSTRAINT IF EXISTS decision_capability_links_capability_id_fkey;
--   ALTER TABLE decision_capability_links
--     ADD CONSTRAINT decision_capability_links_capability_id_fkey
--     FOREIGN KEY (capability_id) REFERENCES capabilities(id) ON DELETE CASCADE;

-- Wrapped: the DROP and the ADD must land together. Run as two autocommitted
-- statements, a failure of the ADD (a stray row, a missing table) would leave
-- the link table with NO foreign key at all -- strictly worse than the wrong
-- one it started with, and silent until something wrote an orphan.
BEGIN;

ALTER TABLE decision_capability_links
    DROP CONSTRAINT IF EXISTS decision_capability_links_capability_id_fkey;

ALTER TABLE decision_capability_links
    ADD CONSTRAINT decision_capability_links_capability_id_fkey
    FOREIGN KEY (capability_id) REFERENCES business_capability(id) ON DELETE CASCADE;

COMMIT;
