"""HTML transport for the typed ARB condition child routes.

`typed-arb-ui-blueprint.md` §11 requires HTML child routes at
``POST /arb/reviews/<review_item_id>/conditions/<condition_id>/{evidence,verify,waive}``
alongside the canonical JSON ingress, each proving exact membership and
answering a success with a **303** to the condition's anchor.

Before those routes existed the typed condition forms posted straight at
``/arb/api/conditions/...``, so a native submit with JavaScript off sent a
form-encoded body to a JSON handler and rendered a raw error payload. These
tests pin the transport, the membership proof and the failure behaviour.

Fixture note
------------
The seeding helpers and the committed-setup ``db_session`` override are imported
from ``tests/test_typed_arb_condition_routes.py`` rather than copied: the typed
command services open their own database sessions, and one graph builder for
both transports is the point — a divergence between them would be exactly the
bug this module exists to prevent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

import pytest

from tests.test_typed_arb_condition_routes import (  # noqa: F401  (fixture import)
    _install_guards,
    _seed,
    db_session,
)


def _now():
    return datetime.now(timezone.utc)


def _local(moment):
    """What a ``datetime-local`` control actually submits: a naive string."""
    return moment.strftime("%Y-%m-%dT%H:%M")


def _evidence_url(review_item_id, condition_id):
    return f"/arb/reviews/{review_item_id}/conditions/{condition_id}/evidence"


def _verify_url(review_item_id, condition_id):
    return f"/arb/reviews/{review_item_id}/conditions/{condition_id}/verify"


def _waive_url(review_item_id, condition_id):
    return f"/arb/reviews/{review_item_id}/conditions/{condition_id}/waive"


def _anchor(condition_id):
    return f"#condition-{condition_id}"


def _attestation_form():
    return {
        "mode": "manual_attestation",
        "statement": "The control was executed and witnessed.",
        "observed_at": _local(_now() - timedelta(minutes=5)),
    }


def _waiver_form(**overrides):
    form = {
        "reason": "Time-bound risk acceptance pending the platform upgrade.",
        "expires_at": _local(_now() + timedelta(days=30)),
        "scope": "The reporting service only.",
        "compensating_control": "Daily manual reconciliation by the duty architect.",
    }
    form.update(overrides)
    return form


# ── registration ─────────────────────────────────────────────────────────────


def test_html_condition_child_routes_are_registered(app):
    """Blueprints register non-fatally, so read the real url_map, not the log."""
    rules = {rule.rule: (rule.endpoint, rule.methods) for rule in app.url_map.iter_rules()}
    for suffix, endpoint in (
        ("evidence", "arb_conditions_html.submit_condition_evidence"),
        ("verify", "arb_conditions_html.verify_condition_evidence"),
        ("waive", "arb_conditions_html.waive_condition"),
    ):
        rule = (
            "/arb/reviews/<int:review_item_id>/conditions/<int:condition_id>/"
            + suffix
        )
        assert rule in rules, f"{rule} is not registered"
        assert rules[rule][0] == endpoint
        assert "POST" in rules[rule][1]
        assert "GET" not in rules[rule][1]


def test_html_condition_child_routes_are_not_csrf_exempt(app):
    from app._bootstrap.csrf_coverage import audit

    exempt = {
        finding.endpoint
        for finding in audit(app)
        if getattr(finding, "exempt", False)
    }
    assert not {
        endpoint
        for endpoint in exempt
        if endpoint.startswith("arb_conditions_html.")
    }


# ── happy path across all three commands ─────────────────────────────────────


def test_evidence_verify_and_waive_over_the_html_transport(
    app, db_session, make_org, client, login_as
):
    """One 303-per-command journey, ending at the right anchor each time."""
    from app.models.arb_decision_event import ARBCondition

    _install_guards(db_session)
    seeded = _seed(db_session, make_org, "html-happy", conditions=2)
    fulfil_id, waive_id = seeded.condition_ids[0], seeded.condition_ids[1]

    # Capture + submit are two commands behind one form (§9).
    login_as(client, seeded.submitter_id)
    submitted = client.post(
        _evidence_url(seeded.review_item_id, fulfil_id),
        data=_attestation_form(),
    )
    assert submitted.status_code == 303
    assert submitted.headers["Location"].endswith(_anchor(fulfil_id))
    db_session.expire_all()
    condition = db_session.get(ARBCondition, fulfil_id)
    assert condition.status == "evidence_submitted"

    # The verify form carries the evidence id in the body; the route proves it.
    from app.models.arb_condition_evidence import ARBConditionEvidenceRecord
    from sqlalchemy import select

    evidence_id = db_session.execute(
        select(ARBConditionEvidenceRecord.id).where(
            ARBConditionEvidenceRecord.condition_id == fulfil_id,
            ARBConditionEvidenceRecord.organization_id == seeded.org_id,
        )
    ).scalar_one()

    login_as(client, seeded.authority_id)
    verified = client.post(
        _verify_url(seeded.review_item_id, fulfil_id),
        data={"condition_evidence_id": str(evidence_id)},
    )
    assert verified.status_code == 303
    assert verified.headers["Location"].endswith(_anchor(fulfil_id))
    db_session.expire_all()
    assert db_session.get(ARBCondition, fulfil_id).status == "fulfilled"

    login_as(client, seeded.authority_id)
    waived = client.post(
        _waive_url(seeded.review_item_id, waive_id), data=_waiver_form()
    )
    assert waived.status_code == 303
    assert waived.headers["Location"].endswith(_anchor(waive_id))
    db_session.expire_all()
    assert db_session.get(ARBCondition, waive_id).status == "waived"


def test_a_naive_datetime_local_value_is_read_as_utc(
    app, db_session, make_org, client, login_as
):
    """The form states the interpretation; the server must actually apply it.

    A naive value silently shifted by the server's own zone would record an
    observation at a time nobody asserted.
    """
    from app.models.arb_condition_evidence import ARBConditionEvidenceRecord
    from sqlalchemy import select

    _install_guards(db_session)
    seeded = _seed(db_session, make_org, "html-utc", conditions=1)
    condition_id = seeded.condition_ids[0]
    observed = (_now() - timedelta(hours=3)).replace(second=0, microsecond=0)

    login_as(client, seeded.submitter_id)
    response = client.post(
        _evidence_url(seeded.review_item_id, condition_id),
        data=_attestation_form() | {"observed_at": _local(observed)},
    )
    assert response.status_code == 303

    db_session.expire_all()
    record = db_session.execute(
        select(ARBConditionEvidenceRecord).where(
            ARBConditionEvidenceRecord.condition_id == condition_id,
            ARBConditionEvidenceRecord.organization_id == seeded.org_id,
        )
    ).scalar_one()
    stored = record.observed_at
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored.astimezone(timezone.utc) == observed.astimezone(timezone.utc)


# ── membership and tenancy ───────────────────────────────────────────────────


def test_a_condition_reached_through_the_wrong_review_is_404(
    app, db_session, make_org, client, login_as
):
    """Same tenant, real condition, wrong review in the path: indistinguishable 404."""
    _install_guards(db_session)
    seeded = _seed(db_session, make_org, "html-membership", conditions=1)

    login_as(client, seeded.submitter_id)
    response = client.post(
        _evidence_url(seeded.review_item_id + 9999, seeded.condition_ids[0]),
        data=_attestation_form(),
    )
    assert response.status_code == 404


def test_another_tenants_condition_is_404_over_the_html_transport(
    app, db_session, make_org, client, login_as
):
    _install_guards(db_session)
    owner = _seed(db_session, make_org, "html-owner", conditions=1)
    intruder = _seed(db_session, make_org, "html-intruder", conditions=1)

    login_as(client, intruder.submitter_id)
    response = client.post(
        _evidence_url(owner.review_item_id, owner.condition_ids[0]),
        data=_attestation_form(),
    )
    assert response.status_code == 404

    # Nothing was written into the other tenant's graph. Read it back on a raw
    # connection: the ORM session carries the tenant filter that the request just
    # exercised, so asking it whether the *other* tenant's row moved would be
    # asking the mechanism under test to grade itself.
    from app import db

    raw = db.engine.raw_connection()
    try:
        with raw.cursor() as cursor:
            cursor.execute(
                "SELECT status FROM arb_canonical_conditions "
                "WHERE id = %s AND organization_id = %s",
                (owner.condition_ids[0], owner.org_id),
            )
            row = cursor.fetchone()
    finally:
        raw.close()
    assert row is not None, "the owning tenant's condition disappeared"
    assert row[0] == "pending"


def test_unauthenticated_html_post_does_not_reach_the_command(
    app, db_session, make_org, client
):
    from app.models.arb_decision_event import ARBCondition

    _install_guards(db_session)
    seeded = _seed(db_session, make_org, "html-anon", conditions=1)

    response = client.post(
        _evidence_url(seeded.review_item_id, seeded.condition_ids[0]),
        data=_attestation_form(),
    )
    assert response.status_code in (302, 303, 401)
    db_session.expire_all()
    assert db_session.get(ARBCondition, seeded.condition_ids[0]).status == "pending"


# ── validation, retention and separation of duties ───────────────────────────


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"reason": "   "}, 400),
        ({"scope": ""}, 400),
        ({"compensating_control": ""}, 400),
        ({"expires_at": ""}, 400),
        # Bounds are §9 rules, checked ahead of the command so nothing is written.
        (
            {"expires_at": _local(datetime.now(timezone.utc) - timedelta(days=1))},
            422,
        ),
        (
            {"expires_at": _local(datetime.now(timezone.utc) + timedelta(days=400))},
            422,
        ),
    ],
)
def test_a_rejected_waiver_writes_nothing_and_keeps_the_operator_text(
    app, db_session, make_org, client, login_as, overrides, expected
):
    from app.models.arb_decision_event import ARBCondition

    _install_guards(db_session)
    seeded = _seed(db_session, make_org, "html-waiver-reject", conditions=1)
    condition_id = seeded.condition_ids[0]

    login_as(client, seeded.authority_id)
    response = client.post(
        _waive_url(seeded.review_item_id, condition_id),
        data=_waiver_form(**overrides),
    )
    assert response.status_code == expected
    assert response.headers["Location"].endswith(_anchor(condition_id))

    db_session.expire_all()
    assert db_session.get(ARBCondition, condition_id).status == "pending"

    with client.session_transaction() as flask_session:
        from app.modules.architecture.routes.arb_condition_html_routes import (
            RETAINED_SESSION_KEY,
        )

        retained = flask_session.get(RETAINED_SESSION_KEY) or {}
    # The operator's own words survive; nothing derived or identifying does.
    assert set(retained) <= {"reason", "scope", "compensating_control", "expires_at"}
    if not overrides.get("reason", "").strip() == "":
        assert retained.get("reason")


def test_verify_without_an_evidence_id_is_rejected_before_the_command(
    app, db_session, make_org, client, login_as
):
    from app.models.arb_decision_event import ARBCondition

    _install_guards(db_session)
    seeded = _seed(db_session, make_org, "html-verify-noid", conditions=1)
    condition_id = seeded.condition_ids[0]

    login_as(client, seeded.authority_id)
    response = client.post(
        _verify_url(seeded.review_item_id, condition_id),
        data={"condition_evidence_id": ""},
    )
    assert response.status_code == 400
    db_session.expire_all()
    assert db_session.get(ARBCondition, condition_id).status == "pending"


def test_the_submitter_cannot_verify_their_own_evidence_over_html(
    app, db_session, make_org, client, login_as
):
    """Separation of duties is the command's, and the HTML transport does not bypass it."""
    from app.models.arb_condition_evidence import ARBConditionEvidenceRecord
    from app.models.arb_decision_event import ARBCondition
    from sqlalchemy import select

    _install_guards(db_session)
    seeded = _seed(db_session, make_org, "html-sod", conditions=1)
    condition_id = seeded.condition_ids[0]

    login_as(client, seeded.submitter_id)
    assert (
        client.post(
            _evidence_url(seeded.review_item_id, condition_id),
            data=_attestation_form(),
        ).status_code
        == 303
    )
    db_session.expire_all()
    evidence_id = db_session.execute(
        select(ARBConditionEvidenceRecord.id).where(
            ARBConditionEvidenceRecord.condition_id == condition_id,
            ARBConditionEvidenceRecord.organization_id == seeded.org_id,
        )
    ).scalar_one()

    login_as(client, seeded.submitter_id)
    refused = client.post(
        _verify_url(seeded.review_item_id, condition_id),
        data={"condition_evidence_id": str(evidence_id)},
    )
    assert refused.status_code == 403
    db_session.expire_all()
    assert db_session.get(ARBCondition, condition_id).status == "evidence_submitted"


# ── the template contract this transport depends on ──────────────────────────


def test_the_condition_forms_declare_both_transports(app):
    """`action` must be the HTML child route and `data-json-action` the JSON one.

    If these ever collapse back to a single JSON `action`, the no-JS path silently
    returns to rendering a raw JSON error payload in the browser window.
    """
    source = app.jinja_env.loader.get_source(
        app.jinja_env, "arb/partials/_typed_conditions.html"
    )[0]
    for suffix in ("evidence", "verify", "waive"):
        assert (
            f'action="/arb/reviews/{{{{ _rid }}}}/conditions/{{{{ _cid }}}}/{suffix}"'
            in source
        ), f"the {suffix} form does not post to its HTML child route"
    assert source.count("data-json-action=") == 3
    # `action=` on its own, not the `data-json-action=` that legitimately holds
    # the JSON URL.
    assert not re.search(r'(?<![-\w])action="/arb/api/conditions/', source)
