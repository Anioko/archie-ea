-- Drop the foreign key that sat on a polymorphic column.
--
-- solution_archimate_elements.element_id is polymorphic: element_table is its
-- discriminator, and rows legitimately reference courses_of_action,
-- stakeholders, business_actors and the other layer tables. One of the two model
-- classes mapping this table (app/models/solution_archimate_element.py) declared
-- a hard FK to archimate_elements.id anyway, and because both classes use
-- extend_existing the constraint reached the physical table.
--
-- Effect: any write whose element_id did not also exist in archimate_elements
-- raised ForeignKeyViolation, aborting the transaction and 500-ing the solution
-- creation wizard. Measured 31 Aug 2026: 4 of 4 rows referenced
-- courses_of_action, so 100% of live data violated the constraint's intent and
-- survived only on id collision.
--
-- Reversal, should this ever prove wrong:
--   ALTER TABLE solution_archimate_elements
--     ADD CONSTRAINT solution_archimate_elements_element_id_fkey
--     FOREIGN KEY (element_id) REFERENCES archimate_elements(id) ON DELETE CASCADE;
--
-- No data is modified. Idempotent: safe to run repeatedly and on a database
-- where the constraint was never created.

ALTER TABLE solution_archimate_elements
    DROP CONSTRAINT IF EXISTS solution_archimate_elements_element_id_fkey;
