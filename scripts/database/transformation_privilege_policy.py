"""Single source of truth for Transformation Room runtime privileges.

The database-role bootstrap and the schema guard installer both consume this
module.  Keeping the policy dependency-free lets the bootstrap run before the
Flask application or its model metadata can be imported.
"""

from __future__ import annotations


RUNTIME_NO_ACCESS_TABLES = frozenset({"archie_command_capability_keys"})

# Table-level privileges on guard-owned relations.  Column-level UPDATE grants
# are listed separately, so no entry here implies DELETE, TRUNCATE, REFERENCES,
# TRIGGER, or an unrestricted UPDATE.
PROTECTED_RUNTIME_TABLE_PRIVILEGES = {
    "operation_results": ("SELECT", "INSERT"),
    "transformation_outbox_events": ("SELECT", "INSERT"),
    "candidate_signals": ("SELECT", "INSERT"),
    "evidence_records": ("SELECT", "INSERT"),
    "evidence_head_events": ("SELECT",),
    "transformation_option_versions": ("SELECT", "INSERT"),
    "decision_brief_versions": ("SELECT",),
    "decision_brief_option_citations": ("SELECT",),
    "decision_brief_evidence_citations": ("SELECT",),
    "decision_events": ("SELECT", "INSERT"),
    "command_idempotency_records": ("SELECT",),
    "evidence_claim_heads": ("SELECT", "INSERT"),
    "decision_briefs": ("SELECT",),
}

PROTECTED_RUNTIME_UPDATE_COLUMNS = {
    "transformation_outbox_events": (
        "delivery_attempts",
        "published_at",
    ),
    "command_idempotency_records": (
        "status",
        "lease_generation",
        "claim_token",
        "claimant_request_id",
        "lease_expires_at",
        "operation_result_id",
        "attempt_count",
        "last_error_class",
        "updated_at",
        "completed_at",
    ),
}

# Signatures contain only identity-argument types so psycopg2 can render an
# exact GRANT regardless of the parameter names stored in pg_proc.
RUNTIME_EXECUTE_FUNCTIONS = (
    (
        "archie_advance_evidence_head",
        "bigint, bigint, integer, bigint, bigint, integer, text",
    ),
    (
        "archie_freeze_decision_brief_version",
        "bigint, bigint, bigint, integer, text, text, text, integer, text, jsonb, text",
    ),
    ("archie_claim_transformation_command", "text, text"),
    ("archie_create_decision_brief", "text, text, text"),
)


__all__ = [
    "PROTECTED_RUNTIME_TABLE_PRIVILEGES",
    "PROTECTED_RUNTIME_UPDATE_COLUMNS",
    "RUNTIME_EXECUTE_FUNCTIONS",
    "RUNTIME_NO_ACCESS_TABLES",
]
