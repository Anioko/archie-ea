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
    solution_id = db.Column(
        db.Integer,
        db.ForeignKey("solutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    element_id = db.Column(
        db.Integer,
        db.ForeignKey("archimate_elements.id", ondelete="CASCADE"),
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
