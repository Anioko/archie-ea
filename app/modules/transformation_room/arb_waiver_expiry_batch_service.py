"""Bounded automatic expiry of typed ARB condition waivers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Iterator, Mapping, Sequence

from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import db
from app.models.arb_decision_event import ARBCondition
from app.modules.transformation_room.arb_condition_lifecycle_service import (
    TypedARBConditionLifecycleService,
)


@dataclass(frozen=True)
class WaiverExpiryCandidate:
    organization_id: int
    condition_id: int
    revision: int


@dataclass(frozen=True)
class WaiverExpiryBatchResult:
    lock_acquired: bool
    organization_ids: tuple[int, ...]
    batch_size: int
    selected_count: int
    expired_count: int
    replayed_count: int
    failed_count: int
    errors: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["organization_ids"] = list(self.organization_ids)
        value["errors"] = [dict(error) for error in self.errors]
        return value


class ARBWaiverExpiryBatchService:
    """Select due waivers and dispatch the existing fenced expiry command."""

    MAX_BATCH_SIZE = 1000
    DEFAULT_BATCH_SIZE = 100
    _LOCK_NAME = "typed-arb-condition-waiver-expiry-r1"

    @classmethod
    def run(
        cls, *, organization_ids: Sequence[int], batch_size: int = DEFAULT_BATCH_SIZE
    ) -> WaiverExpiryBatchResult:
        tenant_ids = cls._normalize_organization_ids(organization_ids)
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or not (
            1 <= batch_size <= cls.MAX_BATCH_SIZE
        ):
            raise ValueError(
                f"batch_size must be between 1 and {cls.MAX_BATCH_SIZE}"
            )
        capability = str(
            current_app.config.get("ARB_CONDITION_EXPIRY_CAPABILITY", "") or ""
        )
        if not capability:
            raise RuntimeError("ARB_CONDITION_EXPIRY_CAPABILITY is required")

        with cls._advisory_lock() as acquired:
            if not acquired:
                return cls._empty_result(tenant_ids, batch_size, lock_acquired=False)
            candidates = cls._select_due(tenant_ids, batch_size)
            return cls._process_candidates(
                candidates=candidates,
                organization_ids=tenant_ids,
                batch_size=batch_size,
                capability=capability,
            )

    @classmethod
    def run_configured(cls) -> WaiverExpiryBatchResult:
        return cls.run(
            organization_ids=cls.configured_organization_ids(),
            batch_size=cls.configured_batch_size(),
        )

    @staticmethod
    def configured_organization_ids() -> tuple[int, ...]:
        raw = current_app.config.get("ARB_CONDITION_EXPIRY_ORGANIZATION_IDS", ())
        if isinstance(raw, str):
            try:
                raw = tuple(
                    int(part.strip()) for part in raw.split(",") if part.strip()
                )
            except ValueError as error:
                raise ValueError(
                    "ARB_CONDITION_EXPIRY_ORGANIZATION_IDS must be comma-separated integers"
                ) from error
        return ARBWaiverExpiryBatchService._normalize_organization_ids(raw)

    @classmethod
    def configured_batch_size(cls) -> int:
        raw = current_app.config.get(
            "ARB_CONDITION_EXPIRY_BATCH_SIZE", cls.DEFAULT_BATCH_SIZE
        )
        try:
            return int(raw)
        except (TypeError, ValueError) as error:
            raise ValueError("ARB_CONDITION_EXPIRY_BATCH_SIZE must be an integer") from error

    @staticmethod
    def _normalize_organization_ids(organization_ids: Iterable[int]) -> tuple[int, ...]:
        if isinstance(organization_ids, (str, bytes)):
            raise ValueError("organization_ids are required")
        organization_ids = tuple(organization_ids)
        if not organization_ids:
            raise ValueError("organization_ids are required")
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in organization_ids
        ):
            raise ValueError("organization_ids must contain positive integers")
        return tuple(sorted(set(organization_ids)))

    @classmethod
    @contextmanager
    def _advisory_lock(cls) -> Iterator[bool]:
        with db.engine.connect() as connection:
            lock_key = connection.scalar(
                select(
                    func.hashtextextended(
                        func.concat(func.current_schema(), f":{cls._LOCK_NAME}"), 0
                    )
                )
            )
            acquired = bool(
                connection.scalar(select(func.pg_try_advisory_lock(lock_key)))
            )
            try:
                yield acquired
            finally:
                if acquired:
                    connection.scalar(select(func.pg_advisory_unlock(lock_key)))

    @staticmethod
    def _select_due(
        organization_ids: tuple[int, ...], batch_size: int
    ) -> tuple[WaiverExpiryCandidate, ...]:
        statement = (
            select(
                ARBCondition.organization_id,
                ARBCondition.id,
                ARBCondition.revision,
            )
            .where(
                ARBCondition.organization_id.in_(organization_ids),
                ARBCondition.status == "waived",
                ARBCondition.waiver_expires_at.is_not(None),
                ARBCondition.waiver_expires_at <= func.clock_timestamp(),
            )
            .order_by(
                ARBCondition.waiver_expires_at,
                ARBCondition.organization_id,
                ARBCondition.id,
            )
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        with Session(db.engine) as session, session.begin():
            rows = session.execute(statement).all()
        return tuple(
            WaiverExpiryCandidate(
                organization_id=row.organization_id,
                condition_id=row.id,
                revision=row.revision,
            )
            for row in rows
        )

    @classmethod
    def _process_candidates(
        cls,
        *,
        candidates: Sequence[WaiverExpiryCandidate],
        organization_ids: tuple[int, ...],
        batch_size: int,
        capability: str,
    ) -> WaiverExpiryBatchResult:
        expired_count = 0
        replayed_count = 0
        errors = []
        for candidate in candidates:
            target_revision = candidate.revision + 1
            command_key = (
                f"arb-waiver-expiry:{candidate.organization_id}:"
                f"{candidate.condition_id}:{target_revision}"
            )
            try:
                result = TypedARBConditionLifecycleService.expire_waivers(
                    capability=capability,
                    command_key=command_key,
                    condition_id=candidate.condition_id,
                    organization_id=candidate.organization_id,
                )
                if result.created:
                    expired_count += 1
                else:
                    replayed_count += 1
            except Exception as error:  # each command owns its transaction
                reason = getattr(error, "reason", None) or str(error)
                errors.append(
                    {
                        "organization_id": candidate.organization_id,
                        "condition_id": candidate.condition_id,
                        "condition_revision": candidate.revision,
                        "error_type": type(error).__name__,
                        "reason": reason,
                    }
                )
            finally:
                # End the preload transaction between commands without
                # discarding caller-owned Session.info (the integration cleanup
                # registry and similar operational context live there).
                db.session.rollback()
        return WaiverExpiryBatchResult(
            lock_acquired=True,
            organization_ids=organization_ids,
            batch_size=batch_size,
            selected_count=len(candidates),
            expired_count=expired_count,
            replayed_count=replayed_count,
            failed_count=len(errors),
            errors=tuple(errors),
        )

    @staticmethod
    def _empty_result(
        organization_ids: tuple[int, ...], batch_size: int, *, lock_acquired: bool
    ) -> WaiverExpiryBatchResult:
        return WaiverExpiryBatchResult(
            lock_acquired=lock_acquired,
            organization_ids=organization_ids,
            batch_size=batch_size,
            selected_count=0,
            expired_count=0,
            replayed_count=0,
            failed_count=0,
            errors=(),
        )


__all__ = [
    "ARBWaiverExpiryBatchService",
    "WaiverExpiryBatchResult",
    "WaiverExpiryCandidate",
]
