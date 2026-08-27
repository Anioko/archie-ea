"""Replay-safe submission of typed governed subjects to the ARB."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import timezone
import hashlib
import uuid
from typing import Any, Mapping

from flask import has_app_context
from sqlalchemy import select, text

from app import db
from app.models.architecture_review_board import ARBReviewCycle, ARBReviewItem
from app.modules.transformation_room.command_service import CommandService
from app.modules.transformation_room.domain import (
    ActorContext,
    BlockedByEvidence,
    CommandConflict,
    DomainMutationResult,
    GovernedSubject,
    NotAuthorised,
)


_SUBJECT_COLUMNS = {
    "decision_brief": "decision_brief_id",
    "solution": "solution_id",
    "architecture_model": "architecture_model_id",
    "adr": "adr_id",
}
_EVIDENCE_COLUMNS = {
    "decision_brief": ("decision_brief_version_id", "decision_brief_version"),
    "solution": ("solution_evidence_snapshot_id", "solution_evidence_snapshot"),
    "architecture_model": (
        "subject_evidence_snapshot_id",
        "arb_subject_evidence_snapshot",
    ),
    "adr": ("subject_evidence_snapshot_id", "arb_subject_evidence_snapshot"),
}


def get_arb_subject_adapter(subject_type):
    """Import lazily so this boundary does not change the legacy model load order."""
    from app.modules.transformation_room.arb_adapters import (
        get_arb_subject_adapter as resolve,
    )

    return resolve(subject_type)


def _required_command_key(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("command_key is required")
    return value.strip()


def _required_subject_id(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("subject_id must be a positive integer")
    return value


@contextmanager
def _adapter_session(session):
    """Make legacy adapter calls participate in CommandService's transaction.

    Subject adapters pre-date the explicit-session command boundary and use the
    Flask-SQLAlchemy scoped session. Temporarily pointing that registry at the
    fenced command session keeps their locks and snapshot insert in the same
    atomic transaction without opening a second persistence authority.
    """

    if not has_app_context():
        # Unit-level command-boundary tests supply an inert session and adapters
        # that do not touch Flask-SQLAlchemy. Production commands require an app
        # context already because CommandService reads current_app configuration.
        yield
        return
    registry = db.session.registry
    had_previous = registry.has()
    previous = registry() if had_previous else None
    registry.set(session)
    try:
        yield
    finally:
        if had_previous:
            registry.set(previous)
        else:
            registry.clear()


class TypedARBSubmissionService:
    """The sole command boundary for new typed ARB review cycles."""

    OPERATION = "arb.submit"

    @classmethod
    def submit(
        cls,
        *,
        actor: ActorContext,
        command_key: str,
        subject_type: str,
        subject_id: int,
        assertions: Mapping[str, Any] | None = None,
    ):
        if not isinstance(actor, ActorContext):
            raise TypeError("actor must be ActorContext")
        command_key = _required_command_key(command_key)
        subject_id = _required_subject_id(subject_id)
        adapter = get_arb_subject_adapter(subject_type)
        supplied_assertions = deepcopy(dict(assertions or {}))

        # Fail closed before creating a durable command receipt for a foreign or
        # malformed identity. The authorizer repeats this check for every replay.
        subject = adapter.load(actor, subject_id)
        cls._validate_loaded_subject(actor, subject, subject_type, subject_id)
        natural_key = (
            f"arb-submission:{actor.organization_id}:{subject_type}:{subject_id}"
        )
        payload = {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "assertions": supplied_assertions,
        }

        def authorize(session, runtime_actor, operation, supplied_key):
            if operation != cls.OPERATION or supplied_key != natural_key:
                raise NotAuthorised("arb_submission_command_mismatch")
            if runtime_actor.organization_id != actor.organization_id:
                raise NotAuthorised("arb_submission_actor_mismatch")
            with _adapter_session(session):
                current = adapter.load(runtime_actor, subject_id)
            cls._validate_loaded_subject(
                runtime_actor, current, subject_type, subject_id
            )

        return CommandService.execute(
            actor=actor,
            operation=cls.OPERATION,
            idempotency_key=command_key,
            payload=payload,
            natural_key=natural_key,
            authorizer=authorize,
            natural_key_resolver=CommandService.fail_closed_pre_envelope_recovery,
            handler=lambda session, claim: cls._submit_locked(
                session=session,
                actor=actor,
                subject=subject,
                adapter=adapter,
                assertions=supplied_assertions,
                claim=claim,
            ),
        )

    @classmethod
    def submit_legacy_solution(
        cls,
        *,
        actor: ActorContext,
        command_key: str,
        solution_id: int,
        workspace_id: int | None = None,
        assertions: Mapping[str, Any] | None = None,
    ):
        supplied = deepcopy(dict(assertions or {}))
        if workspace_id is not None:
            supplied["workspace_id"] = workspace_id
        return cls.submit(
            actor=actor,
            command_key=command_key,
            subject_type="solution",
            subject_id=solution_id,
            assertions=supplied,
        )

    @classmethod
    def _submit_locked(cls, *, session, actor, subject, adapter, assertions, claim):
        del claim  # fencing is enforced by the session before the first write
        cls._lock_subject_submission(session, actor, subject)
        with _adapter_session(session):
            # Adapter.snapshot performs the subject-specific FOR UPDATE and then
            # re-evaluates. The initial evaluation supplies its comparison input.
            readiness = adapter.evaluate(actor, subject, assertions)
            if not readiness.ready:
                raise BlockedByEvidence(
                    "arb_subject_not_ready",
                    reason_codes=list(readiness.reason_codes),
                    missing_evidence=list(readiness.missing_evidence),
                )
            review_item_id = (
                cls._reserve_review_item_id(session)
                if subject.subject_type == "solution"
                else None
            )
            pinned = adapter.snapshot(
                actor,
                subject,
                readiness,
                review_item_id=review_item_id,
            )
            return cls._insert_submission_graph(
                session=session,
                actor=actor,
                subject=subject,
                adapter=adapter,
                pinned_evidence=pinned,
                review_item_id=review_item_id,
            )

    @staticmethod
    def _reserve_review_item_id(session):
        return session.scalar(
            text(
                "SELECT nextval(pg_get_serial_sequence("
                "'arb_review_items', 'id'))"
            )
        )

    @staticmethod
    def _subject_lock_key(organization_id, subject_type, subject_id):
        identity = f"{organization_id}:{subject_type}:{subject_id}".encode("utf-8")
        return int.from_bytes(
            hashlib.sha256(identity).digest()[:8], byteorder="big", signed=True
        )

    @classmethod
    def _lock_subject_submission(cls, session, actor, subject):
        """Serialize first and successor cycle allocation for one typed subject."""
        session.execute(
            text(
                "SELECT pg_advisory_xact_lock(:lock_key) "
                "/* tenancy-ok: deterministic key includes organization_id */"
            ),
            {
                "lock_key": cls._subject_lock_key(
                    actor.organization_id, subject.subject_type, subject.subject_id
                )
            },
        )

    @classmethod
    def _insert_submission_graph(
        cls, *, session, actor, subject, adapter, pinned_evidence, review_item_id=None
    ) -> DomainMutationResult:
        subject_column = _SUBJECT_COLUMNS[subject.subject_type]
        evidence_column, expected_evidence_type = _EVIDENCE_COLUMNS[
            subject.subject_type
        ]
        if pinned_evidence.evidence_type != expected_evidence_type:
            raise CommandConflict("arb_evidence_type_mismatch")

        history = list(
            session.execute(
                select(ARBReviewCycle)
                .where(
                    ARBReviewCycle.organization_id == actor.organization_id,
                    ARBReviewCycle.subject_type == subject.subject_type,
                    ARBReviewCycle.subject_id == subject.subject_id,
                )
                .order_by(ARBReviewCycle.cycle_number.desc(), ARBReviewCycle.id.desc())
                .with_for_update()
            ).scalars()
        )
        if history and history[0].closed_at is None:
            raise CommandConflict("arb_subject_already_has_open_cycle")
        predecessor = history[0] if history else None
        cycle_number = predecessor.cycle_number + 1 if predecessor else 1
        now = CommandService._database_now(session)
        review_number = f"REV-{now:%Y}-{uuid.uuid4().hex[:12].upper()}"
        typed_values = {
            "organization_id": actor.organization_id,
            "subject_type": subject.subject_type,
            "subject_id": subject.subject_id,
            subject_column: subject.subject_id,
            evidence_column: pinned_evidence.evidence_id,
        }
        cycle = ARBReviewCycle(
            **typed_values,
            review_number=review_number,
            cycle_number=cycle_number,
            predecessor_cycle_id=predecessor.id if predecessor else None,
            status="submitted",
            opened_at=now,
        )
        session.add(cycle)
        session.flush()
        review = ARBReviewItem(
            **typed_values,
            id=review_item_id,
            review_cycle_id=cycle.id,
            review_number=review_number,
            title=f"{subject.title} ARB review",
            description=f"Governed {subject.subject_type} submission",
            review_type=getattr(adapter, "review_type", "architecture_change"),
            priority="medium",
            status="submitted",
            submitter_id=actor.user_id,
            submitted_at=now.astimezone(timezone.utc).replace(tzinfo=None),
        )
        session.add(review)
        session.flush()
        response = {
            "review_cycle_id": cycle.id,
            "review_item_id": review.id,
            "evidence_id": pinned_evidence.evidence_id,
            "review_number": review_number,
            "cycle_number": cycle_number,
            "subject_type": subject.subject_type,
            "subject_id": subject.subject_id,
            "status": "submitted",
            "canonical_url": adapter.canonical_url(subject),
        }
        return DomainMutationResult(
            object_ids={
                "review_cycle_id": cycle.id,
                "review_item_id": review.id,
                "evidence_id": pinned_evidence.evidence_id,
            },
            response=response,
            outbox_events=(),
        )

    @staticmethod
    def _validate_loaded_subject(actor, subject, subject_type, subject_id):
        if (
            not isinstance(subject, GovernedSubject)
            or subject.subject_type != subject_type
            or subject.subject_id != subject_id
            or subject.organization_id != actor.organization_id
        ):
            raise NotAuthorised("arb_subject_outside_actor_tenant")


__all__ = ["TypedARBSubmissionService"]
