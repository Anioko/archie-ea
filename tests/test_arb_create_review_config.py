"""Every page carrying the ARB create-review modal must configure it.

The QA audit of 30 Aug 2026, High #8:

    "Alpine component state shows formOptions.review_types: [] and
     formOptions.decision_types: [] -- both empty -- while formOptions.loadError
     is false, so the app never detects the failure... No user can create a new
     ARB review through the UI, blocking a core governance workflow entirely."

The cause was configuration, not code. `arb/sessions.html` serves BOTH
/arb/sessions and /arb/reviews, includes `arb/_create_review_modal.html`, and
loads `js/arb/dashboard.js` -- but declared only `createSessionUrl` on
`window.__ARB_CONFIG__`. `loadFormData()` reads `formDataUrl`, found nothing,
and returned silently, so the dropdowns stayed empty and nothing anywhere went
red. The endpoint was healthy the whole time: /arb/api/form-data returns 10
review types and 8 decision types.

These tests pin the contract at both ends -- the shared modal's config is
declared on every page that includes it, and the endpoint that fills it still
returns the two lists the form cannot function without. A page returning 200
with an unusable form is exactly what a status assertion cannot see.
"""

import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(REPO, "app", "templates")
MODAL = "arb/_create_review_modal.html"

# The two keys dashboard.js reads before the modal can load options or submit.
REQUIRED_CONFIG = ("formDataUrl", "createReviewUrl")


def _templates_including_the_modal():
    found = []
    for dirpath, dirnames, filenames in os.walk(TEMPLATES):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".html"):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            # Built by concatenation: the pattern contains "{%", which %-formatting
            # would read as a conversion specifier.
            pattern = r"{%\s*include\s+['\"]" + re.escape(MODAL) + r"['\"]"
            if not re.search(pattern, source):
                continue
            # A PARTIAL inherits its parent page's config, so judging it on its
            # own reports a defect that does not exist: arb/partials/
            # _legacy_dashboard.html includes the modal and is itself included by
            # arb/dashboard.html, which declares both URLs. Only a page -- a
            # template that extends a layout -- owns its own configuration.
            if not re.search(r"{%\s*extends", source):
                continue
            found.append((os.path.relpath(path, REPO), source))
    return found


def test_the_modal_is_actually_included_somewhere():
    """Guard the guard: if the include is renamed, the test below silently passes."""
    assert _templates_including_the_modal(), (
        "no template includes %s -- this test can no longer see what it protects" % MODAL
    )


@pytest.mark.parametrize("key", REQUIRED_CONFIG)
def test_every_page_with_the_create_review_modal_declares_its_config(key):
    """A page that shows the modal must give it the URLs it reads."""
    missing = [
        rel for rel, source in _templates_including_the_modal()
        if key not in source
    ]
    assert not missing, (
        "%s include the ARB create-review modal but never declare "
        "__ARB_CONFIG__.%s, so the modal loads no options and reports no error"
        % (", ".join(missing), key)
    )


def test_the_form_data_endpoint_returns_the_lists_the_form_needs(client, db_session,
                                                                make_org, login_as):
    """The other end of the contract: the endpoint still fills both dropdowns."""
    from app.models.user import Role, User

    org = make_org("arbcfg")
    role = Role.query.filter_by(name="Architect").first() or Role.query.first()
    user = User(
        email="arb-config@example.com", first_name="ARB", last_name="Config",
        organization_id=org.id, confirmed=True, enterprise_role="arb_member",
    )
    user.role = role
    db_session.add(user)
    db_session.flush()

    login_as(client, user)
    response = client.get("/arb/api/form-data")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["success"] is True
    # Empty lists are the exact symptom the audit reported; assert content.
    assert payload["review_types"], "review_types is empty -- the form cannot be used"
    assert payload["decision_types"], "decision_types is empty -- the form cannot be used"
