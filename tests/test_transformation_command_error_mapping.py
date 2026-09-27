"""Focused command-envelope database error classification."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import DBAPIError

from app.modules.transformation_room.command_service import CommandService
from app.modules.transformation_room.domain import (
    ActorContext,
    CommandClaim,
    CommandConflict,
    DomainMutationResult,
)


class _IdentifierPreparer:
    @staticmethod
    def quote(identifier):
        return identifier


class _Dialect:
    identifier_preparer = _IdentifierPreparer()


class _Bind:
    dialect = _Dialect()


class _FailingEnvelopeSession:
    bind = _Bind()

    def __init__(self, error):
        self._error = error
        self._calls = 0

    def scalar(self, _statement, _parameters=None):
        self._calls += 1
        if self._calls == 1:
            return "public"
        raise self._error


def _persist_with_database_error(message):
    database_error = DBAPIError(
        "SELECT archie_persist_command_envelope(...) ",
        {},
        RuntimeError(message),
        False,
    )
    session = _FailingEnvelopeSession(database_error)
    actor = ActorContext(1, 1, frozenset(), "request-1")
    claim = CommandClaim(1, 1, "token", "d" * 64, "natural-key", "document", "mac")
    mutation = DomainMutationResult({}, {}, ())
    return database_error, lambda: CommandService.persist_command_envelope(
        session,
        actor=actor,
        operation="evidence.observe",
        claim=claim,
        mutation=mutation,
    )


def test_persist_translates_materialisation_identity_mismatch_to_command_conflict():
    """Catches PostgreSQL identity conflicts escaping as raw DBAPI errors."""
    _database_error, persist = _persist_with_database_error(
        "command materialisation identity mismatch"
    )

    with pytest.raises(CommandConflict) as raised:
        persist()

    assert raised.value.reason == "operation_result_materialisation_mismatch"


def test_persist_does_not_translate_unrelated_database_errors():
    """Catches broad conflict matching that hides unrelated database failures."""
    database_error, persist = _persist_with_database_error(
        "connection terminated during command persistence"
    )

    with pytest.raises(DBAPIError) as raised:
        persist()

    assert raised.value is database_error
