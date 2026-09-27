# migration-exempt: spec_data column added via ALTER TABLE (scripts/migrate_blueprint_columns.sql)
"""Compatibility shim. The junction model lives in solution_models.py.

This module used to declare a SECOND SolutionArchiMateElement class mapped to
the same `solution_archimate_elements` table as solution_models.py. The two
disagreed about one column, and that disagreement reached production:

    element_id is POLYMORPHIC -- element_table is its discriminator, and rows
    legitimately reference courses_of_action, goals, drivers, stakeholders and
    the other layer tables. solution_models.py declared it correctly, with no
    foreign key. This module declared a hard FK to archimate_elements.id, and
    because both classes share one Table via extend_existing, that constraint
    reached the physical table.

Any write whose element_id did not also exist in archimate_elements then raised
ForeignKeyViolation, aborting the transaction and 500-ing the solution creation
wizard. Production carried 83 such rows, 5 of them referencing goals, drivers,
stakeholders and constraints -- surviving only because the ids happened to
collide. The constraint is dropped by
scripts/migrate_drop_polymorphic_element_fk.sql.

Resolved 31 Aug 2026 by making this a re-export. The class in solution_models.py
is a strict superset -- it declares every column this one did, plus the
LAYER_TABLES/LAYER_COLORS maps and the `solution` and `created_by`
relationships -- so nothing is lost. 49 modules import this name; they all keep
working and now all get the same class.
"""

from app.models.solution_models import SolutionArchiMateElement  # noqa: F401

__all__ = ["SolutionArchiMateElement"]
