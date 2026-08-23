"""Fenced, reconcile-before-retry command execution for Transformation Room writes."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import math
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Mapping, TypeAlias

from flask import current_app
from sqlalchemy import func, select, text
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.dml import Delete, Insert, Update
from sqlalchemy.orm import Session

from app import db
from app.models.transformation_execution import (
    CommandMaterialisation,
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


def canonical_request_document(payload: Mapping[str, Any]) -> str:
    """Return the exact UTF-8 command document used at every hash boundary."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_canonical_json_default,
    )


def canonical_request_digest(payload: Mapping[str, Any]) -> str:
    """Return SHA-256 over the exact canonical request document."""
    return hashlib.sha256(canonical_request_document(payload).encode("utf-8")).hexdigest()


OperationNaturalKeyResolver: TypeAlias = Callable[
    [Session, ActorContext, str, CommandClaim], DomainMutationResult | None
]
OperationAuthorizer: TypeAlias = Callable[
    [Session, ActorContext, str, str], None
]


class _FencedSession(Session):
    """Acquire the locked command fence lazily, immediately before first write."""

    _fence_actor: ActorContext | None = None
    _fence_claim: CommandClaim | None = None
    _fence_locked = False
    _fence_checking = False

    def configure_fence(self, actor: ActorContext, claim: CommandClaim) -> None:
        self._fence_actor = actor
        self._fence_claim = claim

    def _ensure_locked_fence(self) -> None:
        if self._fence_locked or self._fence_checking:
            return
        if self._fence_actor is None or self._fence_claim is None:
            return
        self._fence_checking = True
        try:
            # The fence SELECT must not autoflush the pending domain row whose
            # write it is intended to authorize.
            with self.no_autoflush:
                CommandService.assert_fence(
                    self,
                    actor=self._fence_actor,
                    claim=self._fence_claim,
                    lock=True,
                )
            self._fence_locked = True
        finally:
            self._fence_checking = False

    @staticmethod
    def _mutates(statement: Any) -> bool:
        if isinstance(statement, (Insert, Update, Delete)):
            return True
        if not isinstance(statement, TextClause):
            return False
        sql = statement.text.lstrip().lower()
        if sql.startswith(("insert ", "update ", "delete ", "merge ", "call ")):
            return True
        return any(
            function_name in sql
            for function_name in (
                "archie_advance_evidence_head(",
                "archie_create_decision_brief(",
                "archie_freeze_decision_brief_version(",
            )
        )

    def execute(self, statement, params=None, *, execution_options=None, bind_arguments=None, **kw):
        if self._mutates(statement):
            self._ensure_locked_fence()
        return super().execute(
            statement,
            params,
            execution_options=execution_options or {},
            bind_arguments=bind_arguments,
            **kw,
        )

    def flush(self, objects=None):
        if self.new or self.dirty or self.deleted:
            self._ensure_locked_fence()
        return super().flush(objects)


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
        return value.astimezone(timezone.utc)

    @staticmethod
    def _new_claim_token() -> str:
        return secrets.token_hex(32)

    @staticmethod
    def _capability_secret() -> tuple[str, bytes]:
        encoded = str(
            current_app.config.get("TRANSFORMATION_COMMAND_CAPABILITY_SECRET", "")
            or ""
        ).strip()
        try:
            secret = bytes.fromhex(encoded)
        except ValueError as error:
            raise RuntimeError(
                "TRANSFORMATION_COMMAND_CAPABILITY_SECRET must be hexadecimal"
            ) from error
        if len(secret) < 32:
            raise RuntimeError(
                "TRANSFORMATION_COMMAND_CAPABILITY_SECRET must contain at least 32 bytes"
            )
        return hashlib.sha256(secret).hexdigest(), secret

    @classmethod
    def _signed_capability(cls, payload: Mapping[str, Any]) -> tuple[str, str]:
        key_id, secret = cls._capability_secret()
        document = canonical_request_document({**dict(payload), "key_id": key_id})
        capability = hmac.new(secret, document.encode("utf-8"), hashlib.sha256).hexdigest()
        return document, capability

    @classmethod
    def _execution_capability(
        cls,
        *,
        actor: ActorContext,
        operation: str,
        idempotency_key: str,
        request_digest: str,
        natural_key: str,
        receipt_id: int,
        generation: int,
        claim_token: str,
        claimant_request_id: str,
    ) -> tuple[str, str]:
        return cls._signed_capability(
            {
                "schema_version": "transformation-command-execution-r1",
                "organization_id": actor.organization_id,
                "actor_id": actor.user_id,
                "operation": operation,
                "idempotency_key": idempotency_key,
                "request_digest": request_digest,
                "natural_key": natural_key,
                "receipt_id": receipt_id,
                "generation": generation,
                "claim_token": claim_token,
                "claimant_request_id": claimant_request_id,
            }
        )

    @staticmethod
    def _require_authorizer(authorizer: OperationAuthorizer) -> OperationAuthorizer:
        if not callable(authorizer):
            raise TypeError("authorizer must be callable")
        return authorizer

    @classmethod
    def claim_from_record(cls, record: CommandIdempotencyRecord) -> CommandClaim:
        actor = ActorContext(
            user_id=record.actor_id,
            organization_id=record.organization_id,
            roles=frozenset(),
            request_id=record.claimant_request_id,
        )
        capability_document, capability_mac = cls._execution_capability(
            actor=actor,
            operation=record.operation,
            idempotency_key=record.idempotency_key,
            request_digest=record.request_digest,
            natural_key=record.natural_key,
            receipt_id=record.id,
            generation=record.lease_generation,
            claim_token=record.claim_token,
            claimant_request_id=record.claimant_request_id,
        )
        return CommandClaim(
            receipt_id=record.id,
            generation=record.lease_generation,
            claim_token=record.claim_token,
            request_digest=record.request_digest,
            natural_key=record.natural_key,
            capability_document=capability_document,
            capability_mac=capability_mac,
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
        with _FencedSession(db.engine, expire_on_commit=False) as session, session.begin():
            session.configure_fence(actor, claim)
            if authorizer is not None:
                authorizer(session, actor, operation, claim.natural_key)
            # This preflight is intentionally non-locking. A handler may run for
            # minutes; heartbeat/reclaim must remain able to advance the lease.
            # The result/outbox/finalisation boundary takes the row lock below.
            cls.assert_fence(session, actor=actor, claim=claim, lock=False)
            mutation = cls.resolve_materialisation(
                session,
                actor=actor,
                operation=operation,
                claim=claim,
            )
            recovered_from_materialisation = mutation is not None
            if mutation is None and natural_key_resolver is not None:
                mutation = natural_key_resolver(
                    session, actor, claim.natural_key, claim
                )
            reconciled = mutation is not None
            if mutation is None:
                mutation = handler(session, claim)
            if not isinstance(mutation, DomainMutationResult):
                source = "natural-key resolver" if reconciled else "command handler"
                raise TypeError(f"{source} must return DomainMutationResult")
            # Backfill legacy natural-key recoveries as well as new handler
            # effects. Once observed, every exact effect has the same immutable
            # recovery contract even if it predates this additive table.
            if not recovered_from_materialisation:
                cls.persist_materialisation(
                    session,
                    actor=actor,
                    operation=operation,
                    claim=claim,
                    mutation=mutation,
                )
            session._ensure_locked_fence()
            result = (
                cls.existing_operation_result(
                    session,
                    actor=actor,
                    operation=operation,
                    claim=claim,
                    mutation=mutation,
                )
                if reconciled
                else None
            )
            created = result is None
            if result is None:
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
                result,
                created=created and not reconciled,
                idempotent=reconciled,
            )
        return command_result

    @classmethod
    def resolve_materialisation(
        cls,
        session: Session,
        *,
        actor: ActorContext,
        operation: str,
        claim: CommandClaim,
    ) -> DomainMutationResult | None:
        """Strictly recover only the exact actor/operation/payload materialisation."""
        row = session.scalar(
            select(CommandMaterialisation).where(
                CommandMaterialisation.organization_id == actor.organization_id,
                CommandMaterialisation.operation == operation,
                CommandMaterialisation.natural_key == claim.natural_key,
            )
        )
        if row is None:
            return None
        if row.actor_id != actor.user_id:
            raise CommandConflict("natural_key_owned_by_another_actor")
        if row.request_digest != claim.request_digest:
            raise CommandConflict("natural_key_payload_conflict")
        events = tuple(copy.deepcopy(row.outbox_events or ()))
        return DomainMutationResult(
            object_ids=copy.deepcopy(dict(row.object_ids)),
            response=copy.deepcopy(dict(row.response_json)),
            outbox_events=events,
        )

    @classmethod
    def persist_materialisation(
        cls,
        session: Session,
        *,
        actor: ActorContext,
        operation: str,
        claim: CommandClaim,
        mutation: DomainMutationResult,
    ) -> CommandMaterialisation:
        row = CommandMaterialisation(
            organization_id=actor.organization_id,
            actor_id=actor.user_id,
            operation=operation,
            natural_key=claim.natural_key,
            request_digest=claim.request_digest,
            receipt_id=claim.receipt_id,
            receipt_generation=claim.generation,
            object_ids=copy.deepcopy(dict(mutation.object_ids)),
            response_json=copy.deepcopy(dict(mutation.response)),
            outbox_events=copy.deepcopy(list(mutation.outbox_events)),
        )
        session.add(row)
        session.flush()
        return row

    @classmethod
    def existing_operation_result(
        cls,
        session: Session,
        *,
        actor: ActorContext,
        operation: str,
        claim: CommandClaim,
        mutation: DomainMutationResult,
    ) -> OperationResult | None:
        """Return only the intact result for this exact recovered materialisation."""
        result = session.scalar(
            select(OperationResult).where(
                OperationResult.organization_id == actor.organization_id,
                OperationResult.operation == operation,
                OperationResult.natural_key == claim.natural_key,
            )
        )
        if result is None:
            return None
        if result.actor_id != actor.user_id:
            raise CommandConflict("natural_key_owned_by_another_actor")
        if result.request_digest != claim.request_digest:
            raise CommandConflict("natural_key_payload_conflict")
        if (
            dict(result.object_ids) != dict(mutation.object_ids)
            or dict(result.response_json) != dict(mutation.response)
        ):
            raise CommandConflict("operation_result_materialisation_mismatch")
        return result

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
        lease_milliseconds = max(10, math.ceil(cls._lease_seconds() * 1000.0))
        claim_document, claim_capability = cls._signed_capability(
            {
                "schema_version": "transformation-command-claim-r1",
                "organization_id": actor.organization_id,
                "actor_id": actor.user_id,
                "operation": operation,
                "idempotency_key": idempotency_key,
                "request_digest": request_digest,
                "natural_key": natural_key,
                "claim_token": token,
                "claimant_request_id": actor.request_id,
                "lease_milliseconds": lease_milliseconds,
            }
        )
        with Session(db.engine, expire_on_commit=False) as session, session.begin():
            # Authorization is mandatory and precedes both receipt creation and
            # immutable-result reconciliation. Resolvers never carry hidden auth.
            authorizer(session, actor, operation, natural_key)
            schema = session.scalar(text("SELECT current_schema()"))
            quoted_schema = session.bind.dialect.identifier_preparer.quote(schema)
            row = session.execute(
                text(
                    f"SELECT * FROM {quoted_schema}.archie_claim_transformation_command("
                    "CAST(:document AS text), CAST(:capability AS text))"
                ),
                {"document": claim_document, "capability": claim_capability},
            ).mappings().one()
            if row["claim_outcome"] == "reconciled":
                result = session.scalar(
                    select(OperationResult).where(
                        OperationResult.id == row["operation_result_id"],
                        OperationResult.organization_id == actor.organization_id,
                        OperationResult.actor_id == actor.user_id,
                        OperationResult.operation == operation,
                        OperationResult.natural_key == natural_key,
                    )
                )
                if result is None:
                    raise CommandConflict("operation_result_missing_after_reconcile")
                return cls.to_command_result(result, created=False, idempotent=True)
            if row["claim_outcome"] == "conflict":
                details = {"receipt_id": row["command_receipt_id"]}
                if row["conflict_error_class"] is not None:
                    details["error_class"] = row["conflict_error_class"]
                if row["retry_after_seconds"] is not None:
                    details["generation"] = row["command_generation"]
                    details["retry_after_seconds"] = row["retry_after_seconds"]
                if row["operation_result_id"] is not None:
                    details["operation_result_id"] = row["operation_result_id"]
                raise CommandConflict(row["conflict_reason"], **details)
            if row["claim_outcome"] != "claimed":
                raise RuntimeError("command claim function returned an unknown outcome")
            capability_document, capability_mac = cls._execution_capability(
                actor=actor,
                operation=operation,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                natural_key=natural_key,
                receipt_id=row["command_receipt_id"],
                generation=row["command_generation"],
                claim_token=row["command_claim_token"],
                claimant_request_id=actor.request_id,
            )
            return CommandClaim(
                receipt_id=row["command_receipt_id"],
                generation=row["command_generation"],
                claim_token=row["command_claim_token"],
                request_digest=request_digest,
                natural_key=natural_key,
                capability_document=capability_document,
                capability_mac=capability_mac,
            )

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
    "canonical_request_document",
    "canonical_request_digest",
]
