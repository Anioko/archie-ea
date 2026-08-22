"""Fenced, reconcile-before-retry command execution for Transformation Room writes."""

from __future__ import annotations

import copy
import hashlib
import json
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Mapping, TypeAlias

from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session

from app import db
from app.models.transformation_execution import (
    CommandIdempotencyRecord,
    OperationOutboxEvent,
    OperationResult,
)
from app.modules.transformation_room.domain import (
    ActorContext,
    CommandClaim,
    CommandConflict,
    CommandResult,
    DomainMutationResult,
    KnownPreCommitTransient,
    StaleClaim,
    TransformationError,
)


def _canonical_json_default(value: Any):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, frozenset):
        return sorted(value)
    raise TypeError(f"{type(value).__name__} is not canonical JSON")


def canonical_request_digest(payload: Mapping[str, Any]) -> str:
    """Return SHA-256 over UTF-8, sorted, whitespace-free canonical JSON."""
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_canonical_json_default,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


OperationNaturalKeyResolver: TypeAlias = Callable[
    [Session, ActorContext, str, CommandClaim], DomainMutationResult | None
]
OperationAuthorizer: TypeAlias = Callable[
    [Session, ActorContext, str, str], None
]


class CommandService:
    """Own the claim transaction and one atomic domain/result/finalise transaction."""

    DEFAULT_LEASE_SECONDS = 30.0

    @classmethod
    def request_digest(cls, payload: Mapping[str, Any]) -> str:
        return canonical_request_digest(payload)

    @classmethod
    def _lease_seconds(cls) -> float:
        return max(
            0.01,
            float(
                current_app.config.get(
                    "TRANSFORMATION_COMMAND_LEASE_SECONDS", cls.DEFAULT_LEASE_SECONDS
                )
            ),
        )

    @staticmethod
    def _database_now(session: Session) -> datetime:
        value = session.scalar(select(func.clock_timestamp()))
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _new_claim_token() -> str:
        return secrets.token_hex(32)

    @staticmethod
    def _require_authorizer(authorizer: OperationAuthorizer) -> OperationAuthorizer:
        if not callable(authorizer):
            raise TypeError("authorizer must be callable")
        return authorizer

    @staticmethod
    def claim_from_record(record: CommandIdempotencyRecord) -> CommandClaim:
        return CommandClaim(
            receipt_id=record.id,
            generation=record.lease_generation,
            claim_token=record.claim_token,
            request_digest=record.request_digest,
            natural_key=record.natural_key,
        )

    @classmethod
    def execute(
        cls,
        *,
        actor: ActorContext,
        operation: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
        natural_key: str,
        authorizer: OperationAuthorizer,
        handler: Callable[[Session, CommandClaim], DomainMutationResult],
        natural_key_resolver: OperationNaturalKeyResolver | None = None,
    ) -> CommandResult:
        authorizer = cls._require_authorizer(authorizer)
        digest = canonical_request_digest(payload)
        claim_or_result = cls.claim_or_reconcile(
            actor=actor,
            operation=operation,
            idempotency_key=idempotency_key,
            request_digest=digest,
            natural_key=natural_key,
            authorizer=authorizer,
        )
        if isinstance(claim_or_result, CommandResult):
            return claim_or_result
        try:
            return cls._execute_claim(
                actor=actor,
                operation=operation,
                claim=claim_or_result,
                handler=handler,
                natural_key_resolver=natural_key_resolver,
                authorizer=None,
            )
        except KnownPreCommitTransient as error:
            cls.mark_retryable(
                actor=actor,
                claim=claim_or_result,
                error_class=type(error).__name__,
            )
            raise
        except StaleClaim:
            raise
        except TransformationError as error:
            cls.mark_non_retryable(
                actor=actor,
                claim=claim_or_result,
                error_class=type(error).__name__,
            )
            raise
        except Exception:
            # The database outcome can be uncertain (for example a connection
            # loss while COMMIT is acknowledged). Leave the receipt claim for
            # result/natural-key reconciliation; never manufacture failure.
            raise

    @classmethod
    def execute_claim(
        cls,
        *,
        actor: ActorContext,
        operation: str,
        claim: CommandClaim,
        authorizer: OperationAuthorizer,
        handler: Callable[[Session, CommandClaim], DomainMutationResult],
        natural_key_resolver: OperationNaturalKeyResolver | None = None,
    ) -> CommandResult:
        authorizer = cls._require_authorizer(authorizer)
        return cls._execute_claim(
            actor=actor,
            operation=operation,
            claim=claim,
            authorizer=authorizer,
            handler=handler,
            natural_key_resolver=natural_key_resolver,
        )

    @classmethod
    def _execute_claim(
        cls,
        *,
        actor: ActorContext,
        operation: str,
        claim: CommandClaim,
        authorizer: OperationAuthorizer | None,
        handler: Callable[[Session, CommandClaim], DomainMutationResult],
        natural_key_resolver: OperationNaturalKeyResolver | None = None,
    ) -> CommandResult:
        command_result = None
        with Session(db.engine, expire_on_commit=False) as session, session.begin():
            if authorizer is not None:
                authorizer(session, actor, operation, claim.natural_key)
            # This preflight is intentionally non-locking. A handler may run for
            # minutes; heartbeat/reclaim must remain able to advance the lease.
            # The result/outbox/finalisation boundary takes the row lock below.
            cls.assert_fence(session, actor=actor, claim=claim, lock=False)
            mutation = (
                natural_key_resolver(session, actor, claim.natural_key, claim)
                if natural_key_resolver is not None
                else None
            )
            reconciled = mutation is not None
            if mutation is None:
                mutation = handler(session, claim)
            if not isinstance(mutation, DomainMutationResult):
                source = "natural-key resolver" if reconciled else "command handler"
                raise TypeError(f"{source} must return DomainMutationResult")
            cls.assert_fence(session, actor=actor, claim=claim)
            result = cls.insert_operation_result(
                session,
                actor=actor,
                operation=operation,
                claim=claim,
                mutation=mutation,
            )
            cls.finalise_succeeded(
                session,
                actor=actor,
                claim=claim,
                result_id=result.id,
            )
            command_result = cls.to_command_result(
                result, created=not reconciled, idempotent=reconciled
            )
        return command_result

    @classmethod
    def claim_or_reconcile(
        cls,
        *,
        actor: ActorContext,
        operation: str,
        idempotency_key: str,
        request_digest: str,
        natural_key: str,
        authorizer: OperationAuthorizer,
    ) -> CommandClaim | CommandResult:
        """Commit a first/reclaimed claim independently, reconciling effects first."""
        authorizer = cls._require_authorizer(authorizer)
        if not operation or not idempotency_key or not natural_key:
            raise ValueError("operation, idempotency_key and natural_key are required")
        if len(request_digest) != 64:
            raise ValueError("request_digest must be a SHA-256 hexadecimal digest")

        token = cls._new_claim_token()
        with Session(db.engine, expire_on_commit=False) as session, session.begin():
            # Authorization is mandatory and precedes both receipt creation and
            # immutable-result reconciliation. Resolvers never carry hidden auth.
            authorizer(session, actor, operation, natural_key)
            now = cls._database_now(session)
            expiry = now + timedelta(seconds=cls._lease_seconds())
            insert = (
                postgresql_insert(CommandIdempotencyRecord)
                .values(
                    organization_id=actor.organization_id,
                    actor_id=actor.user_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                    natural_key=natural_key,
                    status="in_progress",
                    lease_generation=1,
                    claim_token=token,
                    claimant_request_id=actor.request_id,
                    lease_expires_at=expiry,
                    attempt_count=1,
                )
                .on_conflict_do_nothing(
                    index_elements=(
                        CommandIdempotencyRecord.organization_id,
                        CommandIdempotencyRecord.actor_id,
                        CommandIdempotencyRecord.operation,
                        CommandIdempotencyRecord.idempotency_key,
                    )
                )
                .returning(CommandIdempotencyRecord.id)
            )
            inserted_id = session.scalar(insert)
            if inserted_id is not None:
                return CommandClaim(
                    receipt_id=inserted_id,
                    generation=1,
                    claim_token=token,
                    request_digest=request_digest,
                    natural_key=natural_key,
                )

            receipt = session.execute(
                select(CommandIdempotencyRecord)
                .where(
                    CommandIdempotencyRecord.organization_id
                    == actor.organization_id,
                    CommandIdempotencyRecord.actor_id == actor.user_id,
                    CommandIdempotencyRecord.operation == operation,
                    CommandIdempotencyRecord.idempotency_key == idempotency_key,
                )
                .with_for_update()
            ).scalar_one()
            # The upsert may have waited on a competing transaction. Refresh
            # database time after owning the row so a reclaimed lease cannot
            # already be expired when it is written.
            now = cls._database_now(session)
            expiry = now + timedelta(seconds=cls._lease_seconds())

            if receipt.request_digest != request_digest:
                raise CommandConflict(
                    "idempotency_digest_mismatch", receipt_id=receipt.id
                )
            if receipt.natural_key != natural_key:
                raise CommandConflict(
                    "idempotency_natural_key_mismatch", receipt_id=receipt.id
                )

            result = cls._find_result(
                session,
                organization_id=actor.organization_id,
                actor_id=actor.user_id,
                operation=operation,
                natural_key=natural_key,
            )
            if result is not None:
                if result.request_digest != request_digest:
                    raise CommandConflict(
                        "natural_key_digest_mismatch",
                        operation_result_id=result.id,
                    )
                if (
                    receipt.status != "succeeded"
                    or receipt.operation_result_id != result.id
                ):
                    receipt.status = "succeeded"
                    receipt.operation_result_id = result.id
                    receipt.lease_expires_at = None
                    receipt.completed_at = now
                    session.flush()
                return cls.to_command_result(
                    result, created=False, idempotent=True
                )
            result_owner = session.scalar(
                select(OperationResult.actor_id).where(
                    OperationResult.organization_id == actor.organization_id,
                    OperationResult.operation == operation,
                    OperationResult.natural_key == natural_key,
                )
            )
            if result_owner is not None:
                raise CommandConflict("natural_key_owned_by_another_actor")

            if receipt.status == "failed_non_retryable":
                raise CommandConflict(
                    "failed_non_retryable",
                    receipt_id=receipt.id,
                    error_class=receipt.last_error_class,
                )

            lease_active = (
                receipt.status == "in_progress"
                and receipt.lease_expires_at is not None
                and receipt.lease_expires_at > now
            )
            if lease_active:
                retry_after = max(
                    0.001, (receipt.lease_expires_at - now).total_seconds()
                )
                raise CommandConflict(
                    "active_lease",
                    receipt_id=receipt.id,
                    generation=receipt.lease_generation,
                    retry_after_seconds=retry_after,
                )

            receipt.status = "in_progress"
            receipt.lease_generation += 1
            receipt.claim_token = token
            receipt.claimant_request_id = actor.request_id
            receipt.lease_expires_at = expiry
            receipt.operation_result_id = None
            receipt.attempt_count += 1
            receipt.completed_at = None
            session.flush()
            return cls.claim_from_record(receipt)

    @staticmethod
    def _find_result(
        session: Session,
        *,
        organization_id: int,
        actor_id: int,
        operation: str,
        natural_key: str,
    ) -> OperationResult | None:
        return session.execute(
            select(OperationResult).where(
                OperationResult.organization_id == organization_id,
                OperationResult.actor_id == actor_id,
                OperationResult.operation == operation,
                OperationResult.natural_key == natural_key,
            )
        ).scalar_one_or_none()

    @classmethod
    def assert_fence(
        cls,
        session: Session,
        *,
        actor: ActorContext,
        claim: CommandClaim,
        lock: bool = True,
    ) -> CommandIdempotencyRecord:
        statement = select(CommandIdempotencyRecord).where(
                CommandIdempotencyRecord.id == claim.receipt_id,
                CommandIdempotencyRecord.organization_id
                == actor.organization_id,
                CommandIdempotencyRecord.actor_id == actor.user_id,
                CommandIdempotencyRecord.request_digest == claim.request_digest,
                CommandIdempotencyRecord.natural_key == claim.natural_key,
            )
        if lock:
            statement = statement.with_for_update()
        receipt = session.execute(statement).scalar_one_or_none()
        now = cls._database_now(session)
        if (
            receipt is None
            or receipt.status != "in_progress"
            or receipt.lease_generation != claim.generation
            or not secrets.compare_digest(receipt.claim_token, claim.claim_token)
            or receipt.lease_expires_at is None
            or receipt.lease_expires_at <= now
        ):
            raise StaleClaim("stale_or_expired_claim", receipt_id=claim.receipt_id)
        return receipt

    @classmethod
    def insert_operation_result(
        cls,
        session: Session,
        *,
        actor: ActorContext,
        operation: str,
        claim: CommandClaim,
        mutation: DomainMutationResult,
    ) -> OperationResult:
        result = OperationResult(
            organization_id=actor.organization_id,
            actor_id=actor.user_id,
            operation=operation,
            natural_key=claim.natural_key,
            request_digest=claim.request_digest,
            receipt_id=claim.receipt_id,
            receipt_generation=claim.generation,
            object_ids=copy.deepcopy(dict(mutation.object_ids)),
            response_json=copy.deepcopy(dict(mutation.response)),
        )
        session.add(result)
        session.flush()
        for ordinal, event in enumerate(mutation.outbox_events):
            event_type = event.get("event_type")
            payload = event.get("payload")
            if not event_type or not isinstance(payload, Mapping):
                raise ValueError("outbox events require event_type and payload")
            session.add(
                OperationOutboxEvent(
                    organization_id=actor.organization_id,
                    operation_result_id=result.id,
                    event_id=str(event.get("event_id") or uuid.uuid4()),
                    ordinal=ordinal,
                    event_type=str(event_type),
                    payload_json=copy.deepcopy(dict(payload)),
                )
            )
        session.flush()
        return result

    @classmethod
    def finalise_succeeded(
        cls,
        session: Session,
        *,
        actor: ActorContext,
        claim: CommandClaim,
        result_id: int,
    ) -> None:
        receipt = cls.assert_fence(session, actor=actor, claim=claim)
        result = session.execute(
            select(OperationResult).where(
                OperationResult.id == result_id,
                OperationResult.organization_id == actor.organization_id,
                OperationResult.operation == receipt.operation,
                OperationResult.natural_key == claim.natural_key,
                OperationResult.request_digest == claim.request_digest,
            )
        ).scalar_one_or_none()
        if result is None:
            raise StaleClaim("operation_result_outside_claim", receipt_id=claim.receipt_id)
        receipt.status = "succeeded"
        receipt.operation_result_id = result.id
        receipt.lease_expires_at = None
        receipt.completed_at = cls._database_now(session)
        session.flush()

    @classmethod
    def mark_retryable(
        cls,
        *,
        actor: ActorContext,
        claim: CommandClaim,
        error_class: str,
    ) -> bool:
        return cls._mark_failure(
            actor=actor,
            claim=claim,
            status="retryable_failure",
            error_class=error_class,
        )

    @classmethod
    def mark_non_retryable(
        cls,
        *,
        actor: ActorContext,
        claim: CommandClaim,
        error_class: str,
    ) -> bool:
        return cls._mark_failure(
            actor=actor,
            claim=claim,
            status="failed_non_retryable",
            error_class=error_class,
        )

    @classmethod
    def _mark_failure(
        cls,
        *,
        actor: ActorContext,
        claim: CommandClaim,
        status: str,
        error_class: str,
    ) -> bool:
        with Session(db.engine, expire_on_commit=False) as session, session.begin():
            receipt = session.execute(
                select(CommandIdempotencyRecord)
                .where(
                    CommandIdempotencyRecord.id == claim.receipt_id,
                    CommandIdempotencyRecord.organization_id
                    == actor.organization_id,
                    CommandIdempotencyRecord.actor_id == actor.user_id,
                    CommandIdempotencyRecord.request_digest == claim.request_digest,
                    CommandIdempotencyRecord.natural_key == claim.natural_key,
                )
                .with_for_update()
            ).scalar_one_or_none()
            if (
                receipt is None
                or receipt.status != "in_progress"
                or receipt.lease_generation != claim.generation
                or not secrets.compare_digest(receipt.claim_token, claim.claim_token)
                or receipt.operation_result_id is not None
            ):
                return False
            now = cls._database_now(session)
            receipt.status = status
            receipt.last_error_class = error_class
            receipt.lease_expires_at = now if status == "retryable_failure" else None
            receipt.completed_at = (
                None if status == "retryable_failure" else now
            )
            session.flush()
            return True

    @classmethod
    def heartbeat(
        cls, *, actor: ActorContext, claim: CommandClaim
    ) -> CommandClaim:
        with Session(db.engine, expire_on_commit=False) as session, session.begin():
            receipt = session.execute(
                select(CommandIdempotencyRecord)
                .where(
                    CommandIdempotencyRecord.id == claim.receipt_id,
                    CommandIdempotencyRecord.organization_id
                    == actor.organization_id,
                    CommandIdempotencyRecord.actor_id == actor.user_id,
                    CommandIdempotencyRecord.request_digest == claim.request_digest,
                    CommandIdempotencyRecord.natural_key == claim.natural_key,
                )
                .with_for_update()
            ).scalar_one_or_none()
            now = cls._database_now(session)
            if (
                receipt is None
                or receipt.status != "in_progress"
                or receipt.lease_generation != claim.generation
                or not secrets.compare_digest(receipt.claim_token, claim.claim_token)
                or receipt.lease_expires_at is None
                or receipt.lease_expires_at <= now
            ):
                raise StaleClaim("stale_or_expired_claim", receipt_id=claim.receipt_id)
            receipt.lease_expires_at = now + timedelta(seconds=cls._lease_seconds())
            session.flush()
            return cls.claim_from_record(receipt)

    @staticmethod
    def to_command_result(
        result: OperationResult, *, created: bool, idempotent: bool
    ) -> CommandResult:
        return CommandResult(
            created=created,
            idempotent=idempotent,
            operation_result_id=result.id,
            object_ids=copy.deepcopy(dict(result.object_ids)),
            response=copy.deepcopy(dict(result.response_json)),
        )


__all__ = [
    "CommandService",
    "OperationAuthorizer",
    "OperationNaturalKeyResolver",
    "canonical_request_digest",
]
