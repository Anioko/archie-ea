"""Regression tests for V-07 (literal "None" rendered for a user with no
name) and F-05 (page-title audit / ARCH-108 follow-up).

V-07: /account/manage rendered "Full name: None None" when first_name and
last_name were both NULL, because account/manage.html string-formatted the
raw columns instead of using User.full_name(), which already falls back to
the email (or "Unknown User") for a nameless user. The fix routes the
template through that existing shared helper instead of adding a second one.

F-05: several routes rendered an empty (or entirely absent, on
layouts/base.html) <title> element. This test asserts a representative
sample of the fixed pages carry a real, non-empty, non-"None" <title>.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_user(db_session, org_id, email, first_name=None, last_name=None, role_name="Administrator"):
    from app.models.role import Role
    from app.models.user import User

    role = Role.query.filter_by(name=role_name).first()
    user = User(
        email=email,
        password="Testpass123!",
        first_name=first_name,
        last_name=last_name,
        organization_id=org_id,
        confirmed=True,
        role=role,
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_full_name_with_no_name_set_is_not_literal_none(db_session):
    """V-07: User.full_name() must never produce the string 'None'."""
    from app.models.user import User

    user = User(email="nameless@example.com", password="x")
    user.first_name = None
    user.last_name = None

    result = user.full_name()

    assert "None" not in result
    assert result  # non-empty fallback (email or "Unknown User")


def test_account_manage_page_does_not_render_literal_none(app, db_session, login_as, make_org):
    """V-07: the actual /account/manage page, rendered end-to-end."""
    org = make_org("v07")
    user = _make_user(db_session, org.id, "v07-nameless@example.com")
    # first_name/last_name deliberately left NULL

    client = app.test_client()
    login_as(client, user)

    resp = client.get("/account/manage")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "None None" not in body
    assert ">None<" not in body


@pytest.mark.parametrize(
    "path_getter, expected_fragment",
    [
        ("/account/manage", "Account Settings"),
        ("/admin/", "Command Center"),
    ],
)
def test_representative_pages_have_meaningful_titles(
    app, db_session, login_as, make_org, path_getter, expected_fragment
):
    """F-05: a sample of the pages that previously had no <title> block."""
    import re

    org = make_org("f05")
    user = _make_user(db_session, org.id, f"f05-{path_getter.strip('/').replace('/', '-')}@example.com")

    client = app.test_client()
    login_as(client, user)

    resp = client.get(path_getter)
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    match = re.search(r"<title>(.*?)</title>", body, re.DOTALL)
    assert match, f"no <title> element found for {path_getter}"
    title_text = match.group(1).strip()

    assert title_text, f"<title> is empty for {path_getter}"
    assert "None" not in title_text
    assert expected_fragment in title_text


def test_legacy_base_layout_now_has_a_title_block():
    """F-05: layouts/base.html previously had no <title> tag anywhere,
    directly or via partials/_head.html — worse than an empty fallback,
    because no block existed for a child template to fill."""
    with open("app/templates/layouts/base.html", encoding="utf-8") as fh:
        content = fh.read()

    assert "<title>" in content
    assert "{% block title %}" in content
