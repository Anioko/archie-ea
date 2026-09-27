"""A polymorphic column must not carry a foreign key to one of its targets.

solution_archimate_elements.element_id references whichever layer table
element_table names -- courses_of_action, stakeholders, business_actors and the
rest. One of the two model classes mapping this table declared a hard FK to
archimate_elements.id anyway, and because both use extend_existing the
constraint reached the physical table.

The consequence was a 500 on the solution-creation wizard: any element_id not
also present in archimate_elements raised ForeignKeyViolation, which aborted the
transaction. Measured 31 Aug 2026, 4 of 4 rows in the table referenced
courses_of_action -- so every row violated the constraint's intent and survived
only because the ids happened to collide.

That collision is also why this was invisible: the four solution-architect
journeys passed or failed depending on whether unrelated tests had created
archimate_elements rows first. A defect that depends on test ordering is not
caught by "the suite is green".
"""

import pytest

pytestmark = pytest.mark.usefixtures("app")


def test_element_id_carries_no_foreign_key_in_the_orm():
    """Both mappings must leave element_id free of a FK."""
    from app.models.solution_archimate_element import SolutionArchiMateElement

    column = SolutionArchiMateElement.__table__.c.element_id
    assert not list(column.foreign_keys), (
        "element_id declares %r. It is polymorphic -- element_table is the "
        "discriminator -- so a foreign key to any single table makes every "
        "other layer's write fail."
        % [str(fk.target_fullname) for fk in column.foreign_keys]
    )


def test_element_id_carries_no_foreign_key_in_the_database(app):
    """The ORM and the live table must agree.

    reconcile-schema is ADD-only, so removing the FK from the model does not
    remove it from an existing database. Dropping it is
    scripts/migrate_drop_polymorphic_element_fk.sql, and this asserts the
    deployed database actually had it applied.
    """
    from app import db

    with app.app_context():
        rows = db.session.execute(
            db.text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'solution_archimate_elements'::regclass "
                "AND contype = 'f' AND conname LIKE '%%element_id%%'"
            )
        ).fetchall()

    assert rows == [], (
        "the database still constrains element_id: %s -- run "
        "scripts/migrate_drop_polymorphic_element_fk.sql" % [r[0] for r in rows]
    )
