"""
PLT-009 / PLT-031: Weekly digest email functions.

These are called by APScheduler jobs (extensions.py) and CLI commands (cli.py).
Emails degrade gracefully: if SMTP is not configured, content is logged instead.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _safe_send_email(app, subject, recipients, html_body):
    """Send an email via Flask-Mail, falling back to logging if SMTP is unavailable.

    Returns True if sent, False if logged only.
    """
    if not recipients:
        logger.info("No recipients for '%s' — skipping.", subject)
        return False

    mail_server = app.config.get("MAIL_SERVER")
    mail_username = app.config.get("MAIL_USERNAME")
    if not mail_server or not mail_username:
        logger.warning(
            "SMTP not configured (MAIL_SERVER=%s) — logging email instead.",
            mail_server,
        )
        logger.info(
            "EMAIL [%s] to %s:\n%s",
            subject,
            ", ".join(recipients),
            html_body[:2000],
        )
        return False

    try:
        from flask_mail import Message
        from app.extensions import mail

        prefix = app.config.get("EMAIL_SUBJECT_PREFIX", "[ARCHIE]")
        sender = app.config.get("EMAIL_SENDER", mail_username)
        msg = Message(
            subject=f"{prefix} {subject}",
            sender=sender,
            recipients=recipients,
        )
        msg.html = html_body
        mail.send(msg)
        logger.info("Sent '%s' to %d recipients.", subject, len(recipients))
        return True
    except Exception as exc:
        logger.error("Failed to send '%s': %s — logging content instead.", subject, exc)
        logger.info(
            "EMAIL [%s] to %s:\n%s",
            subject,
            ", ".join(recipients),
            html_body[:2000],
        )
        return False


def _get_recipients_by_roles(role_list):
    """Return list of email addresses for users with given enterprise_role values."""
    from app.models import User

    users = User.query.filter(
        User.enterprise_role.in_(role_list),
        User.confirmed.is_(True),
    ).all()
    return [u.email for u in users if u.email]


# ---------------------------------------------------------------------------
# PLT-009: Data Maturity Digest
# ---------------------------------------------------------------------------


def _compute_maturity_data():
    """Compute portfolio-wide completeness metrics for the digest."""
    from app.models.solution_models import Solution

    solutions = Solution.query.all()
    if not solutions:
        return {
            "total": 0,
            "avg_score": 0,
            "zero_connections": [],
            "top_incomplete": [],
            "junction_fill_rates": {},
        }

    scores = []
    zero_connections = []
    all_junction_filled = {}
    all_junction_total = {}

    for sol in solutions:
        try:
            cs = sol.architecture_completeness_score
            score = cs["score"]
            scores.append({"name": sol.name, "id": sol.id, "score": score})
            if score == 0:
                zero_connections.append({"name": sol.name, "id": sol.id})
            for jname in cs.get("filled", []):
                all_junction_filled[jname] = all_junction_filled.get(jname, 0) + 1
            for jname in cs.get("filled", []) + cs.get("missing", []):
                all_junction_total[jname] = all_junction_total.get(jname, 0) + 1
        except Exception:
            logger.debug("Could not compute score for solution %s", sol.id)

    total = len(scores)
    avg_score = round(sum(s["score"] for s in scores) / total) if total else 0
    top_incomplete = sorted(scores, key=lambda s: s["score"])[:10]

    junction_fill_rates = {}
    for jname, jtotal in all_junction_total.items():
        filled = all_junction_filled.get(jname, 0)
        junction_fill_rates[jname] = round(filled / jtotal * 100) if jtotal else 0

    return {
        "total": total,
        "avg_score": avg_score,
        "zero_connections": zero_connections,
        "top_incomplete": top_incomplete,
        "junction_fill_rates": junction_fill_rates,
    }


def _render_maturity_digest_html(data):
    """Build HTML email body for the data maturity digest."""
    now = datetime.utcnow().strftime("%Y-%m-%d")

    zero_rows = ""
    for s in data["zero_connections"][:20]:
        zero_rows += f'<tr><td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{s["name"]}</td></tr>\n'
    if not zero_rows:
        zero_rows = '<tr><td style="padding:4px 8px;color:#16a34a">All solutions have at least one connection.</td></tr>'

    incomplete_rows = ""
    for s in data["top_incomplete"][:10]:
        color = "#dc2626" if s["score"] < 25 else "#d97706" if s["score"] < 50 else "#2563eb"
        incomplete_rows += (
            f'<tr><td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{s["name"]}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #e5e7eb;color:{color};font-weight:600">'
            f'{s["score"]}%</td></tr>\n'
        )

    junction_rows = ""
    for jname, rate in sorted(data["junction_fill_rates"].items(), key=lambda x: x[1]):
        bar_color = "#dc2626" if rate < 25 else "#d97706" if rate < 50 else "#2563eb" if rate < 75 else "#16a34a"
        junction_rows += (
            f'<tr><td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{jname.replace("_", " ").title()}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">'
            f'<div style="background:#e5e7eb;border-radius:4px;height:16px;width:120px;display:inline-block">'
            f'<div style="background:{bar_color};border-radius:4px;height:16px;width:{int(rate * 1.2)}px"></div>'
            f'</div> {rate}%</td></tr>\n'
        )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1f2937;max-width:640px;margin:0 auto;padding:16px">
<h2 style="color:#111827;border-bottom:2px solid #2563eb;padding-bottom:8px">
    Data Maturity Digest &mdash; {now}
</h2>

<table style="width:100%;margin-bottom:24px">
<tr>
  <td style="background:#eff6ff;padding:16px;border-radius:8px;text-align:center;width:50%">
    <div style="font-size:32px;font-weight:700;color:#2563eb">{data['total']}</div>
    <div style="font-size:13px;color:#6b7280">Total Solutions</div>
  </td>
  <td style="width:16px"></td>
  <td style="background:#f0fdf4;padding:16px;border-radius:8px;text-align:center;width:50%">
    <div style="font-size:32px;font-weight:700;color:#16a34a">{data['avg_score']}%</div>
    <div style="font-size:13px;color:#6b7280">Avg Completeness</div>
  </td>
</tr>
</table>

<h3 style="color:#dc2626">Solutions With Zero Connections ({len(data['zero_connections'])})</h3>
<table style="width:100%;border-collapse:collapse;margin-bottom:24px">
{zero_rows}
</table>

<h3 style="color:#d97706">Top 10 Least Complete Solutions</h3>
<table style="width:100%;border-collapse:collapse;margin-bottom:24px">
<tr><th style="text-align:left;padding:4px 8px;border-bottom:2px solid #e5e7eb">Solution</th>
    <th style="text-align:left;padding:4px 8px;border-bottom:2px solid #e5e7eb">Score</th></tr>
{incomplete_rows}
</table>

<h3 style="color:#2563eb">Junction Fill Rates (Portfolio-wide)</h3>
<table style="width:100%;border-collapse:collapse;margin-bottom:24px">
<tr><th style="text-align:left;padding:4px 8px;border-bottom:2px solid #e5e7eb">Junction</th>
    <th style="text-align:left;padding:4px 8px;border-bottom:2px solid #e5e7eb">Fill Rate</th></tr>
{junction_rows}
</table>

<p style="font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;padding-top:8px">
    This is an automated weekly digest from ARCHIE. To unsubscribe, update your notification
    preferences in your profile settings.
</p>
</body>
</html>"""


def send_data_maturity_digest(app):
    """PLT-009: Compute and send the weekly data maturity digest."""
    logger.info("PLT-009: Generating data maturity digest...")
    data = _compute_maturity_data()
    html = _render_maturity_digest_html(data)
    recipients = _get_recipients_by_roles([
        "enterprise_architect",
        "portfolio_manager",
        "platform_admin",
    ])
    _safe_send_email(app, "Weekly Data Maturity Digest", recipients, html)
    logger.info(
        "PLT-009: Digest complete — %d solutions, %d%% avg score, %d recipients.",
        data["total"],
        data["avg_score"],
        len(recipients),
    )
    return data


# ---------------------------------------------------------------------------
# PLT-031: Executive Summary
# ---------------------------------------------------------------------------


def _compute_executive_data():
    """Compute portfolio stats for the executive summary email."""
    from app.models.solution_models import Solution
    from app.models.solution_lifecycle_models import SolutionRisk

    one_week_ago = datetime.utcnow() - timedelta(days=7)

    # New solutions this week
    new_solutions = Solution.query.filter(
        Solution.created_at >= one_week_ago
    ).all()

    # All solutions for completeness
    all_solutions = Solution.query.all()
    scores = []
    for sol in all_solutions:
        try:
            cs = sol.architecture_completeness_score
            scores.append(cs["score"])
        except Exception:  # fabricated-values-ok: skip solutions with missing junctions
            continue

    avg_score = round(sum(scores) / len(scores)) if scores else 0

    # ARB decisions this week
    arb_decisions = []
    try:
        from app.models.architecture_review_board import ARBReviewItem
        decided = ARBReviewItem.query.filter(
            ARBReviewItem.decision_date >= one_week_ago,
            ARBReviewItem.decision.isnot(None),
        ).all()
        for item in decided:
            arb_decisions.append({
                "title": item.title,
                "decision": item.decision,
                "review_number": item.review_number,
            })
    except Exception as exc:
        logger.debug("Could not query ARB decisions: %s", exc)

    # New risks flagged this week
    new_risks = []
    try:
        risks = SolutionRisk.query.filter(
            SolutionRisk.created_at >= one_week_ago
        ).order_by(SolutionRisk.impact.desc()).limit(5).all()
        for r in risks:
            sol = Solution.query.get(r.solution_id)
            new_risks.append({
                "description": (r.risk_description or "")[:120],
                "impact": r.impact,
                "solution_name": sol.name if sol else "Unknown",
            })
    except Exception as exc:
        logger.debug("Could not query new risks: %s", exc)

    # Phase distribution
    phase_counts = {}
    for sol in all_solutions:
        p = sol.adm_phase or "A"
        phase_counts[p] = phase_counts.get(p, 0) + 1

    return {
        "total_solutions": len(all_solutions),
        "new_solutions": [{"name": s.name, "id": s.id} for s in new_solutions],
        "new_solutions_count": len(new_solutions),
        "avg_completeness": avg_score,
        "arb_decisions": arb_decisions,
        "arb_decisions_count": len(arb_decisions),
        "new_risks": new_risks,
        "phase_counts": phase_counts,
        "week_ending": datetime.utcnow().strftime("%Y-%m-%d"),
    }


def _render_executive_summary_html(data):
    """Build HTML email body for the executive summary."""
    week_ending = data["week_ending"]

    # New solutions table
    new_sol_rows = ""
    for s in data["new_solutions"][:10]:
        new_sol_rows += f'<tr><td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{s["name"]}</td></tr>\n'
    if not new_sol_rows:
        new_sol_rows = '<tr><td style="padding:4px 8px;color:#6b7280;font-style:italic">No new solutions this week.</td></tr>'

    # ARB decisions table
    arb_rows = ""
    for d in data["arb_decisions"][:10]:
        badge_color = "#16a34a" if "approved" in (d["decision"] or "") else "#dc2626" if d["decision"] == "rejected" else "#d97706"
        arb_rows += (
            f'<tr><td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{d["review_number"]}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{d["title"][:60]}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #e5e7eb;color:{badge_color};font-weight:600">'
            f'{(d["decision"] or "pending").replace("_", " ").title()}</td></tr>\n'
        )
    if not arb_rows:
        arb_rows = '<tr><td colspan="3" style="padding:4px 8px;color:#6b7280;font-style:italic">No ARB decisions this week.</td></tr>'

    # Risks table
    risk_rows = ""
    for r in data["new_risks"]:
        impact_color = "#dc2626" if r["impact"] in ("critical", "high") else "#d97706"
        risk_rows += (
            f'<tr><td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{r["solution_name"]}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">{r["description"]}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #e5e7eb;color:{impact_color};font-weight:600">'
            f'{r["impact"].title()}</td></tr>\n'
        )
    if not risk_rows:
        risk_rows = '<tr><td colspan="3" style="padding:4px 8px;color:#6b7280;font-style:italic">No new risks flagged this week.</td></tr>'

    # Phase distribution
    phase_rows = ""
    phase_labels = {
        "A": "Architecture Vision",
        "B": "Business Architecture",
        "C": "Information Systems",
        "D": "Technology Architecture",
        "E": "Opportunities & Solutions",
        "F": "Migration Planning",
        "G": "Implementation Governance",
        "H": "Architecture Change Mgmt",
    }
    for phase in ["A", "B", "C", "D", "E", "F", "G", "H"]:
        count = data["phase_counts"].get(phase, 0)
        if count > 0:
            phase_rows += (
                f'<tr><td style="padding:4px 8px;border-bottom:1px solid #e5e7eb">'
                f'Phase {phase} &mdash; {phase_labels.get(phase, phase)}</td>'
                f'<td style="padding:4px 8px;border-bottom:1px solid #e5e7eb;font-weight:600">{count}</td></tr>\n'
            )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1f2937;max-width:640px;margin:0 auto;padding:16px">
<h2 style="color:#111827;border-bottom:2px solid #7c3aed;padding-bottom:8px">
    Executive Architecture Summary &mdash; Week Ending {week_ending}
</h2>

<table style="width:100%;margin-bottom:24px">
<tr>
  <td style="background:#eff6ff;padding:12px;border-radius:8px;text-align:center;width:25%">
    <div style="font-size:28px;font-weight:700;color:#2563eb">{data['total_solutions']}</div>
    <div style="font-size:11px;color:#6b7280">Total Solutions</div>
  </td>
  <td style="width:8px"></td>
  <td style="background:#f0fdf4;padding:12px;border-radius:8px;text-align:center;width:25%">
    <div style="font-size:28px;font-weight:700;color:#16a34a">{data['new_solutions_count']}</div>
    <div style="font-size:11px;color:#6b7280">New This Week</div>
  </td>
  <td style="width:8px"></td>
  <td style="background:#faf5ff;padding:12px;border-radius:8px;text-align:center;width:25%">
    <div style="font-size:28px;font-weight:700;color:#7c3aed">{data['avg_completeness']}%</div>
    <div style="font-size:11px;color:#6b7280">Avg Completeness</div>
  </td>
  <td style="width:8px"></td>
  <td style="background:#fef2f2;padding:12px;border-radius:8px;text-align:center;width:25%">
    <div style="font-size:28px;font-weight:700;color:#dc2626">{data['arb_decisions_count']}</div>
    <div style="font-size:11px;color:#6b7280">ARB Decisions</div>
  </td>
</tr>
</table>

<h3 style="color:#2563eb">New Solutions Submitted ({data['new_solutions_count']})</h3>
<table style="width:100%;border-collapse:collapse;margin-bottom:24px">
{new_sol_rows}
</table>

<h3 style="color:#7c3aed">ARB Decisions This Week</h3>
<table style="width:100%;border-collapse:collapse;margin-bottom:24px">
<tr><th style="text-align:left;padding:4px 8px;border-bottom:2px solid #e5e7eb">Review #</th>
    <th style="text-align:left;padding:4px 8px;border-bottom:2px solid #e5e7eb">Title</th>
    <th style="text-align:left;padding:4px 8px;border-bottom:2px solid #e5e7eb">Decision</th></tr>
{arb_rows}
</table>

<h3 style="color:#dc2626">Top Risks Flagged This Week</h3>
<table style="width:100%;border-collapse:collapse;margin-bottom:24px">
<tr><th style="text-align:left;padding:4px 8px;border-bottom:2px solid #e5e7eb">Solution</th>
    <th style="text-align:left;padding:4px 8px;border-bottom:2px solid #e5e7eb">Risk</th>
    <th style="text-align:left;padding:4px 8px;border-bottom:2px solid #e5e7eb">Impact</th></tr>
{risk_rows}
</table>

<h3 style="color:#374151">Portfolio by TOGAF Phase</h3>
<table style="width:100%;border-collapse:collapse;margin-bottom:24px">
<tr><th style="text-align:left;padding:4px 8px;border-bottom:2px solid #e5e7eb">Phase</th>
    <th style="text-align:left;padding:4px 8px;border-bottom:2px solid #e5e7eb">Solutions</th></tr>
{phase_rows}
</table>

<p style="font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;padding-top:8px">
    This is an automated weekly summary from ARCHIE. Sent to platform administrators.
</p>
</body>
</html>"""


def send_executive_summary(app):
    """PLT-031: Compute and send the weekly executive summary."""
    logger.info("PLT-031: Generating executive summary...")
    data = _compute_executive_data()
    html = _render_executive_summary_html(data)
    recipients = _get_recipients_by_roles(["platform_admin"])
    _safe_send_email(app, "Weekly Executive Architecture Summary", recipients, html)
    logger.info(
        "PLT-031: Summary complete — %d total solutions, %d new, %d ARB decisions, %d recipients.",
        data["total_solutions"],
        data["new_solutions_count"],
        data["arb_decisions_count"],
        len(recipients),
    )
    return data
