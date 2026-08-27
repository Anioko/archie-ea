"""Command-fenced lifecycle transitions for canonical typed ARB conditions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hmac
import json

from flask import current_app
from sqlalchemy import select

from app import db
from app.models.architecture_review_board import ARBReviewCycle, ARBReviewItem
from app.models.arb_condition_event import ARBConditionEvent
from app.models.arb_condition_evidence import ARBConditionEvidenceRecord
from app.models.arb_decision_event import ARBCondition, ARBDecisionEvent
from app.models.user import User
from app.models.transformation_execution import CommandIdempotencyRecord
from app.modules.transformation_room.arb_condition_evidence_service import (
    TypedARBConditionEvidenceService,
)
from app.modules.transformation_room.arb_decision_service import TypedARBDecisionService
from app.modules.transformation_room.arb_submission_service import TypedARBSubmissionService
from app.modules.transformation_room.command_service import CommandService
from app.modules.transformation_room.domain import (
    ActorContext,
    CommandConflict,
    DomainMutationResult,
    NotAuthorised,
    NotFound,
)


class TypedARBConditionLifecycleService:
    SUBMIT_OPERATION = "arb.condition.evidence.submit"
    VERIFY_OPERATION = "arb.condition.evidence.verify"
    WAIVE_OPERATION = "arb.condition.waive"
    EXPIRE_OPERATION = "arb.condition.waiver.expire"
    SYSTEM_EVENT_TYPE = "waiver_expired"
    MAX_WAIVER_DAYS = 365
    MAX_WAIVER_SCOPE_BYTES = 16 * 1024
    NATURAL_KEY_RECONCILIATION = True
    CONCURRENT_TRANSITIONS_SERIALIZED = True
    ATOMIC_EVENT_CONDITION_CYCLE_REVIEW_RESULT = True
    TRANSITIONS = {
        "submit_evidence": {"pending": "evidence_submitted"},
        "verify": {"evidence_submitted": "fulfilled"},
        "waive": {"pending": "waived", "evidence_submitted": "waived"},
        "waiver_expired": {
            "waived:pending": "pending",
            "waived:evidence_submitted": "evidence_submitted",
        },
    }

    @staticmethod
    def natural_key(org_id, condition_id, event_type, revision):
        return f"arb-condition:{org_id}:{condition_id}:{event_type}:{revision}"

    @classmethod
    def submit_evidence(cls, *, actor, command_key, condition_id, condition_evidence_id):
        return cls._execute_actor_transition(
            actor=actor, command_key=command_key, condition_id=condition_id,
            event_type="submit_evidence", operation=cls.SUBMIT_OPERATION,
            condition_evidence_id=condition_evidence_id,
        )

    @classmethod
    def verify(cls, *, actor, command_key, condition_id, condition_evidence_id):
        return cls._execute_actor_transition(
            actor=actor, command_key=command_key, condition_id=condition_id,
            event_type="verify", operation=cls.VERIFY_OPERATION,
            condition_evidence_id=condition_evidence_id,
        )

    @classmethod
    def waive(
        cls, *, actor, command_key, condition_id, reason, expires_at, scope,
        compensating_control,
    ):
        waiver = cls.canonicalize_waiver(
            reason=reason, expires_at=expires_at, scope=scope,
            compensating_control=compensating_control, now=None,
        )
        return cls._execute_actor_transition(
            actor=actor, command_key=command_key, condition_id=condition_id,
            event_type="waive", operation=cls.WAIVE_OPERATION, waiver=waiver,
        )

    @classmethod
    def expire_waivers(
        cls, *, capability, command_key, condition_id, organization_id=None
    ):
        actor = cls._scheduler_actor(capability, organization_id=organization_id)
        return cls._execute(
            actor=actor, command_key=command_key, condition_id=condition_id,
            event_type="waiver_expired", operation=cls.EXPIRE_OPERATION,
            system=True,
        )

    @classmethod
    def _execute_actor_transition(cls, **kwargs):
        actor = kwargs["actor"]
        if not isinstance(actor, ActorContext):
            raise TypeError("actor must be ActorContext")
        return cls._execute(**kwargs)

    @classmethod
    def _execute(
        cls, *, actor, command_key, condition_id, event_type, operation,
        condition_evidence_id=None, waiver=None, system=False,
    ):
        if not isinstance(command_key, str) or not command_key.strip():
            raise ValueError("command_key is required")
        identity = cls._preload_identity(db.session, actor, condition_id)
        existing = cls._existing_receipt(db.session, actor, operation, command_key.strip())
        if existing is not None:
            natural_key = existing.natural_key
            prefix = cls.natural_key(
                actor.organization_id, condition_id, event_type, ""
            )
            if not natural_key.startswith(prefix):
                raise CommandConflict("arb_condition_command_identity_mismatch")
            revision = int(natural_key.rsplit(":", 1)[1])
        else:
            revision = cls._canonical_transition_revision(
                db.session, actor, identity, event_type, condition_evidence_id
            )
            natural_key = cls.natural_key(
                actor.organization_id, condition_id, event_type, revision
            )
        expected_revision = revision - 1
        payload = {
            "condition_id": condition_id, "event_type": event_type,
            "expected_revision": expected_revision,
            "condition_evidence_id": condition_evidence_id,
            "waiver": deepcopy(waiver),
        }

        def authorize(session, runtime_actor, runtime_operation, supplied_key):
            if runtime_operation != operation or supplied_key != natural_key:
                raise NotAuthorised("arb_condition_command_mismatch")
            authorizers = {
                "submit_evidence": cls.authorise_submit,
                "verify": cls.authorise_verify,
                "waive": cls.authorise_waive,
                "waiver_expired": cls.authorise_expiry,
            }
            authorizers[event_type](
                session, runtime_actor, condition_id, for_update=False
            )

        return CommandService.execute(
            actor=actor, operation=operation, idempotency_key=command_key.strip(),
            payload=payload, natural_key=natural_key, authorizer=authorize,
            natural_key_resolver=CommandService.fail_closed_pre_envelope_recovery,
            handler=lambda session, claim: cls._transition_locked(
                session=session, actor=actor, condition_id=condition_id,
                event_type=event_type, expected_revision=expected_revision,
                condition_evidence_id=condition_evidence_id, waiver=waiver,
                claim=claim, system=system,
            ),
        )

    @staticmethod
    def _existing_receipt(session, actor, operation, command_key):
        return session.execute(select(CommandIdempotencyRecord).where(
            CommandIdempotencyRecord.organization_id == actor.organization_id,
            CommandIdempotencyRecord.actor_id == actor.user_id,
            CommandIdempotencyRecord.operation == operation,
            CommandIdempotencyRecord.idempotency_key == command_key,
        )).scalar_one_or_none()

    @classmethod
    def _canonical_transition_revision(
        cls, session, actor, condition, event_type, evidence_id
    ):
        replay_projection = (
            (event_type == "submit_evidence" and condition.status == "evidence_submitted"
             and condition.submitted_evidence_id == evidence_id)
            or (event_type == "verify" and condition.status == "fulfilled"
                and condition.fulfilment_evidence_id == evidence_id)
            or (event_type == "waive" and condition.status == "waived")
            or event_type == "waiver_expired"
        )
        if replay_projection:
            event = session.execute(
                select(ARBConditionEvent).where(
                    ARBConditionEvent.organization_id == actor.organization_id,
                    ARBConditionEvent.condition_id == condition.id,
                    ARBConditionEvent.event_type == event_type,
                ).order_by(ARBConditionEvent.condition_revision.desc()).limit(1)
            ).scalar_one_or_none()
            if event is not None and event.to_state == condition.status:
                return event.condition_revision
        return condition.revision + 1

    @classmethod
    def _preload_identity(cls, session, actor, condition_id):
        condition = session.execute(select(ARBCondition).where(
            ARBCondition.id == condition_id,
            ARBCondition.organization_id == actor.organization_id,
        )).scalar_one_or_none()
        if condition is None:
            raise NotFound("arb_condition_not_found")
        return condition

    @classmethod
    def _transition_locked(
        cls, *, session, actor, condition_id, event_type, expected_revision,
        condition_evidence_id, waiver, claim, system,
    ):
        identity = cls._preload_identity(session, actor, condition_id)
        cycle_identity = session.execute(select(ARBReviewCycle).where(
            ARBReviewCycle.id == identity.review_cycle_id,
            ARBReviewCycle.organization_id == actor.organization_id,
        )).scalar_one_or_none()
        if cycle_identity is None:
            raise NotFound("arb_condition_not_found")
        TypedARBSubmissionService._lock_subject_submission(session, actor, cycle_identity)
        condition, decision, cycle, review, evidence, user = cls._lock_graph(
            session, actor, condition_id, condition_evidence_id
        )
        if system:
            cls._authorise_system_principal(session, actor, locked_user=user)
        else:
            cls.authorise_transition(
                session, actor, condition_id, event_type, for_update=True,
                locked_graph=(condition, decision, cycle, review, evidence, user),
            )
        if condition.revision != expected_revision:
            raise CommandConflict("arb_condition_revision_changed")
        to_state = cls._target(condition, event_type)
        if event_type == "verify" and (
            condition.evidence_submitted_by_id == actor.user_id
            or review.submitter_id == actor.user_id
        ):
            raise NotAuthorised("arb_condition_verification_separation_required")
        if event_type in {"submit_evidence", "verify"}:
            cls._assert_evidence(
                condition, decision, evidence, condition_evidence_id, event_type
            )
        now = CommandService._database_now(session)
        if event_type == "waive":
            waiver = cls.canonicalize_waiver(**waiver, now=now)
            waiver["prior_status"] = condition.status
        elif event_type == "waiver_expired":
            if condition.waiver_expires_at is None or condition.waiver_expires_at > now:
                raise CommandConflict("arb_condition_waiver_not_expired")
            waiver = deepcopy(condition.waiver_scope_json) or {}
            waiver["prior_status"] = condition.waiver_prior_status
        statuses = session.execute(select(ARBCondition.status).where(
            ARBCondition.decision_event_id == decision.id,
            ARBCondition.organization_id == actor.organization_id,
            ARBCondition.id != condition.id,
        )).scalars().all()
        projected_status = cls.project_outcome(
            prior_outcome=cycle.status,
            condition_statuses=tuple(statuses) + (to_state,),
        )
        projection_revision = (cycle.condition_projection_revision or 0) + 1
        event = ARBConditionEvent(
            organization_id=actor.organization_id, condition_id=condition.id,
            decision_event_id=decision.id, review_cycle_id=cycle.id,
            review_item_id=review.id, subject_type=decision.subject_type,
            subject_id=decision.subject_id, event_type=event_type,
            from_state=condition.status, to_state=to_state,
            condition_revision=expected_revision + 1,
            submitted_evidence_id=condition_evidence_id,
            waiver_scope_json=deepcopy(waiver), projection_status=projected_status,
            projection_revision=projection_revision, actor_id=actor.user_id,
            command_receipt_id=claim.receipt_id,
            command_generation=claim.generation,
        )
        session.add(event)
        session.flush()
        prior_status = condition.status
        condition.status = to_state
        condition.revision = expected_revision + 1
        cls._apply_condition_fields(
            condition, event_type, actor.user_id, condition_evidence_id,
            waiver, prior_status, now,
        )
        session.flush()
        cls._project_review(
            cycle, review, projected_status, projection_revision
        )
        session.flush()
        object_ids = {
            "condition_id": condition.id, "condition_event_id": event.id,
            "condition_revision": condition.revision,
            "review_cycle_id": cycle.id, "review_item_id": review.id,
        }
        return DomainMutationResult(
            object_ids=object_ids,
            response={**object_ids, "status": to_state,
                      "projection_status": projected_status},
            outbox_events=(),
        )

    @classmethod
    def _lock_graph(cls, session, actor, condition_id, evidence_id):
        unlocked = cls._preload_identity(session, actor, condition_id)
        cycle = cls._lock_one(session, ARBReviewCycle, unlocked.review_cycle_id, actor)
        review = cls._lock_one(session, ARBReviewItem, unlocked.review_item_id, actor)
        decision = cls._lock_one(session, ARBDecisionEvent, unlocked.decision_event_id, actor)
        condition = cls._lock_one(session, ARBCondition, condition_id, actor)
        evidence = None
        if evidence_id is not None:
            evidence = cls._lock_one(
                session, ARBConditionEvidenceRecord, evidence_id, actor
            )
        user = cls._lock_one(session, User, actor.user_id, actor)
        return condition, decision, cycle, review, evidence, user

    @staticmethod
    def _lock_one(session, model, object_id, actor):
        row = session.execute(select(model).where(
            model.id == object_id,
            model.organization_id == actor.organization_id,
        ).with_for_update()).scalar_one_or_none()
        if row is None:
            raise NotFound("arb_condition_not_found")
        return row

    @classmethod
    def authorise_transition(
        cls, session, actor, condition_id, event_type, *, for_update,
        locked_graph=None,
    ):
        graph = locked_graph or (*cls._load_graph(session, actor, condition_id), None, None)
        condition, _decision, cycle, review, _evidence, user = graph
        if user is None:
            statement = select(User).where(
                User.id == actor.user_id,
                User.organization_id == actor.organization_id,
            )
            if for_update:
                statement = statement.with_for_update()
            user = session.execute(statement).scalar_one_or_none()
        if user is None:
            raise NotAuthorised("arb_condition_transition_not_authorised")
        if event_type == "submit_evidence":
            TypedARBConditionEvidenceService.authorise_acceptance(
                session, actor, condition_id, for_update=for_update
            )
            return
        TypedARBDecisionService.authorise_decision(
            session, actor, cycle.id, for_update=for_update
        )
        if event_type == "verify" and (
            condition.evidence_submitted_by_id == user.id
            or review.submitter_id == user.id
        ):
            raise NotAuthorised("arb_condition_verification_separation_required")

    @classmethod
    def authorise_submit(cls, session, actor, condition_id, *, for_update=False):
        return cls.authorise_transition(
            session, actor, condition_id, "submit_evidence", for_update=for_update
        )

    @classmethod
    def authorise_verify(cls, session, actor, condition_id, *, for_update=False):
        return cls.authorise_transition(
            session, actor, condition_id, "verify", for_update=for_update
        )

    @classmethod
    def authorise_waive(cls, session, actor, condition_id, *, for_update=False):
        return cls.authorise_transition(
            session, actor, condition_id, "waive", for_update=for_update
        )

    @classmethod
    def authorise_expiry(cls, session, actor, condition_id, *, for_update=False):
        del condition_id, for_update
        return cls._authorise_system_principal(session, actor)

    @classmethod
    def _load_graph(cls, session, actor, condition_id):
        condition = cls._preload_identity(session, actor, condition_id)
        decision = session.execute(select(ARBDecisionEvent).where(
            ARBDecisionEvent.id == condition.decision_event_id,
            ARBDecisionEvent.organization_id == actor.organization_id,
        )).scalar_one_or_none()
        cycle = session.execute(select(ARBReviewCycle).where(
            ARBReviewCycle.id == condition.review_cycle_id,
            ARBReviewCycle.organization_id == actor.organization_id,
        )).scalar_one_or_none()
        review = session.execute(select(ARBReviewItem).where(
            ARBReviewItem.id == condition.review_item_id,
            ARBReviewItem.organization_id == actor.organization_id,
        )).scalar_one_or_none()
        if any(row is None for row in (decision, cycle, review)):
            raise NotFound("arb_condition_not_found")
        return condition, decision, cycle, review

    @staticmethod
    def _assert_evidence(condition, decision, evidence, evidence_id, event_type):
        if evidence is None or evidence.id != evidence_id or any((
            evidence.condition_id != condition.id,
            evidence.decision_event_id != decision.id,
            evidence.review_cycle_id != condition.review_cycle_id,
            evidence.review_item_id != condition.review_item_id,
            evidence.organization_id != condition.organization_id,
            event_type == "submit_evidence"
            and evidence.condition_revision != condition.revision,
            event_type == "verify"
            and evidence.condition_revision >= condition.revision,
        )):
            raise CommandConflict("arb_condition_evidence_membership_mismatch")

    @classmethod
    def _target(cls, condition, event_type):
        key = condition.status
        if event_type == "waiver_expired":
            key = f"waived:{condition.waiver_prior_status}"
        target = cls.TRANSITIONS.get(event_type, {}).get(key)
        if target is None:
            raise CommandConflict("arb_condition_transition_invalid")
        return target

    @staticmethod
    def _apply_condition_fields(
        condition, event_type, actor_id, evidence_id, waiver, prior_status, now
    ):
        if event_type == "submit_evidence":
            condition.submitted_evidence_id = evidence_id
            condition.evidence_submitted_by_id = actor_id
            condition.evidence_submitted_at = now
        elif event_type == "verify":
            condition.verified_by_id = actor_id
            condition.verified_at = now
            condition.fulfilled_by_id = actor_id
            condition.fulfilled_at = now
            condition.fulfilment_evidence_id = evidence_id
        elif event_type == "waive":
            condition.waived_by_id = actor_id
            condition.waived_at = now
            condition.waiver_reason = waiver["reason"]
            condition.waiver_expires_at = datetime.fromisoformat(
                waiver["expires_at"].replace("Z", "+00:00")
            )
            condition.compensating_control = waiver["compensating_control"]
            condition.waiver_prior_status = prior_status
            condition.waiver_scope_json = waiver
        else:
            condition.waived_at = None
            condition.waived_by_id = None
            condition.waiver_reason = None
            condition.waiver_expires_at = None
            condition.compensating_control = None
            condition.waiver_scope_json = None
            condition.waiver_prior_status = None

    @staticmethod
    def project_outcome(*, prior_outcome, condition_statuses):
        blocking = any(status not in {"fulfilled", "waived"} for status in condition_statuses)
        if blocking:
            return "approved_with_conditions"
        return "approved"

    @staticmethod
    def _project_review(cycle, review, projected_status, projection_revision):
        cycle.status = projected_status
        review.status = projected_status
        cycle.condition_projection_revision = projection_revision
        review.condition_projection_revision = projection_revision

    @classmethod
    def canonicalize_waiver(
        cls, *, reason, expires_at, scope, compensating_control, now
    ):
        reason = cls._bounded_text(reason, "reason", 2000)
        control = cls._bounded_text(compensating_control, "compensating_control", 2000)
        if not isinstance(scope, dict) or not scope:
            raise ValueError("waiver scope is required")
        if len(json.dumps(scope, sort_keys=True, separators=(",", ":")).encode()) > cls.MAX_WAIVER_SCOPE_BYTES:
            raise ValueError("waiver scope is too large")
        expires = cls._aware_datetime(expires_at)
        if now is not None and (
            expires <= now or expires > now + timedelta(days=cls.MAX_WAIVER_DAYS)
        ):
            raise ValueError("waiver expiry is outside the permitted window")
        return {
            "reason": reason,
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
            "scope": deepcopy(scope), "compensating_control": control,
        }

    @staticmethod
    def _bounded_text(value, field, limit):
        if not isinstance(value, str):
            raise ValueError(f"{field} is required")
        value = " ".join(value.split())
        if not value or len(value) > limit or any(ord(ch) < 32 for ch in value):
            raise ValueError(f"invalid {field}")
        return value

    @staticmethod
    def _aware_datetime(value):
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError("waiver expiry must be timezone-aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _expiry_target(condition):
        if condition.status != "waived" or condition.waiver_prior_status not in {
            "pending", "evidence_submitted",
        }:
            raise CommandConflict("arb_condition_waiver_state_invalid")
        return condition.waiver_prior_status

    @staticmethod
    def _load_active_board_membership(*args, **kwargs):
        return TypedARBDecisionService._has_board_authority(*args, **kwargs)

    @staticmethod
    def _load_pinned_decision_brief_authority(*args, **kwargs):
        return TypedARBDecisionService._has_decision_brief_authority(*args, **kwargs)

    @classmethod
    def _reauthorise_replay(cls, session, actor, condition_id, event_type):
        return cls.authorise_transition(
            session, actor, condition_id, event_type, for_update=False
        )

    @staticmethod
    def _scheduler_actor(capability, *, organization_id=None):
        secret = current_app.config.get("ARB_CONDITION_EXPIRY_CAPABILITY")
        if not secret or not isinstance(capability, str) or not hmac.compare_digest(capability, secret):
            raise NotAuthorised("arb_condition_expiry_capability_required")
        if organization_id is None:
            organization_id = current_app.config.get(
                "ARB_CONDITION_EXPIRY_ORGANIZATION_ID"
            )
        if (
            not isinstance(organization_id, int)
            or isinstance(organization_id, bool)
            or organization_id <= 0
        ):
            raise NotAuthorised("arb_condition_expiry_tenant_required")
        principal_id = TypedARBConditionLifecycleService._configured_scheduler_principal(
            organization_id
        )
        if not principal_id:
            raise NotAuthorised("arb_condition_expiry_principal_invalid")
        return ActorContext(principal_id, organization_id, frozenset(), "arb-expiry-scheduler")

    @staticmethod
    def _configured_scheduler_principal(organization_id):
        principals = current_app.config.get("ARB_CONDITION_EXPIRY_PRINCIPALS", {})
        if isinstance(principals, str):
            try:
                principals = json.loads(principals)
            except json.JSONDecodeError as error:
                raise NotAuthorised("arb_condition_expiry_principal_config_invalid") from error
        if not isinstance(principals, dict):
            raise NotAuthorised("arb_condition_expiry_principal_config_invalid")
        principal_id = principals.get(str(organization_id), principals.get(organization_id))
        legacy_organization_id = current_app.config.get(
            "ARB_CONDITION_EXPIRY_ORGANIZATION_ID"
        )
        if principal_id is None and legacy_organization_id == organization_id:
            principal_id = current_app.config.get("ARB_CONDITION_EXPIRY_PRINCIPAL_ID")
        if (
            not isinstance(principal_id, int)
            or isinstance(principal_id, bool)
            or principal_id <= 0
        ):
            return None
        return principal_id

    @staticmethod
    def _authorise_system_principal(session, actor, locked_user=None):
        user = locked_user or session.execute(select(User).where(
            User.id == actor.user_id,
            User.organization_id == actor.organization_id,
        ).with_for_update()).scalar_one_or_none()
        configured = TypedARBConditionLifecycleService._configured_scheduler_principal(
            actor.organization_id
        )
        if (
            user is None
            or user.organization_id != actor.organization_id
            or user.confirmed is not True
            or actor.user_id != configured
        ):
            raise NotAuthorised("arb_condition_expiry_principal_invalid")


__all__ = ["TypedARBConditionLifecycleService"]
