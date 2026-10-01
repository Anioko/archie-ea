"""Add the review-board/AI-authoring columns to architecture_decisions, and
repoint solution_adr_links.adr_id at it instead of architecture_decision_records.

architecture_decisions is now the only writer for every decision creation
path (lead ruling): the AI chat, workbench and
solution-options-advisor paths that used to insert into
architecture_decision_records first and pair afterwards now write the
canonical row directly. Four fields those paths set had no column there
yet: affected_systems, assumptions, estimated_effort, business_value, and a
free-text decided_by_label for an AI actor that is not a users.id row.

solution_adr_links.adr_id's foreign key is repointed from
architecture_decision_records.id to architecture_decisions.id for the same
reason: the workbench paths that create a link alongside the decision need
it to point at the row that now actually gets created. This feature has
not shipped (this whole consolidation is still mid-review), so there is no
production data under the old relationship to migrate.

Revision ID: 20261001_canonical_decision_columns
Revises: 20260926_widen_element_name
Create Date: 2026-10-01
"""
import sqlalchemy as sa
from alembic import op

revision = "20261001_canonical_decision_columns"
down_revision = "20260926_widen_element_name"
branch_labels = None
depends_on = None


def _fk_name(bind, table, column, target_table):
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table):
        if column in fk.get("constrained_columns", []) and fk.get("referred_table") == target_table:
            return fk.get("name")
    return None


def upgrade():
    bind = op.get_bind()

    op.add_column("architecture_decisions", sa.Column("affected_systems", sa.JSON(), nullable=True))
    op.add_column("architecture_decisions", sa.Column("assumptions", sa.Text(), nullable=True))
    op.add_column("architecture_decisions", sa.Column("estimated_effort", sa.String(50), nullable=True))
    op.add_column("architecture_decisions", sa.Column("business_value", sa.String(50), nullable=True))
    op.add_column("architecture_decisions", sa.Column("decided_by_label", sa.Text(), nullable=True))

    fk_name = _fk_name(bind, "solution_adr_links", "adr_id", "architecture_decision_records")
    if fk_name:
        op.drop_constraint(fk_name, "solution_adr_links", type_="foreignkey")
    op.create_foreign_key(
        "solution_adr_links_adr_id_fkey",
        "solution_adr_links", "architecture_decisions",
        ["adr_id"], ["id"],
    )


def downgrade():
    bind = op.get_bind()

    fk_name = _fk_name(bind, "solution_adr_links", "adr_id", "architecture_decisions")
    if fk_name:
        op.drop_constraint(fk_name, "solution_adr_links", type_="foreignkey")
    op.create_foreign_key(
        "solution_adr_links_adr_id_fkey",
        "solution_adr_links", "architecture_decision_records",
        ["adr_id"], ["id"],
    )

    op.drop_column("architecture_decisions", "decided_by_label")
    op.drop_column("architecture_decisions", "business_value")
    op.drop_column("architecture_decisions", "estimated_effort")
    op.drop_column("architecture_decisions", "assumptions")
    op.drop_column("architecture_decisions", "affected_systems")
