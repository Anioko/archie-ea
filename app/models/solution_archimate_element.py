# migration-exempt: spec_data column added via ALTER TABLE (scripts/migrate_blueprint_columns.sql)
"""
Junction table: solution_archimate_elements
Many-to-many: Solution <-> ArchiMateElement with element_role annotation.
SA-001: SolutionArchiMateService keystone.
"""

from datetime import datetime

from app import db


class SolutionArchiMateElement(db.Model):  # migration-exempt
    __tablename__ = "solution_archimate_elements"

    id = db.Column(db.Integer, primary_key=True)
    # NOTE: no index=True here. This class shares __tablename__
    # "solution_archimate_elements" (extend_existing) with the polymorphic
    # definition in solution_models.py, which already indexes solution_id.
    # Declaring index=True in BOTH registers the implicit index
    # ix_solution_archimate_elements_solution_id twice, so a fresh create_all()
    # (e.g. flask init-db on a new DB, or CI) fails with DuplicateTable.
    solution_id = db.Column(
        db.Integer,
        db.ForeignKey("solutions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # NO ForeignKey, deliberately. This column is POLYMORPHIC: element_table is
    # its discriminator, and the sibling mapping in solution_models.py has always
    # declared it without one ("FK to respective layer table"). This class used to
    # point it at archimate_elements.id, which put a real constraint on the
    # physical table and made every non-ArchiMate write a coin flip -- it survived
    # only when the target id happened to exist in archimate_elements too.
    #
    # Measured 31 Aug 2026: 4 of 4 rows in the table referenced courses_of_action,
    # so the constraint was violated in intent by 100% of live data. The wizard's
    # "Buy a managed platform" course-of-action path 500s with
    # ForeignKeyViolation whenever the ids do not coincide, which also made
    # tests/journeys/test_journey_solution_architect.py pass or fail depending on
    # what unrelated tests had created first.
    #
    # Dropped from existing databases by
    # scripts/migrate_drop_polymorphic_element_fk.sql. Reversible: the constraint
    # definition is recorded in that script's header.
    element_id = db.Column(
        db.Integer,
        nullable=False,
        index=True,
    )
    layer_type = db.Column(db.String(64), nullable=True)
    element_table = db.Column(db.String(128), nullable=True)
    element_name = db.Column(db.String(256), nullable=True)
    relationship_type = db.Column(db.String(64), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_new_element = db.Column(db.Boolean, nullable=True, default=False)
    # e.g. 'primary', 'supporting', 'impacted', 'ai_derived'
    element_role = db.Column(db.String(64), nullable=False, default="primary")
    # Structured spec data: fields, api_contract, business_rules, integrations, deployment
    spec_data = db.Column(db.JSON, nullable=True, default=None)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "solution_id", "element_id", name="uq_sol_archimate_elem_direct"
        ),
        {"extend_existing": True},
    )
