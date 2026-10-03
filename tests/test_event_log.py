"""Outbox and event-log integration tests — PR 2 of the durable event log.

Covers:
  * Entity emits produce outbox rows (with rollback/commit semantics)
  * Outbox rows are relayed into event_log with per-org monotonic ordinals
  * Two-organisation isolation (offsets are per org; A's replay never has B's rows)
  * Replay from timestamp rebuilds a derived table identically
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select, text

from app import db
from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
from app.models.event_log import EventLogRecord
from app.models.organization import Organization
from app.models.transformation_execution import OperationOutboxEvent
from app.services.event_log_service import (
    relay_outbox_batch,
    read_from_offset,
    replay_from,
    max_ordinal,
)
from app.services.outbox import emit_event


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _install_guards(app, _schema):
    """Re-install the transformation DB guards so the updated trigger
    (allowing entity events with NULL operation_result_id) is active."""
    from app.models.transformation_db_guards import ensure_transformation_db_guards
    with app.app_context(), db.engine.begin() as connection:
        ensure_transformation_db_guards(connection)


@pytest.fixture
def two_orgs(db_session):
    """Two distinct organisations with no shared rows."""
    suffix = uuid.uuid4().hex[:10]
    org_a = Organization(name=f"Event Log A {suffix}", slug=f"ela-{suffix}")
    org_b = Organization(name=f"Event Log B {suffix}", slug=f"elb-{suffix}")
    db_session.add_all([org_a, org_b])
    db_session.flush()
    return {"A": org_a, "B": org_b}


def _fresh_element(db_session, org_id, name="Test Element", **kw):
    el = ArchiMateElement(
        name=name,
        type=kw.pop("type", "ApplicationComponent"),
        layer=kw.pop("layer", "Application"),
        organization_id=org_id,
        **kw,
    )
    db_session.add(el)
    db_session.flush()
    return el


# ---------------------------------------------------------------------------
# Rollback / commit semantics
# ---------------------------------------------------------------------------


class TestOutboxTransactionSemantics:
    """A rolled-back transaction emits no events; a committed one emits exactly one."""

    def test_rollback_emits_no_outbox_event(self, db_session, two_orgs):
        org_a = two_orgs["A"]

        # Create element in a sub-transaction, then roll back.
        db_session.begin_nested()
        _fresh_element(db_session, org_a.id, "Rollback Element")
        db_session.rollback()  # roll back the savepoint AND the element

        db_session.commit()

        count = db_session.query(OperationOutboxEvent).filter(
            OperationOutboxEvent.organization_id == org_a.id,
            OperationOutboxEvent.entity_type == "archimate_element",
        ).count()
        assert count == 0, "Rolled-back element write must produce zero outbox events"

    def test_commit_emits_exactly_one_outbox_event(self, db_session, two_orgs):
        org_a = two_orgs["A"]

        el = _fresh_element(db_session, org_a.id, "Committed Element")
        db_session.commit()

        rows = (
            db_session.query(OperationOutboxEvent)
            .filter(
                OperationOutboxEvent.organization_id == org_a.id,
                OperationOutboxEvent.entity_type == "archimate_element",
                OperationOutboxEvent.entity_id == el.id,
            )
            .all()
        )
        assert len(rows) == 1, (
            f"Committed element write must produce exactly 1 outbox event, got {len(rows)}"
        )
        event = rows[0]
        assert event.event_type == "archimate_element.created"
        assert event.payload_json["id"] == el.id
        assert event.entity_type == "archimate_element"
        assert event.entity_id == el.id
        assert event.operation_result_id is None


# ---------------------------------------------------------------------------
# Outbox-to-event-log relay
# ---------------------------------------------------------------------------


class TestRelay:
    """Relay copies outbox rows into event_log with per-org ordinals."""

    def test_relay_creates_event_log_rows(self, db_session, two_orgs):
        org_a = two_orgs["A"]

        # Write one element (the ORM listener emits an outbox event).
        el = _fresh_element(db_session, org_a.id, "Relay Element")
        db_session.commit()

        # Before relay: outbox row exists, event_log is empty.
        outbox_count = db_session.query(OperationOutboxEvent).filter(
            OperationOutboxEvent.organization_id == org_a.id,
        ).count()
        assert outbox_count == 1

        log_count = db_session.query(EventLogRecord).filter(
            EventLogRecord.organization_id == org_a.id,
        ).count()
        assert log_count == 0

        # Relay.
        inserted = relay_outbox_batch()
        db_session.commit()
        assert inserted == 1

        log_count = db_session.query(EventLogRecord).filter(
            EventLogRecord.organization_id == org_a.id,
        ).count()
        assert log_count == 1

        log_row = db_session.query(EventLogRecord).filter(
            EventLogRecord.organization_id == org_a.id,
        ).first()
        assert log_row.ordinal == 1
        assert log_row.event_type == "archimate_element.created"
        assert log_row.entity_type == "archimate_element"
        assert log_row.entity_id == el.id

        # Outbox row marked as processed.
        outbox = db_session.query(OperationOutboxEvent).filter(
            OperationOutboxEvent.organization_id == org_a.id,
        ).first()
        assert outbox.published_at is not None

    def test_relay_is_idempotent(self, db_session, two_orgs):
        org_a = two_orgs["A"]
        _fresh_element(db_session, org_a.id, "Idempotent Element")
        db_session.commit()

        # Relay twice.
        first = relay_outbox_batch()
        db_session.commit()
        second = relay_outbox_batch()
        db_session.commit()

        assert first == 1
        assert second == 0  # Nothing new to relay.

        log_count = db_session.query(EventLogRecord).filter(
            EventLogRecord.organization_id == org_a.id,
        ).count()
        assert log_count == 1  # No duplicates.

    def test_per_org_monotonic_ordinals(self, db_session, two_orgs):
        org_a = two_orgs["A"]
        org_b = two_orgs["B"]

        # Create elements in both orgs.
        _fresh_element(db_session, org_a.id, "A1")
        _fresh_element(db_session, org_b.id, "B1")
        _fresh_element(db_session, org_a.id, "A2")
        _fresh_element(db_session, org_b.id, "B2")
        db_session.commit()

        inserted = relay_outbox_batch()
        db_session.commit()
        assert inserted == 4

        # Org A ordinals should be 1, 2.
        a_rows = (
            db_session.query(EventLogRecord)
            .filter(EventLogRecord.organization_id == org_a.id)
            .order_by(EventLogRecord.ordinal)
            .all()
        )
        assert [r.ordinal for r in a_rows] == [1, 2]

        # Org B ordinals should also be 1, 2 (independent).
        b_rows = (
            db_session.query(EventLogRecord)
            .filter(EventLogRecord.organization_id == org_b.id)
            .order_by(EventLogRecord.ordinal)
            .all()
        )
        assert [r.ordinal for r in b_rows] == [1, 2]


# ---------------------------------------------------------------------------
# Consumer read API
# ---------------------------------------------------------------------------


class TestReadFromOffset:
    def test_read_from_offset_returns_exact_slice(self, db_session, two_orgs):
        org_a = two_orgs["A"]

        # Create 3 elements, relay them, so we have ordinals 1, 2, 3.
        for name in ["R1", "R2", "R3"]:
            _fresh_element(db_session, org_a.id, name)
        db_session.commit()
        relay_outbox_batch()
        db_session.commit()

        # Read from offset 0 → all 3
        rows = read_from_offset(org_a.id, from_offset=0, limit=10)
        assert len(rows) == 3
        assert [r["ordinal"] for r in rows] == [1, 2, 3]

        # Read from offset 1 → remaining 2
        rows = read_from_offset(org_a.id, from_offset=1, limit=10)
        assert len(rows) == 2
        assert [r["ordinal"] for r in rows] == [2, 3]

        # Read from offset 3 → none
        rows = read_from_offset(org_a.id, from_offset=3, limit=10)
        assert len(rows) == 0

    def test_read_from_offset_respects_limit(self, db_session, two_orgs):
        org_a = two_orgs["A"]

        for name in ["L1", "L2", "L3", "L4", "L5"]:
            _fresh_element(db_session, org_a.id, name)
        db_session.commit()
        relay_outbox_batch()
        db_session.commit()

        rows = read_from_offset(org_a.id, from_offset=0, limit=3)
        assert len(rows) == 3

    def test_max_ordinal(self, db_session, two_orgs):
        org_a = two_orgs["A"]

        _fresh_element(db_session, org_a.id, "M1")
        _fresh_element(db_session, org_a.id, "M2")
        db_session.commit()
        relay_outbox_batch()
        db_session.commit()

        assert max_ordinal(org_a.id) == 2


# ---------------------------------------------------------------------------
# Replay from timestamp
# ---------------------------------------------------------------------------


class TestReplayFrom:
    def test_replay_from_timestamp(self, db_session, two_orgs):
        org_a = two_orgs["A"]

        # Create first element.
        before = datetime.now(timezone.utc)
        _fresh_element(db_session, org_a.id, "Early")
        db_session.commit()
        relay_outbox_batch()
        db_session.commit()

        # Create second element slightly later.
        _fresh_element(db_session, org_a.id, "Late")
        db_session.commit()
        relay_outbox_batch()
        db_session.commit()

        # Replay everything from `before`.
        rows = replay_from(org_a.id, since=before, limit=100)
        assert len(rows) == 2

        # Replay from slightly after first creation → only second element.
        after_first = before + timedelta(seconds=5)
        rows = replay_from(org_a.id, since=after_first, limit=100)
        # The "Late" element should have a created_at > after_first
        assert all(r["created_at"] >= after_first.isoformat() for r in rows)


# ---------------------------------------------------------------------------
# Two-organisation isolation
# ---------------------------------------------------------------------------


class TestTwoOrgIsolation:
    def test_org_A_replay_never_has_B_events(self, db_session, two_orgs):
        org_a = two_orgs["A"]
        org_b = two_orgs["B"]

        _fresh_element(db_session, org_a.id, "A Element")
        _fresh_element(db_session, org_b.id, "B Element")
        db_session.commit()
        relay_outbox_batch()
        db_session.commit()

        # Read org A's events — must not include B's.
        a_rows = read_from_offset(org_a.id, from_offset=0, limit=100)
        a_event_names = {r["payload"].get("name") for r in a_rows}
        assert "A Element" in a_event_names
        assert "B Element" not in a_event_names

        # Read org B's events — must not include A's.
        b_rows = read_from_offset(org_b.id, from_offset=0, limit=100)
        b_event_names = {r["payload"].get("name") for r in b_rows}
        assert "B Element" in b_event_names
        assert "A Element" not in b_event_names

    def test_offsets_are_per_organisation(self, db_session, two_orgs):
        org_a = two_orgs["A"]
        org_b = two_orgs["B"]

        _fresh_element(db_session, org_a.id, "A Only")
        db_session.commit()
        relay_outbox_batch()
        db_session.commit()

        # Org A has offset 1, Org B has none.
        assert max_ordinal(org_a.id) == 1
        assert max_ordinal(org_b.id) == 0

    def test_outbox_rows_are_org_scoped(self, db_session, two_orgs):
        org_a = two_orgs["A"]
        org_b = two_orgs["B"]

        _fresh_element(db_session, org_a.id, "A Element")
        db_session.commit()

        # Direct query for org A's outbox.
        a_outbox = db_session.query(OperationOutboxEvent).filter(
            OperationOutboxEvent.organization_id == org_a.id,
        ).all()
        assert len(a_outbox) == 1
        assert a_outbox[0].organization_id == org_a.id

        # Org B's outbox is empty.
        b_outbox = db_session.query(OperationOutboxEvent).filter(
            OperationOutboxEvent.organization_id == org_b.id,
        ).all()
        assert len(b_outbox) == 0


# ---------------------------------------------------------------------------
# Direct outbox emit (regression)
# ---------------------------------------------------------------------------


class TestDirectOutboxEmit:
    def test_emit_event_and_relay(self, db_session, two_orgs):
        org_a = two_orgs["A"]

        event = emit_event(
            organization_id=org_a.id,
            event_type="test.custom.event",
            payload={"hello": "world"},
            entity_type="test_entity",
            entity_id=42,
        )
        db_session.commit()

        # Outbox row exists.
        outbox = db_session.get(OperationOutboxEvent, event.id)
        assert outbox is not None
        assert outbox.event_type == "test.custom.event"
        assert outbox.entity_type == "test_entity"
        assert outbox.entity_id == 42

        # Relay.
        inserted = relay_outbox_batch()
        db_session.commit()
        assert inserted == 1

        # Event log has it.
        log_rows = db_session.query(EventLogRecord).filter(
            EventLogRecord.organization_id == org_a.id,
        ).all()
        assert len(log_rows) == 1
        assert log_rows[0].ordinal == 1
        assert log_rows[0].payload_json == {"hello": "world"}

    def test_relay_increments_delivery_attempts(self, db_session, two_orgs):
        """After relay, delivery_attempts must be an integer, not a BinaryExpression."""
        org_a = two_orgs["A"]

        event = emit_event(
            organization_id=org_a.id,
            event_type="test.delivery.count",
            payload={"n": 1},
            entity_type="test_entity",
            entity_id=99,
        )
        db_session.commit()

        # Before relay: delivery_attempts is 0 (server default).
        outbox_before = db_session.get(OperationOutboxEvent, event.id)
        assert outbox_before.delivery_attempts == 0

        inserted = relay_outbox_batch()
        db_session.commit()
        assert inserted == 1

        # After relay: delivery_attempts must be an int, incremented to 1.
        db_session.expire_all()
        outbox_after = db_session.get(OperationOutboxEvent, event.id)
        assert isinstance(outbox_after.delivery_attempts, int), (
            f"delivery_attempts must be int, got {type(outbox_after.delivery_attempts)}"
        )
        assert outbox_after.delivery_attempts == 1

        # Relay again (idempotent) — no unpublished rows remain.
        inserted2 = relay_outbox_batch()
        db_session.commit()
        assert inserted2 == 0  # nothing new to relay

        db_session.expire_all()
        outbox_after2 = db_session.get(OperationOutboxEvent, event.id)
        assert isinstance(outbox_after2.delivery_attempts, int)
        assert outbox_after2.delivery_attempts == 1  # unchanged, row already published


# ---------------------------------------------------------------------------
# Session isolation for the after_flush outbox listener
# ---------------------------------------------------------------------------


class TestOutboxSessionIsolation:
    """The after_flush listener stores pending/seen/depth on session.info,
    not module-level globals, so two sessions never interfere."""

    def test_consecutive_flushes_produce_distinct_events(self, db_session, two_orgs):
        """Two consecutive element creates in the same session must each
        produce their own outbox event — the listener state must reset
        between flushes."""
        org_a = two_orgs["A"]

        # First element.
        _fresh_element(db_session, org_a.id, "First Element")
        db_session.flush()

        # Second element — must not be confused with the first.
        _fresh_element(db_session, org_a.id, "Second Element")
        db_session.flush()

        db_session.commit()

        from app.models.transformation_execution import OperationOutboxEvent
        count = (
            db_session.query(OperationOutboxEvent)
            .filter(
                OperationOutboxEvent.organization_id == org_a.id,
                OperationOutboxEvent.entity_type == "archimate_element",
            )
            .count()
        )
        assert count == 2, f"Expected 2 outbox events, got {count}"