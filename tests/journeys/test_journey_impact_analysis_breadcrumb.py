"""Journey: the Impact Analysis page's breadcrumb must end in the page's own name.

Reported problem: the H1 said "Impact Analysis" but the trail read "Home > Strategy Layer > Strategic
Planning". "Strategic Planning" is the name of a different page, so a user retracing their steps by
breadcrumb, or scanning history, would not recognise it as the page they were just on.

Asserted on the real rendered page, as a logged-in architect, comparing the last crumb with the H1.
"""

import re

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def _crumbs(html):
    navs = re.findall(r'<nav[^>]*aria-label="Breadcrumb".*?</nav>', html, re.S)
    # Assert exactly one, not just "at least one": a second breadcrumb-shaped <nav> (the sidebar carries one
    # with the identical aria-label) would make re.search silently pick whichever comes first in the
    # document rather than failing loudly.
    assert len(navs) == 1, "expected exactly one breadcrumb <nav>, found %d" % len(navs)
    items = re.findall(r"<li\b.*?</li>", navs[0], re.S)
    texts = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", i)).strip() for i in items]
    return [t for t in texts if t]


def _h1(html):
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    assert match, "no <h1> on the page"
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", match.group(1))).strip()


def test_impact_analysis_breadcrumb_leaf_matches_the_page_title(app, client):
    from app import db

    with app.app_context():
        org_id = make_org(db, "ImpactCrumb")
        architect = make_user(db, org_id, "sa", "solution_architect", role_name="Architect")
    login(client, architect)

    response = client.get("/strategic/impact-analysis")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    crumbs = _crumbs(html)
    assert crumbs[-1] == _h1(html) == "Impact Analysis", (crumbs, _h1(html))
    # The parent crumbs are unchanged.
    assert crumbs[:2] == ["Home", "Strategy Layer"], crumbs
