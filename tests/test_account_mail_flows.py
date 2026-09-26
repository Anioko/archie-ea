"""Password reset, address confirmation and team invitations by e-mail.

Every message is captured by Flask-Mail's test backend (``mail.record_messages``):
under TESTING the SMTP session is suppressed and each message that would have
been handed to the mail server is recorded instead. The links in those
messages are then followed exactly as a person would follow them.
"""
import hashlib
import re
import uuid
from datetime import timedelta

import pytest

from tests.test_team_invite_acceptance import PASSWORD, _make_org
from tests.test_team_invite_acceptance import _make_user as _make_user_with


def _make_user(db_session, org, **kwargs):
    # The sign-in forms validate addresses, and reserved domains such as
    # .test do not pass, so every account here uses one that does.
    kwargs.setdefault("email", "person-{}@example.com".format(uuid.uuid4().hex[:10]))
    return _make_user_with(db_session, org, **kwargs)

NEW_PASSWORD = "Brand-New-Horse-42!"
SENDER = "no-reply@example.com"


@pytest.fixture
def outbox(app):
    from app.extensions import mail

    with mail.record_messages() as messages:
        yield messages


@pytest.fixture
def mail_on(app, monkeypatch):
    monkeypatch.setitem(app.config, "MAIL_DEFAULT_SENDER", SENDER)


@pytest.fixture
def mail_off(app, monkeypatch):
    monkeypatch.setitem(app.config, "MAIL_DEFAULT_SENDER", None)
    monkeypatch.setitem(app.config, "MAIL_USERNAME", None)


def _anonymous(app):
    """A client with no session, and no signed-in user cached on ``g``."""
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)
    return app.test_client()


def _link(message, path):
    match = re.search(r"https?://[^\s\"'<>]+" + re.escape(path) + r"[^\s\"'<>]+", message.body)
    assert match, "no {} link in: {}".format(path, message.body)
    return match.group(0).split("://", 1)[1].split("/", 1)[1].join(["/", ""])


def _main(resp):
    """The page's own content: everything outside <main> carries per-request nonces."""
    html = resp.get_data(as_text=True)
    return html[html.index("<main"):html.index("</main>")]


def _tokens(user_id, purpose):
    from app.models.account_token import AccountToken

    return AccountToken.query.filter_by(user_id=user_id, purpose=purpose).all()


def _fresh(user):
    from app import db
    from app.models.user import User

    db.session.expire_all()
    return db.session.get(User, user.id)


def _session_user_id(client):
    with client.session_transaction() as sess:
        return sess.get("_user_id")


# -- password reset -------------------------------------------------------


def test_reset_request_mails_a_link_whose_secret_is_stored_only_as_a_digest(
    app, db_session, mail_on, outbox
):
    org = _make_org(db_session, "R1")
    user = _make_user(db_session, org)
    db_session.commit()

    resp = _anonymous(app).post("/account/reset-password", data={"email": user.email})

    assert resp.status_code == 200
    assert b"Check your e-mail" in resp.data
    assert len(outbox) == 1
    assert outbox[0].recipients == [user.email]
    assert outbox[0].sender == SENDER
    path = _link(outbox[0], "/account/reset-password/")
    raw = path.rsplit("/", 1)[1]
    rows = _tokens(user.id, "password_reset")
    assert len(rows) == 1
    assert rows[0].token_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert raw not in rows[0].token_hash
    assert rows[0].delivery_status == "sent"
    assert rows[0].organization_id == org.id


def test_reset_link_sets_the_password_once_and_signs_nobody_in(app, db_session, mail_on, outbox):
    org = _make_org(db_session, "R2")
    user = _make_user(db_session, org)
    db_session.commit()
    _anonymous(app).post("/account/reset-password", data={"email": user.email})
    path = _link(outbox[0], "/account/reset-password/")

    client = _anonymous(app)
    assert client.get(path).status_code == 200
    resp = client.post(path, data={"password": NEW_PASSWORD, "password2": NEW_PASSWORD})

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/account/login")
    assert _session_user_id(client) is None
    assert _fresh(user).verify_password(NEW_PASSWORD)

    again = _anonymous(app)
    reused = again.post(path, data={"password": "Another-Horse-99!", "password2": "Another-Horse-99!"})
    assert reused.status_code == 410
    assert b"no longer works" in reused.data
    assert b"Send a new reset link" in reused.data
    assert _session_user_id(again) is None
    assert _fresh(user).verify_password(NEW_PASSWORD)
    assert _anonymous(app).get(path).status_code == 410


def test_an_expired_reset_link_is_refused_and_changes_nothing(app, db_session, mail_on, outbox):
    from app.models.account_token import _utcnow

    org = _make_org(db_session, "R3")
    user = _make_user(db_session, org)
    db_session.commit()
    _anonymous(app).post("/account/reset-password", data={"email": user.email})
    path = _link(outbox[0], "/account/reset-password/")
    row = _tokens(user.id, "password_reset")[0]
    row.expires_at = _utcnow() - timedelta(seconds=1)
    db_session.commit()

    client = _anonymous(app)
    assert client.get(path).status_code == 410
    resp = client.post(path, data={"password": NEW_PASSWORD, "password2": NEW_PASSWORD})
    assert resp.status_code == 410
    assert _fresh(user).verify_password(PASSWORD)


def test_a_newer_reset_link_withdraws_the_older_one(app, db_session, mail_on, outbox):
    org = _make_org(db_session, "R4")
    user = _make_user(db_session, org)
    db_session.commit()
    _anonymous(app).post("/account/reset-password", data={"email": user.email})
    _anonymous(app).post("/account/reset-password", data={"email": user.email})
    first = _link(outbox[0], "/account/reset-password/")
    second = _link(outbox[1], "/account/reset-password/")

    assert _anonymous(app).get(first).status_code == 410
    assert _anonymous(app).get(second).status_code == 200


def test_an_unknown_address_gets_the_same_answer_and_no_mail(app, db_session, mail_on, outbox):
    from app.models.account_token import AccountToken

    org = _make_org(db_session, "R5")
    user = _make_user(db_session, org)
    db_session.commit()
    before = AccountToken.query.count()
    unknown = "nobody-{}@example.com".format(uuid.uuid4().hex[:8])

    known_resp = _anonymous(app).post("/account/reset-password", data={"email": user.email})
    unknown_resp = _anonymous(app).post("/account/reset-password", data={"email": unknown})

    assert unknown_resp.status_code == known_resp.status_code == 200
    assert _main(unknown_resp).replace(unknown, "ADDRESS") == _main(known_resp).replace(
        user.email, "ADDRESS"
    )
    assert [m.recipients for m in outbox] == [[user.email]]
    assert AccountToken.query.count() == before + 1


def test_reset_without_a_mail_server_says_so_and_sends_nothing(app, db_session, mail_off, outbox):
    from app.models.account_token import AccountToken

    org = _make_org(db_session, "R6")
    user = _make_user(db_session, org)
    db_session.commit()
    before = AccountToken.query.count()

    page = _anonymous(app).get("/account/reset-password")
    resp = _anonymous(app).post("/account/reset-password", data={"email": user.email})

    for r in (page, resp):
        assert r.status_code == 200
        assert b"E-mail is not available on this server" in r.data
    assert outbox == []
    assert AccountToken.query.count() == before


# -- address confirmation -------------------------------------------------


def _register(client, email):
    return client.post("/account/register", data={
        "first_name": "Trial", "last_name": "Founder", "email": email,
        "password": PASSWORD, "password2": PASSWORD,
    })


def test_sign_up_waits_for_the_emailed_confirmation_then_goes_to_the_invite_step(
    app, db_session, mail_on, outbox
):
    from app.models.user import User

    email = "founder-{}@example.com".format(uuid.uuid4().hex[:8])
    client = _anonymous(app)
    resp = _register(client, email)

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/account/unconfirmed")
    user = User.find_by_email(email)
    assert user.confirmed is False
    assert len(outbox) == 1 and outbox[0].recipients == [email]
    assert client.get("/dashboard/overview").headers["Location"].endswith("/account/unconfirmed")

    path = _link(outbox[0], "/account/confirm-account/")
    confirmed = client.get(path)
    assert confirmed.status_code == 302
    assert confirmed.headers["Location"].endswith("/admin/team")
    assert _fresh(user).confirmed is True

    reused = _anonymous(app).get(path)
    assert reused.status_code == 410
    assert b"no longer works" in reused.data


def test_a_confirmation_link_works_without_being_signed_in(app, db_session, mail_on, outbox):
    from app.models.user import User

    email = "founder-{}@example.com".format(uuid.uuid4().hex[:8])
    _register(_anonymous(app), email)
    path = _link(outbox[0], "/account/confirm-account/")

    resp = _anonymous(app).get(path)

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/account/login")
    assert _fresh(User.find_by_email(email)).confirmed is True


def test_resending_confirmation_withdraws_the_earlier_link(app, db_session, mail_on, outbox):
    email = "founder-{}@example.com".format(uuid.uuid4().hex[:8])
    client = _anonymous(app)
    _register(client, email)
    resp = client.post("/account/confirm-account")

    assert resp.status_code == 302
    assert len(outbox) == 2
    first = _link(outbox[0], "/account/confirm-account/")
    assert _anonymous(app).get(first).status_code == 410


def test_sign_up_without_a_mail_server_is_usable_and_says_no_message_was_sent(
    app, db_session, mail_off, outbox
):
    from app.models.user import User

    email = "founder-{}@example.com".format(uuid.uuid4().hex[:8])
    client = _anonymous(app)
    resp = _register(client, email)

    assert resp.status_code == 302
    assert User.find_by_email(email).confirmed is True
    assert outbox == []
    with client.session_transaction() as sess:
        flashes = [m for _c, m in sess.get("_flashes", [])]
    assert any("E-mail is not available on this server" in m for m in flashes)


# -- invitations ----------------------------------------------------------


def _invite(client, login_as, admin, email, role="architect", persona="data_architect"):
    login_as(client, admin)
    return client.post("/admin/team/invite", data={"email": email, "role": role, "persona": persona})


def test_an_accepted_invitation_joins_the_inviters_organisation(
    app, db_session, login_as, client, mail_on, outbox
):
    from app.models.org_role import OrgRole
    from app.models.user import User

    org = _make_org(db_session, "I1")
    admin = _make_user(db_session, org, org_admin=True)
    db_session.commit()
    email = "teammate-{}@example.com".format(uuid.uuid4().hex[:8])

    resp = _invite(client, login_as, admin, email)

    assert resp.status_code == 302
    assert len(outbox) == 1 and outbox[0].recipients == [email]
    invitee = User.find_by_email(email)
    assert invitee.organization_id == org.id
    assert invitee.password_hash is None
    assert OrgRole.get_role(org.id, invitee.id) is None
    login_as(client, admin)
    team = client.get("/admin/team")
    assert email.encode() in team.data and b"Sent " in team.data

    path = _link(outbox[0], "/account/join/")
    guest = _anonymous(app)
    page = guest.get(path)
    assert page.status_code == 200
    assert org.name.encode() in page.data
    joined = guest.post(path, data={"password": NEW_PASSWORD, "password2": NEW_PASSWORD})

    assert joined.status_code == 302
    assert joined.headers["Location"].endswith("/account/login")
    invitee = _fresh(invitee)
    assert invitee.organization_id == org.id
    assert invitee.confirmed is True
    assert invitee.verify_password(NEW_PASSWORD)
    assert invitee.enterprise_role == "data_architect"
    assert OrgRole.get_role(org.id, invitee.id) == "architect"
    assert _anonymous(app).get(path).status_code == 410


def test_another_organisations_invitation_is_refused(
    app, db_session, login_as, client, mail_on, outbox
):
    from app.models.account_token import AccountToken
    from app.models.org_role import OrgRole
    from app.models.user import User

    org_a = _make_org(db_session, "IA")
    org_b = _make_org(db_session, "IB")
    admin_a = _make_user(db_session, org_a, org_admin=True)
    admin_b = _make_user(db_session, org_b, org_admin=True)
    db_session.commit()
    email = "teammate-{}@example.com".format(uuid.uuid4().hex[:8])
    _invite(client, login_as, admin_a, email)
    path = _link(outbox[0], "/account/join/")
    invitee = User.find_by_email(email)
    token_id = AccountToken.query.filter_by(user_id=invitee.id, purpose="invitation").one().id

    # Org B's administrator cannot resend or withdraw org A's invitation.
    client_b = app.test_client()
    login_as(client_b, admin_b)
    assert client_b.post(f"/admin/team/invitations/{token_id}/resend").status_code == 404
    login_as(client_b, admin_b)
    assert client_b.post(f"/admin/team/invitations/{token_id}/revoke").status_code == 404
    login_as(client_b, admin_b)
    assert email.encode() not in client_b.get("/admin/team").data
    assert len(outbox) == 1

    # Someone signed in to org B cannot take the invitation up.
    login_as(client_b, admin_b)
    assert client_b.post(path, data={"password": NEW_PASSWORD, "password2": NEW_PASSWORD}).status_code == 410
    assert OrgRole.get_role(org_b.id, invitee.id) is None

    # A token whose organisation is not the account's organisation puts its
    # holder nowhere: neither org A nor org B.
    invitee.organization_id = org_b.id
    db_session.commit()
    resp = _anonymous(app).post(path, data={"password": NEW_PASSWORD, "password2": NEW_PASSWORD})
    assert resp.status_code == 410
    assert OrgRole.get_role(org_a.id, invitee.id) is None
    assert OrgRole.get_role(org_b.id, invitee.id) is None
    assert _fresh(invitee).password_hash is None


def test_an_expired_invitation_is_refused_and_grants_nothing(
    app, db_session, login_as, client, mail_on, outbox
):
    from app.models.account_token import AccountToken, _utcnow
    from app.models.org_role import OrgRole
    from app.models.user import User

    org = _make_org(db_session, "I3")
    admin = _make_user(db_session, org, org_admin=True)
    db_session.commit()
    email = "teammate-{}@example.com".format(uuid.uuid4().hex[:8])
    _invite(client, login_as, admin, email)
    path = _link(outbox[0], "/account/join/")
    invitee = User.find_by_email(email)
    row = AccountToken.query.filter_by(user_id=invitee.id, purpose="invitation").one()
    row.expires_at = _utcnow() - timedelta(seconds=1)
    db_session.commit()

    guest = _anonymous(app)
    assert guest.get(path).status_code == 410
    assert guest.post(path, data={"password": NEW_PASSWORD, "password2": NEW_PASSWORD}).status_code == 410
    assert OrgRole.get_role(org.id, invitee.id) is None
    assert _fresh(invitee).password_hash is None


def test_resending_an_invitation_withdraws_the_earlier_link(
    app, db_session, login_as, client, mail_on, outbox
):
    from app.models.account_token import AccountToken
    from app.models.user import User

    org = _make_org(db_session, "I4")
    admin = _make_user(db_session, org, org_admin=True)
    db_session.commit()
    email = "teammate-{}@example.com".format(uuid.uuid4().hex[:8])
    _invite(client, login_as, admin, email)
    invitee = User.find_by_email(email)
    token_id = AccountToken.query.filter_by(user_id=invitee.id, purpose="invitation").one().id

    login_as(client, admin)
    assert client.post(f"/admin/team/invitations/{token_id}/resend").status_code == 302

    assert len(outbox) == 2
    assert _anonymous(app).get(_link(outbox[0], "/account/join/")).status_code == 410
    assert _anonymous(app).get(_link(outbox[1], "/account/join/")).status_code == 200


def test_inviting_without_a_mail_server_says_so_and_creates_nothing(
    app, db_session, login_as, client, mail_off, outbox
):
    from app.models.user import User

    org = _make_org(db_session, "I5")
    admin = _make_user(db_session, org, org_admin=True)
    db_session.commit()
    email = "teammate-{}@example.com".format(uuid.uuid4().hex[:8])

    resp = _invite(client, login_as, admin, email)

    assert resp.status_code == 503
    assert b"E-mail is not available on this server" in resp.data
    assert User.find_by_email(email) is None
    assert outbox == []


def test_a_refused_message_is_shown_as_not_sent_with_its_reason(
    app, db_session, login_as, client, mail_on, monkeypatch
):
    import smtplib

    from app import flask_email

    def refuse(self, message, envelope_from=None):
        raise smtplib.SMTPRecipientsRefused({"x@example.com": (550, b"no such mailbox")})

    monkeypatch.setattr(flask_email._BoundedConnection, "send", refuse)
    org = _make_org(db_session, "I6")
    admin = _make_user(db_session, org, org_admin=True)
    db_session.commit()
    email = "teammate-{}@example.com".format(uuid.uuid4().hex[:8])

    _invite(client, login_as, admin, email)
    login_as(client, admin)
    team = client.get("/admin/team")

    assert b"Not sent:" in team.data
    assert b"SMTPRecipientsRefused" in team.data
