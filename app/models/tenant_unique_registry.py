"""Which unique constraints on tenant-scoped tables must be scoped per organisation.

A column declared ``unique=True`` on a ``TenantMixin`` model is unique across
*every* organisation. For a value the tenant authors — a capability code, a
vendor name, a data-domain code, an ADR number — that makes the value a
first-come-first-served resource: the second organisation to use "SAP", "CUST"
or "AD-001" is refused, and the error it sees says only that the value is taken.

This registry is the audit's output and the fixer's input. It was produced by
walking the SQLAlchemy mapper registry (not by grepping for columns named
"code"), which found 60 cross-tenant unique constraints over 46 tables, and then
judging each one against its declaration.

Three verdicts:

``SCOPE_PER_TENANT``
    The value is authored or imported by the tenant, so two organisations can
    legitimately hold the same one. These are defects.

``GLOBAL_BY_DESIGN``
    Global uniqueness is correct. Each entry records why, because "it looked
    fine" is not a reason anybody can check later.

Composite constraints made only of foreign keys to tenant-scoped rows are
neither: they cannot collide across organisations, because the rows they
reference cannot. The scanner skips them, and the gate does too.
"""

from __future__ import annotations

# (table, column) pairs that must become UNIQUE (organization_id, column).
SCOPE_PER_TENANT = [
    # Sequential references a tenant issues for itself. Every organisation
    # starts at 001.
    ("adm_phase_approvals", "approval_number"),          # ADM-2026-001
    ("architecture_change_requests", "acr_reference"),   # ACR-2026-001
    ("architecture_decisions", "decision_id"),           # AD-001
    ("architecture_review_boards", "board_number"),      # ARB-2026-001
    ("capability_governance_decision", "adr_number"),
    ("capability_gap_analysis", "analysis_code"),        # GA-2024-Q1

    # Codes a tenant brings with it, from its own model or a spreadsheet.
    ("business_capability", "code"),                     # CAP-001, BC.1.2, APQC ids
    ("application_components", "application_code"),
    ("application_components", "external_id"),
    ("application_consolidation_recommendations", "recommendation_code"),
    ("business_processes", "process_code"),              # P2P-001, O2C-001
    # Declared correctly from the start — UNIQUE (organization_id, code), never
    # unique=True. Listed anyway because it is a *new* column: on an existing
    # database reconcile-schema adds the column and never an index, so
    # create_all's constraint is missing there. The boot chain's
    # scope-unique-to-tenant creates it (the drop steps are no-ops, since there
    # is no legacy global index to drop). Without this line the constraint
    # exists only on databases created after the column.
    ("business_objects", "code"),                        # CUST, ORD, INV
    ("courses_of_action", "code"),
    ("data_domains", "code"),                            # CUST, PROD, FIN, OPS
    ("enterprise_initiatives", "code"),
    ("projects", "code"),

    # Names every organisation independently wants to use. These are the ones
    # where a collision is not hypothetical: two customers both run SAP, both
    # have a "Customer" data domain, and both want a tag called "Core".
    ("archimate_viewpoints", "name"),
    ("capability_tags", "name"),
    ("data_domains", "name"),
    ("governance_gates", "gate_name"),
    ("vendor_stack_templates", "vendor_name"),
    ("vendor_taxonomy", "canonical_name"),

    # Identifiers owned by a system outside Archie, one per tenant.
    ("kanban_cards", "jira_issue_key"),                  # ARCH-142, per Jira site
    ("vendor_contracts", "contract_number"),
    ("technology_devices", "serial_number"),
    ("solution_problem_definitions", "session_id"),
]

# Deliberately left globally unique, with the reason.
GLOBAL_BY_DESIGN = {
    ("users", "email"):
        "login identity — one account per address across the whole platform",
    ("sso_configs", "organization_id"):
        "one SSO configuration per organisation; the unique IS the tenancy rule",
    ("subscriptions", "organization_id"):
        "one subscription per organisation; the unique IS the tenancy rule",
    ("application_rationalization_scores", "application_component_id"):
        "one score per application, and the application is already tenant-scoped",
    # archimate_id is assigned by an after-insert listener as
    # f"archimate-{primary_key}", so it is derived from a global sequence and
    # cannot collide. Listed per table because each is a separate declaration.
    ("archimate_contracts", "archimate_id"): "generated from the primary key",
    ("archimate_representations", "archimate_id"): "generated from the primary key",
    ("business_capability", "archimate_id"): "generated from the primary key",
    ("business_collaborations", "archimate_id"): "generated from the primary key",
    ("business_interfaces", "archimate_id"): "generated from the primary key",
    ("capabilities", "archimate_id"): "generated from the primary key",
    ("technology_collaborations_full", "archimate_id"): "generated from the primary key",
    ("technology_events", "archimate_id"): "generated from the primary key",
    ("technology_functions", "archimate_id"): "generated from the primary key",
    ("technology_interactions", "archimate_id"): "generated from the primary key",
    ("technology_processes", "archimate_id"): "generated from the primary key",
    # enterprise_raci_assignments (stakeholder_type, stakeholder_id, capability_id).
    # Surfaced once the gate stopped accepting any foreign key and started
    # requiring one that points at a tenant-scoped table: capability_id
    # references unified_capabilities, which is deliberately global shared
    # reference data (see the tenancy notes in CLAUDE.md). Both id columns are
    # primary keys drawn from global sequences, so two organisations cannot
    # produce the same triple — the separation comes from the ids themselves
    # rather than from the constraint.
    ("enterprise_raci_assignments", "stakeholder_type"):
        "part of a triple keyed on globally-unique primary keys; see below",
    ("enterprise_raci_assignments", "stakeholder_id"):
        "a primary key from a global sequence — two organisations cannot share one",
    ("enterprise_raci_assignments", "capability_id"):
        "a unified_capabilities primary key, global by design and globally unique",
}


#: PostgreSQL truncates identifiers at 63 bytes. SQLAlchemy silently truncates
#: the names it generates itself, and raises IdentifierError for one you supply
#: — at DDL-compile time, so the failure is `create_all()` on a database where
#: the table does not yet exist. That is `flask init-db` on a fresh install, and
#: therefore the first command in the compose boot chain, which then never
#: reaches gunicorn. Every existing database passes, because create_all emits no
#: DDL for a table it already has, which is exactly why it survived CI and a
#: local run.
MAX_IDENTIFIER = 63


def tenant_unique_index_name(table: str, column: str) -> str:
    """The name of the per-tenant unique index for one column, always legal.

    Deterministic, so the model declaration and the upgrade command agree: if
    they disagreed, the command would create a second index under a different
    name and never recognise the one already there.

    When the natural name is too long it is shortened by dropping characters
    from the middle of the table name rather than the ends, because the prefix
    and the column are what make it readable.
    """
    name = f"uq_{table}_org_{column}"
    if len(name) <= MAX_IDENTIFIER:
        return name

    fixed = len(f"uq__org_{column}")
    budget = MAX_IDENTIFIER - fixed
    if budget < 8:
        # Pathological column name: keep the tail, which is the distinguishing
        # part, and accept an unreadable prefix over an illegal identifier.
        return name[-MAX_IDENTIFIER:]
    head = budget // 2
    tail = budget - head
    return f"uq_{table[:head]}{table[-tail:]}_org_{column}"


def index_names(table: str, column: str) -> dict:
    """The index names involved in scoping one column, by role."""
    return {
        "tenant": tenant_unique_index_name(table, column),
        "legacy_index": f"ix_{table}_{column}",
        "legacy_constraint": f"{table}_{column}_key",
        "lookup": f"ix_{table}_{column}",
    }
