"""PostgreSQL append-only and fenced-transition guards for command records."""

from __future__ import annotations

from sqlalchemy import event

from app.models.transformation_execution import (
    CommandIdempotencyRecord,
    OperationOutboxEvent,
    OperationResult,
)
from app.models.transformation_evidence import (
    CandidateSignal,
    EvidenceClaimHead,
    EvidenceHeadEvent,
    EvidenceRecord,
)


TRANSFORMATION_RUNTIME_ROLE = "archie_runtime"


_IMMUTABILITY_FUNCTION_SQL = r"""
CREATE OR REPLACE FUNCTION public.archie_reject_transformation_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF TG_TABLE_NAME = 'transformation_outbox_events' AND TG_OP = 'UPDATE' THEN
        IF NEW.id = OLD.id
           AND NEW.organization_id = OLD.organization_id
           AND NEW.operation_result_id = OLD.operation_result_id
           AND NEW.event_id = OLD.event_id
           AND NEW.ordinal = OLD.ordinal
           AND NEW.event_type = OLD.event_type
           AND NEW.payload_json::jsonb = OLD.payload_json::jsonb
           AND NEW.created_at = OLD.created_at
           AND NEW.delivery_attempts >= OLD.delivery_attempts
           AND (
               NEW.published_at IS NOT DISTINCT FROM OLD.published_at
               OR (
                   NEW.published_at IS NOT NULL
                   AND (OLD.published_at IS NULL OR NEW.published_at >= OLD.published_at)
               )
           ) THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'transformation immutable rows are append-only'
        USING ERRCODE = '55000';
END;
$$
"""


_RECEIPT_FUNCTION_SQL = r"""
CREATE OR REPLACE FUNCTION public.archie_guard_transformation_receipt()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    now_at_database timestamptz := clock_timestamp();
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'command receipt identity and terminal result are immutable'
            USING ERRCODE = '55000';
    END IF;

    IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
       OR NEW.actor_id IS DISTINCT FROM OLD.actor_id
       OR NEW.operation IS DISTINCT FROM OLD.operation
       OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.request_digest IS DISTINCT FROM OLD.request_digest
       OR NEW.natural_key IS DISTINCT FROM OLD.natural_key
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'command receipt identity, digest, and natural key are immutable'
            USING ERRCODE = '55000';
    END IF;

    IF OLD.operation_result_id IS NOT NULL
       AND NEW.operation_result_id IS DISTINCT FROM OLD.operation_result_id THEN
        RAISE EXCEPTION 'command receipt terminal result is immutable'
            USING ERRCODE = '55000';
    END IF;

    -- Heartbeat: same fence and state, expiry moves strictly forward.
    IF OLD.status = 'in_progress'
       AND NEW.status = 'in_progress'
       AND NEW.lease_generation = OLD.lease_generation
       AND NEW.claim_token = OLD.claim_token
       AND NEW.claimant_request_id = OLD.claimant_request_id
       AND NEW.operation_result_id IS NOT DISTINCT FROM OLD.operation_result_id
       AND NEW.attempt_count = OLD.attempt_count
       AND NEW.last_error_class IS NOT DISTINCT FROM OLD.last_error_class
       AND NEW.completed_at IS NOT DISTINCT FROM OLD.completed_at
       AND NEW.lease_expires_at > OLD.lease_expires_at
       AND NEW.lease_expires_at > now_at_database THEN
        RETURN NEW;
    END IF;

    -- Reclaim: only an expired/retryable non-terminal lease, exactly next fence.
    IF OLD.status IN ('in_progress', 'retryable_failure')
       AND (OLD.status = 'retryable_failure'
            OR OLD.lease_expires_at IS NULL
            OR OLD.lease_expires_at <= now_at_database)
       AND NEW.status = 'in_progress'
       AND NEW.lease_generation = OLD.lease_generation + 1
       AND NEW.claim_token IS NOT NULL
       AND length(NEW.claim_token) >= 32
       AND NEW.claim_token IS DISTINCT FROM OLD.claim_token
       AND NEW.lease_expires_at > now_at_database
       AND NEW.operation_result_id IS NULL
       AND NEW.attempt_count = OLD.attempt_count + 1
       AND NEW.completed_at IS NULL THEN
        RETURN NEW;
    END IF;

    -- A known pre-commit transient is immediately reclaimable by the same digest.
    IF OLD.status = 'in_progress'
       AND NEW.status = 'retryable_failure'
       AND NEW.lease_generation = OLD.lease_generation
       AND NEW.claim_token = OLD.claim_token
       AND NEW.claimant_request_id = OLD.claimant_request_id
       AND NEW.operation_result_id IS NULL
       AND NEW.attempt_count = OLD.attempt_count
       AND NEW.last_error_class IS NOT NULL
       AND NEW.lease_expires_at <= now_at_database
       AND NEW.completed_at IS NULL THEN
        RETURN NEW;
    END IF;

    -- Validation/authorization failures are terminal but never business success.
    IF OLD.status = 'in_progress'
       AND NEW.status = 'failed_non_retryable'
       AND NEW.lease_generation = OLD.lease_generation
       AND NEW.claim_token = OLD.claim_token
       AND NEW.claimant_request_id = OLD.claimant_request_id
       AND NEW.operation_result_id IS NULL
       AND NEW.attempt_count = OLD.attempt_count
       AND NEW.last_error_class IS NOT NULL
       AND NEW.lease_expires_at IS NULL
       AND NEW.completed_at IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Atomic finalise or result-led repair. The immutable result is the proof.
    IF OLD.status IN ('in_progress', 'retryable_failure', 'succeeded')
       AND OLD.operation_result_id IS NULL
       AND NEW.status = 'succeeded'
       AND NEW.lease_generation = OLD.lease_generation
       AND NEW.claim_token = OLD.claim_token
       AND NEW.claimant_request_id = OLD.claimant_request_id
       AND NEW.operation_result_id IS NOT NULL
       AND NEW.attempt_count = OLD.attempt_count
       AND NEW.lease_expires_at IS NULL
       AND NEW.completed_at IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM public.operation_results result
           WHERE result.id = NEW.operation_result_id
             AND result.organization_id = NEW.organization_id
             AND result.actor_id = NEW.actor_id
             AND result.operation = NEW.operation
             AND result.natural_key = NEW.natural_key
             AND result.request_digest = NEW.request_digest
       ) THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'invalid command receipt transition or fence'
        USING ERRCODE = '55000';
END;
$$
"""


_EVIDENCE_HEAD_GUARD_SQL = r"""
CREATE OR REPLACE FUNCTION public.archie_guard_evidence_head()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.current_record_id IS NOT NULL OR NEW.revision <> 0 THEN
            RAISE EXCEPTION 'evidence head must be created empty at revision zero'
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        IF OLD.current_record_id IS NOT NULL OR EXISTS (
            SELECT 1 FROM public.evidence_head_events event
            WHERE event.head_id = OLD.id
        ) THEN
            RAISE EXCEPTION 'evidence head with history cannot be deleted'
                USING ERRCODE = '55000';
        END IF;
        RETURN OLD;
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
       OR NEW.subject_type IS DISTINCT FROM OLD.subject_type
       OR NEW.subject_id IS DISTINCT FROM OLD.subject_id
       OR NEW.claim_key IS DISTINCT FROM OLD.claim_key
       OR NEW.source_identity IS DISTINCT FROM OLD.source_identity
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'evidence head identity is immutable'
            USING ERRCODE = '55000';
    END IF;
    IF NEW.current_record_id IS NULL OR NEW.revision <> OLD.revision + 1 THEN
        RAISE EXCEPTION 'evidence head revision must advance exactly once'
            USING ERRCODE = '55000';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM public.evidence_records record
        WHERE record.id = NEW.current_record_id
          AND record.organization_id = NEW.organization_id
          AND record.subject_type = NEW.subject_type
          AND record.subject_id = NEW.subject_id
          AND record.claim_key = NEW.claim_key
          AND record.source_identity = NEW.source_identity
          AND record.supersedes_id IS NOT DISTINCT FROM OLD.current_record_id
    ) THEN
        RAISE EXCEPTION 'evidence head target is outside its chain or has wrong predecessor'
            USING ERRCODE = '55000';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM public.evidence_head_events event
        JOIN public.command_idempotency_records receipt
          ON receipt.id = event.command_receipt_id
         AND receipt.organization_id = event.organization_id
         AND receipt.actor_id = event.actor_id
        WHERE event.organization_id = NEW.organization_id
          AND event.head_id = NEW.id
          AND event.old_record_id IS NOT DISTINCT FROM OLD.current_record_id
          AND event.new_record_id = NEW.current_record_id
          AND event.revision = NEW.revision
          AND event.created_txid = txid_current()
          AND receipt.status = 'in_progress'
          AND receipt.lease_generation = event.command_generation
          AND receipt.lease_expires_at > clock_timestamp()
    ) THEN
        RAISE EXCEPTION 'evidence head move requires same-transaction fenced event'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$
"""


_EVIDENCE_EVENT_BINDING_SQL = r"""
CREATE OR REPLACE FUNCTION public.archie_guard_evidence_event_binding()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM public.evidence_claim_heads head
        JOIN public.evidence_records record
          ON record.id = NEW.new_record_id
         AND record.organization_id = NEW.organization_id
         AND record.subject_type = head.subject_type
         AND record.subject_id = head.subject_id
         AND record.claim_key = head.claim_key
         AND record.source_identity = head.source_identity
         AND record.supersedes_id IS NOT DISTINCT FROM NEW.old_record_id
        JOIN public.command_idempotency_records receipt
          ON receipt.id = NEW.command_receipt_id
         AND receipt.organization_id = NEW.organization_id
         AND receipt.actor_id = NEW.actor_id
         AND receipt.lease_generation = NEW.command_generation
         AND receipt.status IN ('in_progress', 'succeeded')
        WHERE head.id = NEW.head_id
          AND head.organization_id = NEW.organization_id
          AND head.current_record_id = NEW.new_record_id
          AND head.revision = NEW.revision
          AND NEW.created_txid = txid_current()
    ) THEN
        RAISE EXCEPTION 'evidence event is not bound to its head movement'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$
"""


_EVIDENCE_HEAD_ADVANCE_SQL = r"""
CREATE OR REPLACE FUNCTION public.archie_advance_evidence_head(
    p_head_id bigint,
    p_new_record_id bigint,
    p_expected_revision integer,
    p_actor_id bigint,
    p_receipt_id bigint,
    p_generation integer,
    p_claim_token text
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    head_organization_id bigint;
    head_subject_type text;
    head_subject_id bigint;
    head_claim_key text;
    head_source_identity text;
    head_current_record_id bigint;
    head_revision integer;
    receipt_actor_id bigint;
    receipt_organization_id bigint;
    receipt_operation text;
    receipt_natural_key text;
    receipt_status text;
    receipt_generation integer;
    receipt_token text;
    receipt_expiry timestamptz;
    record_candidate_id bigint;
    record_classification text;
    record_source_type text;
    record_source_record_id bigint;
    record_created_by_id bigint;
    record_value jsonb;
    record_citations jsonb;
    governing_record_id bigint;
    governing_source_identity text;
    governing_head_id bigint;
    governing_current_record_id bigint;
    attestation_candidate_id bigint;
    attestation_source_identity text;
    attestation_revision integer;
    expected_natural_key text;
    event_reason text;
    affected integer;
BEGIN
    -- Read immutable identity inputs first, then acquire every evidence-head
    -- lock in the same natural-key order.  The values are re-read after the
    -- locks, so neither this preliminary snapshot nor the caller's snapshot
    -- can authorize a stale movement.
    SELECT organization_id, subject_type, subject_id, claim_key,
           source_identity, current_record_id, revision
      INTO head_organization_id, head_subject_type, head_subject_id,
           head_claim_key, head_source_identity, head_current_record_id,
           head_revision
      FROM public.evidence_claim_heads
     WHERE id = p_head_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'evidence head not found' USING ERRCODE = '55000';
    END IF;
    SELECT record.candidate_id, record.classification, record.source_type,
           record.source_record_id, record.created_by_id,
           record.value_json::jsonb, record.cited_evidence_ids::jsonb
      INTO record_candidate_id, record_classification, record_source_type,
           record_source_record_id, record_created_by_id,
           record_value, record_citations
      FROM public.evidence_records record
        WHERE record.id = p_new_record_id
          AND record.organization_id = head_organization_id
          AND record.subject_type = head_subject_type
          AND record.subject_id = head_subject_id
          AND record.claim_key = head_claim_key
          AND record.source_identity = head_source_identity
          AND record.supersedes_id IS NOT DISTINCT FROM head_current_record_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'evidence record does not extend the evidence head'
            USING ERRCODE = '55000';
    END IF;

    SELECT actor_id, organization_id, operation, natural_key, status,
           lease_generation, claim_token, lease_expires_at
      INTO receipt_actor_id, receipt_organization_id, receipt_operation,
           receipt_natural_key, receipt_status, receipt_generation,
           receipt_token, receipt_expiry
      FROM public.command_idempotency_records
     WHERE id = p_receipt_id;
    IF receipt_operation = 'evidence.conflict.resolve'
       AND record_value ->> 'governing_evidence_id' ~ '^[1-9][0-9]*$' THEN
        governing_record_id := (record_value ->> 'governing_evidence_id')::bigint;
        SELECT governing.source_identity, governing_head.id
          INTO governing_source_identity, governing_head_id
          FROM public.evidence_records governing
          LEFT JOIN public.evidence_claim_heads governing_head
            ON governing_head.organization_id = governing.organization_id
           AND governing_head.subject_type = governing.subject_type
           AND governing_head.subject_id = governing.subject_id
           AND governing_head.claim_key = governing.claim_key
           AND governing_head.source_identity = governing.source_identity
         WHERE governing.id = governing_record_id
           AND governing.organization_id = head_organization_id
           AND governing.subject_type = head_subject_type
           AND governing.subject_id = head_subject_id
           AND governing.claim_key = head_claim_key;
    END IF;

    IF governing_head_id IS NULL THEN
        PERFORM head.id
          FROM public.evidence_claim_heads head
         WHERE head.id = p_head_id
         ORDER BY head.organization_id, head.subject_type, head.subject_id,
                  head.claim_key, head.source_identity, head.id
         FOR UPDATE;
    ELSE
        PERFORM head.id
          FROM public.evidence_claim_heads head
         WHERE head.id IN (p_head_id, governing_head_id)
         ORDER BY head.organization_id, head.subject_type, head.subject_id,
                  head.claim_key, head.source_identity, head.id
         FOR UPDATE;
    END IF;

    SELECT organization_id, subject_type, subject_id, claim_key,
           source_identity, current_record_id, revision
      INTO head_organization_id, head_subject_type, head_subject_id,
           head_claim_key, head_source_identity, head_current_record_id,
           head_revision
      FROM public.evidence_claim_heads
     WHERE id = p_head_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'evidence head not found' USING ERRCODE = '55000';
    END IF;
    IF head_revision <> p_expected_revision THEN
        RAISE EXCEPTION 'stale evidence head revision' USING ERRCODE = '40001';
    END IF;
    SELECT record.candidate_id, record.classification, record.source_type,
           record.source_record_id, record.created_by_id,
           record.value_json::jsonb, record.cited_evidence_ids::jsonb
      INTO record_candidate_id, record_classification, record_source_type,
           record_source_record_id, record_created_by_id,
           record_value, record_citations
      FROM public.evidence_records record
        WHERE record.id = p_new_record_id
          AND record.organization_id = head_organization_id
          AND record.subject_type = head_subject_type
          AND record.subject_id = head_subject_id
          AND record.claim_key = head_claim_key
          AND record.source_identity = head_source_identity
          AND record.supersedes_id IS NOT DISTINCT FROM head_current_record_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'evidence record does not extend the locked head'
            USING ERRCODE = '55000';
    END IF;

    SELECT actor_id, organization_id, operation, natural_key, status,
           lease_generation, claim_token, lease_expires_at
      INTO receipt_actor_id, receipt_organization_id, receipt_operation,
           receipt_natural_key, receipt_status, receipt_generation,
           receipt_token, receipt_expiry
      FROM public.command_idempotency_records
     WHERE id = p_receipt_id
     FOR UPDATE;
    IF NOT FOUND
       OR receipt_actor_id <> p_actor_id
       OR receipt_organization_id <> head_organization_id
       OR receipt_status <> 'in_progress'
       OR receipt_generation <> p_generation
       OR receipt_token IS DISTINCT FROM p_claim_token
       OR receipt_expiry IS NULL
       OR receipt_expiry <= clock_timestamp() THEN
        RAISE EXCEPTION 'evidence head command fence is stale or unrelated'
            USING ERRCODE = '55000';
    END IF;

    IF receipt_operation = 'evidence.conflict.resolve' THEN
        SELECT head.current_record_id
          INTO governing_current_record_id
          FROM public.evidence_claim_heads head
         WHERE head.id = governing_head_id
           AND head.organization_id = head_organization_id
           AND head.subject_type = head_subject_type
           AND head.subject_id = head_subject_id
           AND head.claim_key = head_claim_key
           AND head.source_identity = governing_source_identity;
        IF NOT FOUND
           OR governing_current_record_id IS DISTINCT FROM governing_record_id THEN
            RAISE EXCEPTION 'governing evidence is not current'
                USING ERRCODE = '55000';
        END IF;
    END IF;

    IF record_created_by_id <> p_actor_id THEN
        RAISE EXCEPTION 'evidence record actor does not match command actor'
            USING ERRCODE = '55000';
    END IF;

    IF receipt_operation = 'evidence.observe'
       AND record_classification = 'observed' THEN
        expected_natural_key := format(
            'evidence:%%s:%%s:%%s:%%s',
            record_candidate_id,
            head_claim_key,
            encode(sha256(convert_to(head_source_identity, 'UTF8')), 'hex'),
            head_revision + 1
        );
        event_reason := 'canonical source observation';
    ELSIF receipt_operation = 'evidence.attest'
       AND record_classification = 'attested'
       AND record_source_type = 'attestation'
       AND record_source_record_id = p_actor_id
       AND head_source_identity = format('attestation:user:%%s', p_actor_id) THEN
        expected_natural_key := format(
            'evidence:%%s:%%s:%%s:%%s',
            record_candidate_id,
            head_claim_key,
            encode(sha256(convert_to(head_source_identity, 'UTF8')), 'hex'),
            head_revision + 1
        );
        event_reason := 'human attestation submitted';
    ELSIF receipt_operation = 'evidence.attest'
       AND record_classification = 'conflict'
       AND record_source_type = 'governance_conflict'
       AND head_source_identity = format(
           'conflict:request:%%s', record_source_record_id
       )
       AND EXISTS (
           SELECT 1
           FROM public.evidence_requests request
           WHERE request.id = record_source_record_id
             AND request.organization_id = head_organization_id
             AND request.candidate_id = record_candidate_id
             AND request.subject_type = head_subject_type
             AND request.subject_id = head_subject_id
             AND request.claim_key = head_claim_key
             AND request.assigned_to_id = p_actor_id
       ) THEN
        SELECT attestation.candidate_id, attestation.source_identity, event.revision
          INTO attestation_candidate_id, attestation_source_identity,
               attestation_revision
          FROM jsonb_array_elements_text(
                   COALESCE(record_citations, '[]'::jsonb)
               ) AS citation(evidence_id)
          JOIN public.evidence_records attestation
            ON attestation.id = citation.evidence_id::bigint
          JOIN public.evidence_head_events event
            ON event.new_record_id = attestation.id
           AND event.organization_id = head_organization_id
           AND event.command_receipt_id = p_receipt_id
           AND event.command_generation = p_generation
           AND event.created_txid = txid_current()
         WHERE attestation.organization_id = head_organization_id
           AND attestation.subject_type = head_subject_type
           AND attestation.subject_id = head_subject_id
           AND attestation.claim_key = head_claim_key
           AND attestation.classification = 'attested'
           AND attestation.source_type = 'attestation'
           AND attestation.source_record_id = p_actor_id
           AND attestation.created_by_id = p_actor_id
         ORDER BY attestation.id DESC
         LIMIT 1;
        IF FOUND THEN
            IF attestation_candidate_id IS DISTINCT FROM record_candidate_id THEN
                RAISE EXCEPTION 'attestation candidate does not match conflict request candidate'
                    USING ERRCODE = '55000';
            END IF;
            expected_natural_key := format(
                'evidence:%%s:%%s:%%s:%%s',
                attestation_candidate_id,
                head_claim_key,
                encode(
                    sha256(convert_to(attestation_source_identity, 'UTF8')),
                    'hex'
                ),
                attestation_revision
            );
            event_reason := 'attestation disagrees with canonical observation';
        END IF;
    ELSIF receipt_operation = 'evidence.conflict.resolve'
       AND record_classification = 'derived'
       AND record_source_type = 'governance_resolution'
       AND head_source_identity = format(
           'resolution:conflict:%%s', record_source_record_id
       )
       AND record_value ->> 'conflict_evidence_id' = record_source_record_id::text
       AND EXISTS (
           SELECT 1
           FROM public.evidence_records conflict
           JOIN public.evidence_records governing
             ON governing.id = (record_value ->> 'governing_evidence_id')::bigint
            AND governing.organization_id = conflict.organization_id
            AND governing.subject_type = conflict.subject_type
            AND governing.subject_id = conflict.subject_id
            AND governing.claim_key = conflict.claim_key
           WHERE conflict.id = record_source_record_id
             AND conflict.organization_id = head_organization_id
             AND conflict.subject_type = head_subject_type
             AND conflict.subject_id = head_subject_id
             AND conflict.claim_key = head_claim_key
             AND conflict.classification = 'conflict'
             AND EXISTS (
                 SELECT 1
                 FROM jsonb_array_elements_text(
                     conflict.cited_evidence_ids::jsonb
                 ) AS cited(evidence_id)
                 WHERE cited.evidence_id =
                       record_value ->> 'governing_evidence_id'
             )
       ) THEN
        expected_natural_key := format(
            'evidence-conflict-resolution:%%s:%%s',
            record_source_record_id,
            record_value ->> 'governing_evidence_id'
        );
        event_reason := 'decision authority selected governing source';
    END IF;

    IF expected_natural_key IS NULL
       OR receipt_natural_key IS DISTINCT FROM expected_natural_key THEN
        RAISE EXCEPTION 'receipt operation or natural key does not authorize evidence head'
            USING ERRCODE = '55000';
    END IF;

    INSERT INTO public.evidence_head_events (
        organization_id, head_id, old_record_id, new_record_id, actor_id,
        command_receipt_id, command_generation, reason, revision, created_txid
    ) VALUES (
        head_organization_id, p_head_id, head_current_record_id, p_new_record_id,
        p_actor_id, p_receipt_id, p_generation, event_reason,
        head_revision + 1, txid_current()
    );

    UPDATE public.evidence_claim_heads
       SET current_record_id = p_new_record_id,
           revision = head_revision + 1,
           updated_at = clock_timestamp()
     WHERE id = p_head_id
       AND organization_id = head_organization_id
       AND revision = head_revision
       AND current_record_id IS NOT DISTINCT FROM head_current_record_id;
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 1 THEN
        RAISE EXCEPTION 'evidence head compare-and-swap failed'
            USING ERRCODE = '40001';
    END IF;
    RETURN head_revision + 1;
END;
$$
"""


_FUNCTION_SPECS = (
    (
        "archie_reject_transformation_mutation",
        _IMMUTABILITY_FUNCTION_SQL,
    ),
    ("archie_guard_transformation_receipt", _RECEIPT_FUNCTION_SQL),
    ("archie_guard_evidence_head", _EVIDENCE_HEAD_GUARD_SQL),
    ("archie_guard_evidence_event_binding", _EVIDENCE_EVENT_BINDING_SQL),
)

_TRIGGER_SPECS = (
    (
        "operation_results",
        "trg_transformation_result_immutable",
        "archie_reject_transformation_mutation",
    ),
    (
        "transformation_outbox_events",
        "trg_transformation_outbox_immutable",
        "archie_reject_transformation_mutation",
    ),
    (
        "command_idempotency_records",
        "trg_transformation_receipt_guard",
        "archie_guard_transformation_receipt",
    ),
    (
        "candidate_signals",
        "trg_candidate_signal_immutable",
        "archie_reject_transformation_mutation",
    ),
    (
        "evidence_records",
        "trg_evidence_record_immutable",
        "archie_reject_transformation_mutation",
    ),
    (
        "evidence_head_events",
        "trg_evidence_event_immutable",
        "archie_reject_transformation_mutation",
    ),
    (
        "evidence_claim_heads",
        "trg_evidence_head_guard",
        "archie_guard_evidence_head",
    ),
)

_EVIDENCE_EVENT_BINDING_TRIGGER = "trg_evidence_event_binding"


_IMMUTABLE_TABLES = (
    "operation_results",
    "transformation_outbox_events",
    "candidate_signals",
    "evidence_records",
    "evidence_head_events",
)


_COMMAND_TABLES = _IMMUTABLE_TABLES + (
    "command_idempotency_records",
    "evidence_claim_heads",
)


def _normalise_function_body(body: str) -> str:
    return "\n".join(line.rstrip() for line in body.strip().splitlines())


def _expected_function_body(create_sql: str) -> str:
    body = create_sql.split("AS $$", 1)[1].rsplit("$$", 1)[0]
    # ``exec_driver_sql`` passes percent signs through psycopg2's paramstyle;
    # doubled literals are stored by PostgreSQL as the intended single sign.
    return _normalise_function_body(body.replace("%%", "%"))


def inspect_transformation_db_guards(connection) -> list[str]:
    """Return semantic guard drift without changing database state."""
    if connection.dialect.name != "postgresql":
        return []
    drift: list[str] = []
    for function_name, create_sql in _FUNCTION_SPECS:
        row = connection.exec_driver_sql(
            """
            SELECT proc.prosrc, proc.prosecdef, proc.proconfig
            FROM pg_proc proc
            JOIN pg_namespace namespace ON namespace.oid = proc.pronamespace
            WHERE namespace.nspname = 'public'
              AND proc.proname = %s
              AND proc.pronargs = 0
              AND proc.prorettype = 'trigger'::regtype
            """,
            (function_name,),
        ).first()
        if row is None:
            drift.append(f"function_missing:{function_name}")
            continue
        if _normalise_function_body(row.prosrc) != _expected_function_body(create_sql):
            drift.append(f"function_body:{function_name}")
        if row.prosecdef is not True:
            drift.append(f"function_security:{function_name}")
        if "search_path=pg_catalog, public" not in (row.proconfig or []):
            drift.append(f"function_search_path:{function_name}")

    advance = connection.exec_driver_sql(
        """
        SELECT proc.prosrc, proc.prosecdef, proc.proconfig
        FROM pg_proc proc
        JOIN pg_namespace namespace ON namespace.oid = proc.pronamespace
        WHERE namespace.nspname = 'public'
          AND proc.proname = 'archie_advance_evidence_head'
          AND proc.pronargs = 7
          AND proc.prorettype = 'integer'::regtype
        """
    ).first()
    if advance is None:
        drift.append("function_missing:archie_advance_evidence_head")
    else:
        if _normalise_function_body(advance.prosrc) != _expected_function_body(
            _EVIDENCE_HEAD_ADVANCE_SQL
        ):
            drift.append("function_body:archie_advance_evidence_head")
        if advance.prosecdef is not True:
            drift.append("function_security:archie_advance_evidence_head")
        if "search_path=pg_catalog, public" not in (advance.proconfig or []):
            drift.append("function_search_path:archie_advance_evidence_head")

    for table_name, trigger_name, function_name in _TRIGGER_SPECS:
        table_present = connection.exec_driver_sql(
            f"SELECT to_regclass('public.{table_name}') IS NOT NULL"
        ).scalar()
        if not table_present:
            continue
        row = connection.exec_driver_sql(
            """
            SELECT trigger.tgenabled, trigger.tgtype,
                   trigger.tgqual IS NOT NULL AS has_when,
                   trigger.tgattr::text AS update_columns,
                   namespace.nspname AS function_schema,
                   proc.proname AS function_name
            FROM pg_trigger trigger
            JOIN pg_proc proc ON proc.oid = trigger.tgfoid
            JOIN pg_namespace namespace ON namespace.oid = proc.pronamespace
            WHERE trigger.tgname = %s
              AND trigger.tgrelid = to_regclass(%s)
              AND NOT trigger.tgisinternal
            """,
            (trigger_name, f"public.{table_name}"),
        ).first()
        if row is None:
            drift.append(f"trigger_missing:{trigger_name}")
            continue
        if row.tgenabled != "O":
            drift.append(f"trigger_disabled:{trigger_name}")
        if row.function_schema != "public" or row.function_name != function_name:
            drift.append(f"trigger_function:{trigger_name}")
        # Evidence heads also guard INSERT so they can only start empty at revision 0.
        expected_tgtype = 31 if table_name == "evidence_claim_heads" else 27
        if row.tgtype != expected_tgtype:
            drift.append(f"trigger_shape:{trigger_name}")
        if row.has_when:
            drift.append(f"trigger_when:{trigger_name}")
        if row.update_columns:
            drift.append(f"trigger_columns:{trigger_name}")

    if connection.exec_driver_sql(
        "SELECT to_regclass('public.evidence_head_events') IS NOT NULL"
    ).scalar():
        row = connection.exec_driver_sql(
            """
            SELECT trigger.tgenabled, trigger.tgtype, trigger.tgdeferrable,
                   trigger.tginitdeferred,
                   trigger.tgqual IS NOT NULL AS has_when,
                   trigger.tgattr::text AS update_columns,
                   namespace.nspname AS function_schema,
                   proc.proname AS function_name
            FROM pg_trigger trigger
            JOIN pg_proc proc ON proc.oid = trigger.tgfoid
            JOIN pg_namespace namespace ON namespace.oid = proc.pronamespace
            WHERE trigger.tgname = %s
              AND trigger.tgrelid = to_regclass('public.evidence_head_events')
              AND NOT trigger.tgisinternal
            """,
            (_EVIDENCE_EVENT_BINDING_TRIGGER,),
        ).first()
        if row is None:
            drift.append(
                f"trigger_missing:{_EVIDENCE_EVENT_BINDING_TRIGGER}"
            )
        else:
            if row.tgenabled != "O":
                drift.append(
                    f"trigger_disabled:{_EVIDENCE_EVENT_BINDING_TRIGGER}"
                )
            if (
                row.function_schema != "public"
                or row.function_name != "archie_guard_evidence_event_binding"
            ):
                drift.append(
                    f"trigger_function:{_EVIDENCE_EVENT_BINDING_TRIGGER}"
                )
            if (
                row.tgtype != 5
                or not row.tgdeferrable
                or not row.tginitdeferred
            ):
                drift.append(
                    f"trigger_shape:{_EVIDENCE_EVENT_BINDING_TRIGGER}"
                )
            if row.has_when:
                drift.append(f"trigger_when:{_EVIDENCE_EVENT_BINDING_TRIGGER}")
            if row.update_columns:
                drift.append(
                    f"trigger_columns:{_EVIDENCE_EVENT_BINDING_TRIGGER}"
                )
    return drift


def _repair_triggers(connection) -> None:
    for table_name, trigger_name, function_name in _TRIGGER_SPECS:
        table_present = connection.exec_driver_sql(
            f"SELECT to_regclass('public.{table_name}') IS NOT NULL"
        ).scalar()
        if not table_present:
            continue
        row = connection.exec_driver_sql(
            """
            SELECT trigger.tgenabled, trigger.tgtype,
                   trigger.tgqual IS NOT NULL AS has_when,
                   trigger.tgattr::text AS update_columns,
                   namespace.nspname AS function_schema,
                   proc.proname AS function_name
            FROM pg_trigger trigger
            JOIN pg_proc proc ON proc.oid = trigger.tgfoid
            JOIN pg_namespace namespace ON namespace.oid = proc.pronamespace
            WHERE trigger.tgname = %s
              AND trigger.tgrelid = to_regclass(%s)
              AND NOT trigger.tgisinternal
            """,
            (trigger_name, f"public.{table_name}"),
        ).first()
        expected_tgtype = 31 if table_name == "evidence_claim_heads" else 27
        correct = (
            row is not None
            and row.tgenabled == "O"
            and row.tgtype == expected_tgtype
            and not row.has_when
            and not row.update_columns
            and row.function_schema == "public"
            and row.function_name == function_name
        )
        if correct:
            continue
        connection.exec_driver_sql(
            f"DROP TRIGGER IF EXISTS {trigger_name} ON public.{table_name}"
        )
        events = (
            "INSERT OR UPDATE OR DELETE"
            if table_name == "evidence_claim_heads"
            else "UPDATE OR DELETE"
        )
        connection.exec_driver_sql(
            f"CREATE TRIGGER {trigger_name} "
            f"BEFORE {events} ON public.{table_name} "
            "FOR EACH ROW "
            f"EXECUTE FUNCTION public.{function_name}()"
        )

    if not connection.exec_driver_sql(
        "SELECT to_regclass('public.evidence_head_events') IS NOT NULL"
    ).scalar():
        return
    row = connection.exec_driver_sql(
        """
        SELECT trigger.tgenabled, trigger.tgtype, trigger.tgdeferrable,
               trigger.tginitdeferred,
               trigger.tgqual IS NOT NULL AS has_when,
               trigger.tgattr::text AS update_columns,
               namespace.nspname AS function_schema,
               proc.proname AS function_name
        FROM pg_trigger trigger
        JOIN pg_proc proc ON proc.oid = trigger.tgfoid
        JOIN pg_namespace namespace ON namespace.oid = proc.pronamespace
        WHERE trigger.tgname = %s
          AND trigger.tgrelid = to_regclass('public.evidence_head_events')
          AND NOT trigger.tgisinternal
        """,
        (_EVIDENCE_EVENT_BINDING_TRIGGER,),
    ).first()
    correct = (
        row is not None
        and row.tgenabled == "O"
        and row.tgtype == 5
        and row.tgdeferrable
        and row.tginitdeferred
        and not row.has_when
        and not row.update_columns
        and row.function_schema == "public"
        and row.function_name == "archie_guard_evidence_event_binding"
    )
    if not correct:
        connection.exec_driver_sql(
            "DROP TRIGGER IF EXISTS trg_evidence_event_binding "
            "ON public.evidence_head_events"
        )
        connection.exec_driver_sql(
            "CREATE CONSTRAINT TRIGGER trg_evidence_event_binding "
            "AFTER INSERT ON public.evidence_head_events "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
            "EXECUTE FUNCTION public.archie_guard_evidence_event_binding()"
        )


def ensure_transformation_db_guards(
    connection,
    *,
    runtime_role: str = TRANSFORMATION_RUNTIME_ROLE,
):
    """Install/refresh guards once under a transaction-scoped advisory lock."""
    if connection.dialect.name != "postgresql":
        return
    connection.exec_driver_sql(
        "SELECT pg_advisory_xact_lock(hashtext("
        "'archie_transformation_command_db_guards'))"
    )
    connection.exec_driver_sql(_IMMUTABILITY_FUNCTION_SQL)
    connection.exec_driver_sql(_RECEIPT_FUNCTION_SQL)
    connection.exec_driver_sql(_EVIDENCE_HEAD_GUARD_SQL)
    connection.exec_driver_sql(_EVIDENCE_EVENT_BINDING_SQL)
    connection.exec_driver_sql(_EVIDENCE_HEAD_ADVANCE_SQL)
    connection.exec_driver_sql(
        "REVOKE ALL ON FUNCTION public.archie_reject_transformation_mutation() FROM PUBLIC"
    )
    connection.exec_driver_sql(
        "REVOKE ALL ON FUNCTION public.archie_guard_transformation_receipt() FROM PUBLIC"
    )
    connection.exec_driver_sql(
        "REVOKE ALL ON FUNCTION public.archie_guard_evidence_head() FROM PUBLIC"
    )
    connection.exec_driver_sql(
        "REVOKE ALL ON FUNCTION "
        "public.archie_guard_evidence_event_binding() FROM PUBLIC"
    )
    connection.exec_driver_sql(
        "REVOKE ALL ON FUNCTION public.archie_advance_evidence_head("
        "bigint, bigint, integer, bigint, bigint, integer, text) FROM PUBLIC"
    )
    runtime_role_exists = connection.exec_driver_sql(
        "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)",
        (runtime_role,),
    ).scalar()
    runtime_role_identifier = connection.dialect.identifier_preparer.quote(
        runtime_role
    )
    if runtime_role_exists:
        connection.exec_driver_sql(
            "REVOKE ALL ON FUNCTION "
            "public.archie_reject_transformation_mutation() "
            f"FROM {runtime_role_identifier}"
        )
        connection.exec_driver_sql(
            "REVOKE ALL ON FUNCTION public.archie_guard_transformation_receipt() "
            f"FROM {runtime_role_identifier}"
        )
        connection.exec_driver_sql(
            "REVOKE ALL ON FUNCTION public.archie_guard_evidence_head() "
            f"FROM {runtime_role_identifier}"
        )
        connection.exec_driver_sql(
            "REVOKE ALL ON FUNCTION "
            "public.archie_guard_evidence_event_binding() "
            f"FROM {runtime_role_identifier}"
        )
        connection.exec_driver_sql(
            "GRANT EXECUTE ON FUNCTION public.archie_advance_evidence_head("
            "bigint, bigint, integer, bigint, bigint, integer, text) "
            f"TO {runtime_role_identifier}"
        )
    _repair_triggers(connection)
    # The runtime role gets only the columns required by the service protocol.
    # It never owns these objects and has no DELETE or TRUNCATE privilege.
    for table_name in _COMMAND_TABLES:
        present = connection.exec_driver_sql(
            f"SELECT to_regclass('public.{table_name}') IS NOT NULL"
        ).scalar()
        if present:
            connection.exec_driver_sql(
                f"REVOKE ALL ON TABLE public.{table_name} FROM PUBLIC"
            )
    if runtime_role_exists:
        for table_name in _COMMAND_TABLES:
            present = connection.exec_driver_sql(
                f"SELECT to_regclass('public.{table_name}') IS NOT NULL"
            ).scalar()
            if present:
                connection.exec_driver_sql(
                    f"REVOKE ALL ON TABLE public.{table_name} "
                    f"FROM {runtime_role_identifier}"
                )
                privileges = (
                    "SELECT"
                    if table_name == "evidence_head_events"
                    else "SELECT, INSERT"
                )
                connection.exec_driver_sql(
                    f"GRANT {privileges} ON TABLE public.{table_name} "
                    f"TO {runtime_role_identifier}"
                )
        if connection.exec_driver_sql(
            "SELECT to_regclass('public.transformation_outbox_events') IS NOT NULL"
        ).scalar():
            connection.exec_driver_sql(
                "GRANT UPDATE (delivery_attempts, published_at) ON TABLE "
                "public.transformation_outbox_events "
                f"TO {runtime_role_identifier}"
            )
        if connection.exec_driver_sql(
            "SELECT to_regclass('public.command_idempotency_records') IS NOT NULL"
        ).scalar():
            connection.exec_driver_sql(
                "GRANT UPDATE (status, lease_generation, claim_token, "
                "claimant_request_id, lease_expires_at, operation_result_id, "
                "attempt_count, last_error_class, updated_at, completed_at) "
                "ON TABLE public.command_idempotency_records "
                f"TO {runtime_role_identifier}"
            )
    remaining_drift = inspect_transformation_db_guards(connection)
    if remaining_drift:
        raise RuntimeError(
            "transformation database guard repair incomplete: "
            + ", ".join(remaining_drift)
        )


@event.listens_for(CommandIdempotencyRecord.__table__, "after_create")
@event.listens_for(OperationResult.__table__, "after_create")
@event.listens_for(OperationOutboxEvent.__table__, "after_create")
@event.listens_for(CandidateSignal.__table__, "after_create")
@event.listens_for(EvidenceRecord.__table__, "after_create")
@event.listens_for(EvidenceClaimHead.__table__, "after_create")
@event.listens_for(EvidenceHeadEvent.__table__, "after_create")
def _install_transformation_guards_after_create(_target, connection, **_kwargs):
    ensure_transformation_db_guards(connection)


__all__ = [
    "TRANSFORMATION_RUNTIME_ROLE",
    "ensure_transformation_db_guards",
    "inspect_transformation_db_guards",
]
