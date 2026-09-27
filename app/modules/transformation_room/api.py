"""Canonical versioned HTTP API for the Transformation Room.

Every view is deliberately an adapter: it parses protocol values, builds a
server-owned actor, proves nested URL scope, then calls one public domain
service.  No route creates a model, commits, or calls ``CommandService``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from flask import Blueprint, current_app, request
from flask_wtf.csrf import CSRFError

from app.modules.transformation_room.arb_submission_service import (
    TypedARBSubmissionService,
)
from app.modules.transformation_room.decision_service import (
    DecisionBriefService,
    TransformationOptionService,
)
from app.modules.transformation_room.discovery_service import (
    RationalisationDiscoveryService,
)
from app.modules.transformation_room.domain import (
    ApprovedAction,
    DiscoveryFilters,
    HumanAssertions,
    NotFound,
    ProgrammeIntake,
    TypedEvidenceValue,
)
from app.modules.transformation_room.evidence_service import (
    TransformationEvidenceService,
)
from app.modules.transformation_room.execution_service import (
    TransformationExecutionService,
)
from app.modules.transformation_room.gate_service import TransformationGateService
from app.modules.transformation_room.http import (
    RequestValidationError,
    actor_context,
    api_endpoint,
    api_error,
    api_success,
    command_success,
    idempotency_key,
    if_match,
    iso_datetime,
    json_object,
)
from app.modules.transformation_room.outcome_service import OutcomeMeasurementService
from app.modules.transformation_room.programme_service import (
    TransformationProgrammeService,
)


transformation_api_bp = Blueprint(
    "transformation_api",
    __name__,
    url_prefix="/api/v1/transformation-programmes",
)


def _required(payload: Mapping[str, Any], field: str) -> Any:
    if field not in payload:
        raise RequestValidationError(f"{field} is required.", field=field)
    return payload[field]


def _integer(value: Any, field: str, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if isinstance(value, bool):
        raise RequestValidationError(f"{field} must be a positive integer.", field=field)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise RequestValidationError(
            f"{field} must be a positive integer.", field=field
        ) from error
    if parsed <= 0:
        raise RequestValidationError(f"{field} must be a positive integer.", field=field)
    return parsed


def _sequence(value: Any, field: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RequestValidationError(f"{field} must be an array.", field=field)
    return value


def _iso_date(value: Any, field: str, *, optional: bool = False) -> date | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RequestValidationError(f"{field} must be an ISO date.", field=field)
    try:
        return date.fromisoformat(value.strip())
    except ValueError as error:
        raise RequestValidationError(f"{field} must be an ISO date.", field=field) from error


def _boolean_query(field: str, default: bool = False) -> bool:
    value = request.args.get(field)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise RequestValidationError(f"{field} must be true or false.", field=field)


def _query_ids(field: str) -> tuple[int, ...]:
    raw_values = request.args.getlist(field)
    if not raw_values:
        return ()
    values: list[int] = []
    for raw in raw_values:
        for item in raw.split(","):
            values.append(_integer(item.strip(), field))
    if len(set(values)) != len(values):
        raise RequestValidationError(f"{field} values must be unique.", field=field)
    return tuple(values)


def _scoped_actor(programme_id: int, workstream_id: int | None = None):
    actor = actor_context(programme_id=programme_id, workstream_id=workstream_id)
    if workstream_id is not None:
        TransformationProgrammeService.get_workstream(
            actor=actor,
            programme_id=programme_id,
            workstream_id=workstream_id,
        )
    return actor


def _workstream_rows(actor, programme_id: int):
    programme = TransformationProgrammeService.get_programme(
        actor=actor, programme_id=programme_id
    )
    rows = TransformationProgrammeService.load_workstreams_for_tenant(
        actor, programme_id
    )
    by_id = {row.id: row for row in rows}
    if any(workstream_id not in by_id for workstream_id in programme.workstream_ids):
        raise NotFound("workstream_not_found")
    return tuple(by_id[workstream_id] for workstream_id in programme.workstream_ids)


def _typed_evidence(payload: Mapping[str, Any]) -> TypedEvidenceValue:
    value = _required(payload, "value")
    if not isinstance(value, Mapping):
        raise RequestValidationError("value must be an object.", field="value")
    return TypedEvidenceValue(
        value_type=_required(value, "value_type"),
        value=_required(value, "value"),
        unit=value.get("unit"),
        currency=value.get("currency"),
    )


def _human_assertions(payload: Mapping[str, Any]) -> HumanAssertions:
    assertions = _required(payload, "assertions")
    if not isinstance(assertions, Mapping):
        raise RequestValidationError("assertions must be an object.", field="assertions")
    return HumanAssertions(
        reviewed_ai_material=_required(assertions, "reviewed_ai_material"),
        acknowledged_unknown_codes=_sequence(
            _required(assertions, "acknowledged_unknown_codes"),
            "assertions.acknowledged_unknown_codes",
        ),
        acknowledged_superseded_evidence_ids=tuple(
            _integer(item, "assertions.acknowledged_superseded_evidence_ids")
            for item in _sequence(
                _required(assertions, "acknowledged_superseded_evidence_ids"),
                "assertions.acknowledged_superseded_evidence_ids",
            )
        ),
        rationale=_required(assertions, "rationale"),
    )


def _approved_actions(payload: Mapping[str, Any]) -> tuple[ApprovedAction, ...]:
    actions = _sequence(_required(payload, "actions"), "actions")
    parsed = []
    for index, action in enumerate(actions):
        if not isinstance(action, Mapping):
            raise RequestValidationError(
                "Each action must be an object.", field=f"actions.{index}"
            )
        parsed.append(
            ApprovedAction(
                action_key=_required(action, "action_key"),
                option_version_id=_integer(
                    _required(action, "option_version_id"),
                    f"actions.{index}.option_version_id",
                ),
                title=_required(action, "title"),
                owner_id=_integer(
                    _required(action, "owner_id"), f"actions.{index}.owner_id"
                ),
                start_date=_iso_date(
                    action.get("start_date"), f"actions.{index}.start_date", optional=True
                ),
                target_date=_iso_date(
                    action.get("target_date"), f"actions.{index}.target_date", optional=True
                ),
                scheduling_applicable=_required(action, "scheduling_applicable"),
            )
        )
    return tuple(parsed)


def _exporter(provider_key: str):
    registry = current_app.extensions.get("transformation_delivery_exporters", {})
    exporter = registry.get(provider_key) if isinstance(registry, Mapping) else None
    if callable(exporter):
        return exporter

    def unavailable_provider(_work_package, _request, _provider_idempotency_key):
        raise RuntimeError("The configured delivery provider is unavailable")

    return unavailable_provider


def _delivery_response(result, actor):
    if result.response.get("status") == "failed":
        return api_error(
            "provider_failed",
            "The delivery provider failed; the governed attempt was recorded.",
            status=502,
            request_id_value=actor.request_id,
            meta={
                "delivery_export_attempt_id": result.response.get(
                    "delivery_export_attempt_id"
                ),
                "idempotent": result.idempotent,
                "operation_result_id": result.operation_result_id,
            },
        )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.errorhandler(CSRFError)
def transformation_csrf_error(_error):
    return api_error(
        "validation_failed",
        "A valid CSRF token is required.",
        status=400,
        field="csrf_token",
    )


@transformation_api_bp.route("", methods=["GET"])
@api_endpoint
def list_programmes():
    actor = actor_context()
    programmes = TransformationProgrammeService.list_programmes(actor=actor)
    return api_success(
        {"programmes": programmes}, status=200, request_id_value=actor.request_id
    )


@transformation_api_bp.route("", methods=["POST"])
@api_endpoint
def create_programme():
    actor = actor_context()
    command_key = idempotency_key()
    payload = json_object()
    intake = ProgrammeIntake(
        name=_required(payload, "name"),
        objective=_required(payload, "objective"),
        owner_id=_integer(_required(payload, "owner_id"), "owner_id"),
        target_date=payload.get("target_date"),
        target_date_unavailable_reason=payload.get(
            "target_date_unavailable_reason"
        ),
        workstream_type=_required(payload, "workstream_type"),
        scope_expression=_required(payload, "scope_expression"),
        outcome=_required(payload, "outcome"),
    )
    result = TransformationProgrammeService.create_programme(
        actor=actor, command_key=command_key, request=intake
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route("/<int:programme_id>", methods=["GET"])
@api_endpoint
def get_programme(programme_id):
    actor = actor_context(programme_id=programme_id)
    programme = TransformationProgrammeService.get_programme(
        actor=actor, programme_id=programme_id
    )
    return api_success(programme, status=200, request_id_value=actor.request_id)


@transformation_api_bp.route("/<int:programme_id>", methods=["DELETE"])
@api_endpoint
def archive_programme(programme_id):
    actor = actor_context(programme_id=programme_id)
    command_key = idempotency_key()
    expected_revision = if_match()
    payload = json_object()
    result = TransformationProgrammeService.archive(
        actor=actor,
        programme_id=programme_id,
        rationale=_required(payload, "rationale"),
        expected_revision=expected_revision,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id)


@transformation_api_bp.route("/<int:programme_id>/role-assignments", methods=["POST"])
@api_endpoint
def assign_programme_role(programme_id):
    actor = actor_context(programme_id=programme_id)
    command_key = idempotency_key()
    expected_revision = if_match()
    payload = json_object()
    result = TransformationProgrammeService.assign_role(
        actor=actor,
        programme_id=programme_id,
        workstream_id=_integer(
            payload.get("workstream_id"), "workstream_id", optional=True
        ),
        user_id=_integer(_required(payload, "user_id"), "user_id"),
        role=_required(payload, "role"),
        effective_from=_required(payload, "effective_from"),
        effective_to=payload.get("effective_to"),
        expected_revision=expected_revision,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route("/<int:programme_id>/workstreams", methods=["GET"])
@api_endpoint
def list_workstreams(programme_id):
    actor = actor_context(programme_id=programme_id)
    rows = _workstream_rows(actor, programme_id)
    return api_success(
        {"workstreams": rows}, status=200, request_id_value=actor.request_id
    )


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>", methods=["GET"]
)
@api_endpoint
def get_workstream(programme_id, workstream_id):
    actor = _scoped_actor(programme_id, workstream_id)
    rows = _workstream_rows(actor, programme_id)
    workstream = next((row for row in rows if row.id == workstream_id), None)
    if workstream is None:
        raise NotFound("workstream_not_found")
    return api_success(workstream, status=200, request_id_value=actor.request_id)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>/objective",
    methods=["PATCH"],
)
@api_endpoint
def update_workstream_objective(programme_id, workstream_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    expected_revision = if_match()
    payload = json_object()
    result = TransformationProgrammeService.update_objective(
        actor=actor,
        workstream_id=workstream_id,
        objective=_required(payload, "objective"),
        scope_expression=_required(payload, "scope_expression"),
        expected_revision=expected_revision,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>/transitions",
    methods=["POST"],
)
@api_endpoint
def transition_workstream(programme_id, workstream_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    expected_revision = if_match()
    payload = json_object()
    result = TransformationGateService.transition(
        actor=actor,
        workstream_id=workstream_id,
        target_stage=_required(payload, "target_stage"),
        expected_revision=expected_revision,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>/discovery-candidates",
    methods=["GET"],
)
@api_endpoint
def discover_candidates(programme_id, workstream_id):
    actor = _scoped_actor(programme_id, workstream_id)
    filters = DiscoveryFilters(
        business_unit_ids=_query_ids("business_unit_id"),
        capability_ids=_query_ids("capability_id"),
        include_archived=_boolean_query("include_archived"),
    )
    candidates = RationalisationDiscoveryService.discover(
        actor=actor, workstream_id=workstream_id, filters=filters
    )
    return api_success(
        {"candidates": candidates}, status=200, request_id_value=actor.request_id
    )


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>/candidates",
    methods=["POST"],
)
@api_endpoint
def accept_candidate(programme_id, workstream_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    payload = json_object()
    result = RationalisationDiscoveryService.accept_candidate(
        actor=actor,
        workstream_id=workstream_id,
        application_id=_integer(
            _required(payload, "application_id"), "application_id"
        ),
        signal_digests=_sequence(
            _required(payload, "signal_digests"), "signal_digests"
        ),
        inclusion_reason=_required(payload, "inclusion_reason"),
        overlap_disposition=payload.get("overlap_disposition"),
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/candidates/<int:candidate_id>/evidence-requests",
    methods=["POST"],
)
@api_endpoint
def plan_evidence_requests(programme_id, workstream_id, candidate_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    payload = json_object()
    assignments = _required(payload, "assignments")
    if not isinstance(assignments, Mapping):
        raise RequestValidationError("assignments must be an object.", field="assignments")
    result = TransformationEvidenceService.plan_required_requests(
        actor=actor,
        candidate_id=candidate_id,
        assignments={
            str(claim): _integer(user_id, f"assignments.{claim}")
            for claim, user_id in assignments.items()
        },
        due_at=iso_datetime(payload.get("due_at"), "due_at", required=False),
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/candidates/<int:candidate_id>/evidence-observations",
    methods=["POST"],
)
@api_endpoint
def record_evidence_observation(programme_id, workstream_id, candidate_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    expected_head_revision = if_match(allow_zero=True)
    payload = json_object()
    result = TransformationEvidenceService.record_observation(
        actor=actor,
        candidate_id=candidate_id,
        claim_key=_required(payload, "claim_key"),
        adapter_key=_required(payload, "adapter_key"),
        source_key=_required(payload, "source_key"),
        expected_head_revision=expected_head_revision,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>/evidence", methods=["GET"]
)
@api_endpoint
def list_active_evidence(programme_id, workstream_id):
    actor = _scoped_actor(programme_id, workstream_id)
    subject_type = request.args.get("subject_type")
    subject_id = _integer(request.args.get("subject_id"), "subject_id")
    records = TransformationEvidenceService.active_evidence(
        actor=actor, subject_type=subject_type, subject_id=subject_id
    )
    return api_success(
        {"evidence": records}, status=200, request_id_value=actor.request_id
    )


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/evidence-requests/<int:evidence_request_id>/attestations",
    methods=["POST"],
)
@api_endpoint
def submit_evidence_attestation(
    programme_id, workstream_id, evidence_request_id
):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    expected_head_revision = if_match(allow_zero=True)
    payload = json_object()
    result = TransformationEvidenceService.submit_attestation(
        actor=actor,
        request_id=evidence_request_id,
        value=_typed_evidence(payload),
        expected_head_revision=expected_head_revision,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/evidence-requests/<int:evidence_request_id>/acceptance",
    methods=["POST"],
)
@api_endpoint
def accept_evidence_request(programme_id, workstream_id, evidence_request_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    expected_revision = if_match()
    payload = json_object()
    result = TransformationEvidenceService.accept_request(
        actor=actor,
        request_id=evidence_request_id,
        evidence_id=_integer(_required(payload, "evidence_id"), "evidence_id"),
        expected_revision=expected_revision,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/evidence-requests/<int:evidence_request_id>/decline",
    methods=["POST"],
)
@api_endpoint
def decline_evidence_request(programme_id, workstream_id, evidence_request_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    expected_revision = if_match()
    payload = json_object()
    result = TransformationEvidenceService.decline_request(
        actor=actor,
        request_id=evidence_request_id,
        reason=_required(payload, "reason"),
        expected_revision=expected_revision,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/evidence-requests/<int:evidence_request_id>/expiry",
    methods=["POST"],
)
@api_endpoint
def expire_evidence_request(programme_id, workstream_id, evidence_request_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    expected_revision = if_match()
    json_object()
    result = TransformationEvidenceService.expire_request(
        actor=actor,
        request_id=evidence_request_id,
        expected_revision=expected_revision,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/evidence-requests/<int:evidence_request_id>/waiver",
    methods=["POST"],
)
@api_endpoint
def waive_evidence_request(programme_id, workstream_id, evidence_request_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    expected_revision = if_match()
    payload = json_object()
    result = TransformationEvidenceService.waive_unavailable_request(
        actor=actor,
        request_id=evidence_request_id,
        reason=_required(payload, "reason"),
        expires_at=iso_datetime(_required(payload, "expires_at"), "expires_at"),
        interim_accountable_id=_integer(
            _required(payload, "interim_accountable_id"), "interim_accountable_id"
        ),
        expected_revision=expected_revision,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/evidence/<int:conflict_evidence_id>/resolution",
    methods=["POST"],
)
@api_endpoint
def resolve_evidence_conflict(
    programme_id, workstream_id, conflict_evidence_id
):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    payload = json_object()
    result = TransformationEvidenceService.resolve_conflict(
        actor=actor,
        conflict_evidence_id=conflict_evidence_id,
        governing_evidence_id=_integer(
            _required(payload, "governing_evidence_id"), "governing_evidence_id"
        ),
        rationale=_required(payload, "rationale"),
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>/options",
    methods=["POST"],
)
@api_endpoint
def create_option(programme_id, workstream_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    payload = json_object()
    draft = _required(payload, "draft")
    if not isinstance(draft, Mapping):
        raise RequestValidationError("draft must be an object.", field="draft")
    result = TransformationOptionService.create_draft(
        actor=actor,
        workstream_id=workstream_id,
        candidate_id=_integer(
            payload.get("candidate_id"), "candidate_id", optional=True
        ),
        draft=draft,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/options/<int:option_id>/versions",
    methods=["POST"],
)
@api_endpoint
def freeze_option(programme_id, workstream_id, option_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    expected_revision = if_match()
    json_object()
    result = TransformationOptionService.freeze_version(
        actor=actor,
        option_id=option_id,
        expected_revision=expected_revision,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>/option-comparison",
    methods=["GET"],
)
@api_endpoint
def compare_options(programme_id, workstream_id):
    actor = _scoped_actor(programme_id, workstream_id)
    version_ids = _query_ids("option_version_id")
    if not version_ids:
        raise RequestValidationError(
            "At least one option_version_id is required.", field="option_version_id"
        )
    comparison = TransformationOptionService.compare(
        actor=actor, option_version_ids=version_ids
    )
    return api_success(comparison, status=200, request_id_value=actor.request_id)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>/decision-briefs",
    methods=["POST"],
)
@api_endpoint
def create_decision_brief(programme_id, workstream_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    payload = json_object()
    result = DecisionBriefService.create_brief(
        actor=actor,
        workstream_id=workstream_id,
        candidate_id=_integer(
            payload.get("candidate_id"), "candidate_id", optional=True
        ),
        title=_required(payload, "title"),
        recommendation_option_id=_integer(
            _required(payload, "recommendation_option_id"),
            "recommendation_option_id",
        ),
        decision_authority_id=_integer(
            _required(payload, "decision_authority_id"), "decision_authority_id"
        ),
        unknown_codes=_sequence(
            _required(payload, "unknown_codes"), "unknown_codes"
        ),
        conflicts=_sequence(_required(payload, "conflicts"), "conflicts"),
        expected_impacts=_sequence(
            _required(payload, "expected_impacts"), "expected_impacts"
        ),
        option_exception=payload.get("option_exception"),
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/decision-briefs/<int:brief_id>/readiness",
    methods=["GET"],
)
@api_endpoint
def decision_brief_readiness(programme_id, workstream_id, brief_id):
    actor = _scoped_actor(programme_id, workstream_id)
    readiness = DecisionBriefService.evaluate(actor=actor, brief_id=brief_id)
    return api_success(readiness, status=200, request_id_value=actor.request_id)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/decision-briefs/<int:brief_id>/versions",
    methods=["POST"],
)
@api_endpoint
def freeze_decision_brief(programme_id, workstream_id, brief_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    expected_revision = if_match()
    payload = json_object()
    result = DecisionBriefService.freeze(
        actor=actor,
        brief_id=brief_id,
        option_version_ids=tuple(
            _integer(item, "option_version_ids")
            for item in _sequence(
                _required(payload, "option_version_ids"), "option_version_ids"
            )
        ),
        evidence_ids=tuple(
            _integer(item, "evidence_ids")
            for item in _sequence(_required(payload, "evidence_ids"), "evidence_ids")
        ),
        assertions=_human_assertions(payload),
        expected_revision=expected_revision,
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/decision-briefs/<int:brief_id>/arb-submissions",
    methods=["POST"],
)
@api_endpoint
def submit_decision_brief_to_arb(programme_id, workstream_id, brief_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    payload = json_object()
    assertions = payload.get("assertions") or {}
    if not isinstance(assertions, Mapping):
        raise RequestValidationError("assertions must be an object.", field="assertions")
    result = TypedARBSubmissionService.submit(
        actor=actor,
        command_key=command_key,
        subject_type="decision_brief",
        subject_id=brief_id,
        assertions=assertions,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/decision-brief-versions/<int:brief_version_id>/execution",
    methods=["POST"],
)
@api_endpoint
def materialise_execution(programme_id, workstream_id, brief_version_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    payload = json_object()
    result = TransformationExecutionService.materialise(
        actor=actor,
        decision_brief_version_id=brief_version_id,
        actions=_approved_actions(payload),
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/decision-brief-versions/<int:brief_version_id>/technology-solutions",
    methods=["POST"],
)
@api_endpoint
def create_technology_solution(programme_id, workstream_id, brief_version_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    payload = json_object()
    result = TransformationExecutionService.create_technology_solution(
        actor=actor,
        decision_brief_version_id=brief_version_id,
        option_version_id=_integer(
            _required(payload, "option_version_id"), "option_version_id"
        ),
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/work-packages/<int:work_package_id>/delivery-exports",
    methods=["POST"],
)
@api_endpoint
def export_work_package(programme_id, workstream_id, work_package_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    payload = json_object()
    provider_key = _required(payload, "provider_key")
    export_request = _required(payload, "request")
    if not isinstance(export_request, Mapping):
        raise RequestValidationError("request must be an object.", field="request")
    result = TransformationExecutionService.export_work_package(
        actor=actor,
        work_package_id=work_package_id,
        provider_key=provider_key,
        request=export_request,
        exporter=_exporter(str(provider_key).strip().lower()),
        command_key=command_key,
    )
    return _delivery_response(result, actor)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/work-packages/<int:work_package_id>/delivery-exports/<int:attempt_id>/retries",
    methods=["POST"],
)
@api_endpoint
def retry_work_package_export(
    programme_id, workstream_id, work_package_id, attempt_id
):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    payload = json_object()
    provider_key = _required(payload, "provider_key")
    export_request = _required(payload, "request")
    if not isinstance(export_request, Mapping):
        raise RequestValidationError("request must be an object.", field="request")
    result = TransformationExecutionService.export_work_package(
        actor=actor,
        work_package_id=work_package_id,
        provider_key=provider_key,
        request=export_request,
        exporter=_exporter(str(provider_key).strip().lower()),
        command_key=command_key,
        predecessor_attempt_id=attempt_id,
    )
    return _delivery_response(result, actor)


@transformation_api_bp.route(
    "/<int:programme_id>/workstreams/<int:workstream_id>"
    "/benefits/<int:benefit_id>/measurements",
    methods=["POST"],
)
@api_endpoint
def record_outcome_measurement(programme_id, workstream_id, benefit_id):
    actor = _scoped_actor(programme_id, workstream_id)
    command_key = idempotency_key()
    payload = json_object()
    raw_value = payload.get("value")
    try:
        value = Decimal(str(raw_value)) if raw_value is not None else None
    except (InvalidOperation, ValueError) as error:
        raise RequestValidationError("value must be numeric.", field="value") from error
    result = OutcomeMeasurementService.record(
        actor=actor,
        benefit_id=benefit_id,
        value=value,
        unavailable_reason=payload.get("unavailable_reason"),
        observed_at=iso_datetime(_required(payload, "observed_at"), "observed_at"),
        source_identity=_required(payload, "source_identity"),
        source_version=_required(payload, "source_version"),
        command_key=command_key,
    )
    return command_success(result, request_id_value=actor.request_id, created_status=201)


__all__ = ["transformation_api_bp"]
