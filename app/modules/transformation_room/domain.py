"""Immutable boundary types and stable Transformation Room errors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ActorContext:
    user_id: int
    organization_id: int
    roles: frozenset[str]
    request_id: str


@dataclass(frozen=True)
class CommandClaim:
    receipt_id: int
    generation: int
    claim_token: str
    request_digest: str
    natural_key: str
    capability_document: str
    capability_mac: str


@dataclass(frozen=True)
class DomainMutationResult:
    object_ids: Mapping[str, int]
    response: Mapping[str, Any]
    outbox_events: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class CommandResult:
    created: bool
    idempotent: bool
    operation_result_id: int
    object_ids: Mapping[str, int]
    response: Mapping[str, Any]


@dataclass(frozen=True)
class GateBlocker:
    code: str
    message: str
    resource_type: str | None
    resource_id: int | None
    action_url: str | None


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    current_stage: str
    target_stage: str
    policy_version: str
    blockers: Sequence[GateBlocker]
    warnings: Sequence[GateBlocker]
    evidence_ids: Sequence[int]


@dataclass(frozen=True)
class ProgrammeIntake:
    name: str
    objective: str
    owner_id: int
    target_date: date | None
    target_date_unavailable_reason: str | None
    workstream_type: str
    scope_expression: Mapping[str, Any]
    outcome: Mapping[str, Any]


@dataclass(frozen=True)
class ProgrammeView:
    programme_id: int
    workstream_ids: Sequence[int]
    lifecycle: str
    owner_id: int
    next_action: GateBlocker | None


@dataclass(frozen=True)
class DiscoveryFilters:
    business_unit_ids: Sequence[int]
    capability_ids: Sequence[int]
    include_archived: bool = False


@dataclass(frozen=True)
class DiscoverySignal:
    rule_code: str
    rule_version: str
    source_record_ids: Mapping[str, Sequence[int]]
    evaluated_at: datetime
    observed_values: Mapping[str, Any]
    confidence: Decimal | None
    unknown_code: str | None
    content_hash: str


@dataclass(frozen=True)
class DiscoveryCandidate:
    application_id: int
    signal_digests: Sequence[str]
    confidence: Decimal | None
    unknown_codes: Sequence[str]
    signals: Sequence[DiscoverySignal] = ()


@dataclass(frozen=True)
class TypedEvidenceValue:
    value_type: str
    value: Any
    unit: str | None
    currency: str | None


@dataclass(frozen=True)
class SourceResolution:
    source_identity: str
    canonical_subject_type: str
    canonical_subject_id: int


@dataclass(frozen=True)
class SourceVersion:
    version: str
    checksum: str
    observed_at: datetime
    value: TypedEvidenceValue


@dataclass(frozen=True)
class FreshnessResult:
    status: str
    expires_at: datetime | None
    rule_version: str


@dataclass(frozen=True)
class HumanAssertions:
    reviewed_ai_material: bool
    acknowledged_unknown_codes: Sequence[str]
    acknowledged_superseded_evidence_ids: Sequence[int]
    rationale: str


@dataclass(frozen=True)
class OptionComparison:
    option_version_ids: Sequence[int]
    comparable_currency: str | None
    cost_range: tuple[Decimal, Decimal] | None
    benefit_range: tuple[Decimal, Decimal] | None
    conflicts: Sequence[str]


@dataclass(frozen=True)
class BriefReadiness:
    ready: bool
    gate: GateResult
    option_version_ids: Sequence[int]
    evidence_ids: Sequence[int]


@dataclass(frozen=True)
class GovernedSubject:
    subject_type: str
    subject_id: int
    organization_id: int
    title: str
    logical_version_id: int | None


@dataclass(frozen=True)
class PinnedEvidence:
    evidence_type: str
    evidence_id: int
    content_hash: str


@dataclass(frozen=True)
class ApprovedAction:
    action_key: str
    option_version_id: int
    title: str
    owner_id: int
    start_date: date | None
    target_date: date | None
    scheduling_applicable: bool


@dataclass(frozen=True)
class StageView:
    programme: ProgrammeView
    workstream_id: int
    stage: str
    gate: GateResult | None
    resources: Mapping[str, Sequence[Mapping[str, Any]]]
    unavailable_reasons: Mapping[str, str]


@dataclass(frozen=True)
class TransformationPortfolioView:
    programmes: Sequence[ProgrammeView]
    evidence_debt: Mapping[str, int | None]
    decision_ageing: Mapping[str, Decimal | None]
    cross_domain_dependencies: Mapping[str, int | None]
    delivery_confidence: Mapping[str, Decimal | None]
    outcome_variance: Mapping[str, Decimal | None]


class TransformationError(Exception):
    code = "transformation_error"
    http_status = 500

    def __init__(self, reason: str | None = None, **details: Any):
        self.reason = reason or self.code
        self.details = dict(details)
        for name, value in details.items():
            setattr(self, name, value)
        super().__init__(self.reason)


class CommandConflict(TransformationError):
    code, http_status = "conflict", 409


class StaleClaim(CommandConflict):
    code = "stale_claim"


class KnownPreCommitTransient(TransformationError):
    code, http_status = "retryable_failure", 503


class NotAuthorised(TransformationError):
    code, http_status = "not_authorised", 403


class NotFound(TransformationError):
    code, http_status = "not_found", 404


class BlockedByEvidence(TransformationError):
    code, http_status = "blocked_by_evidence", 422


class AuthenticationRequired(TransformationError):
    code, http_status = "not_authenticated", 401


__all__ = [
    "ActorContext",
    "ApprovedAction",
    "AuthenticationRequired",
    "BlockedByEvidence",
    "BriefReadiness",
    "CommandClaim",
    "CommandConflict",
    "CommandResult",
    "DiscoveryCandidate",
    "DiscoveryFilters",
    "DiscoverySignal",
    "DomainMutationResult",
    "FreshnessResult",
    "GateBlocker",
    "GateResult",
    "GovernedSubject",
    "HumanAssertions",
    "KnownPreCommitTransient",
    "NotAuthorised",
    "NotFound",
    "OptionComparison",
    "PinnedEvidence",
    "ProgrammeIntake",
    "ProgrammeView",
    "SourceResolution",
    "SourceVersion",
    "StageView",
    "StaleClaim",
    "TransformationError",
    "TransformationPortfolioView",
    "TypedEvidenceValue",
]
