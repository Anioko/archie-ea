"""Real Flask/DB empty-portfolio contract; shared rollback fixtures, no route doubles."""
import re
import uuid


def test_empty_procurement_portfolio_has_no_measured_utilization(
    db_session, make_org, client, login_as
):
    from app.models.user import User

    org = make_org("procurement-empty")
    user = User(
        email=f"qa-procurement-{uuid.uuid4().hex}@example.com",
        first_name="QA", last_name="Procurement", confirmed=True,
        organization_id=org.id, enterprise_role="procurement",
    )
    db_session.add(user)
    db_session.flush()
    login_as(client, user)
    response = client.get("/procurement/compliance")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    metric = re.search(r'Overall Utilization</div>\s*<div[^>]*>([^<]+)</div>', html)
    assert metric and metric.group(1).strip() == "—"
    assert "No license data" in html
    assert "Utilization unavailable" in html
