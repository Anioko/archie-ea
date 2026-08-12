"""Every link in the application shell must work for the persona seeing it.

The sidebar wordmark linked to ``admin.index``, which is ``@admin_required``. So
the most-clicked element on every page — the product logo — answered 403 for
every persona except platform_admin. A business architect clicking it got a
permission error on a page they had every right to be on.

Nothing caught it. ``dead-interactions`` looks for controls that do nothing, and
this one navigated. ``broken-surfaces`` resolves front-end targets against the
route table, and the route exists. It is only wrong *for this user*, which means
the check has to render the shell as a persona and follow what it finds.

That is what this does: render the shell as a business architect with both admin
flags off, collect every internal link, and request each one.
"""

from __future__ import annotations

import re
import uuid

import pytest


def _persona_user(db_session, org_id, enterprise_role):
    from app.models.user import User

    user = User(
        email=f"shell-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Shell",
        last_name="Probe",
        organization_id=org_id,
        confirmed=True,
        enterprise_role=enterprise_role,
    )
    # These default True on the model; leaving them on would grant "admin" and
    # hide exactly the failure this test exists to find.
    user.is_platform_admin = False
    user.is_org_admin = False
    db_session.add(user)
    db_session.commit()
    return user.id


def _client_as(app, user_id):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)
    return client


@pytest.mark.parametrize(
    "persona", ["business_architect", "solution_architect", "enterprise_architect"]
)
def test_the_shell_has_no_link_this_persona_cannot_open(
    app, db_session, make_org, tenant_ctx, persona
):
    org = make_org(f"shell-{persona[:6]}-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user_id = _persona_user(db_session, org.id, persona)

    client = _client_as(app, user_id)
    home = client.get("/dashboard/overview")
    assert home.status_code == 200, "the shell itself did not render"

    links = sorted(set(re.findall(r'href="(/[^"#?]*)"', home.data.decode("utf8", "replace"))))
    assert len(links) > 20, "the shell rendered almost no navigation — check the fixture"

    broken = []
    for href in links:
        if href.startswith("/static") or "logout" in href:
            continue
        response = client.get(href, follow_redirects=True)
        if response.status_code >= 400:
            broken.append(f"{response.status_code} {href}")

    assert not broken, (
        f"a {persona} is shown links they cannot open:\n  " + "\n  ".join(broken)
    )
