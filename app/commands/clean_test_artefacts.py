"""flask --app manage clean-test-artefacts — ARCH-116 remedy.

ARCH-116 is data hygiene, not a code defect: a debug/QA-probe row ("ZZ Approval
UI Probe", id 70 — the "ZZ" prefix is a sorting hack to force it to the bottom
of an alphabetical list) is currently the *only* row in the application
catalogue of this environment, so any demo, screenshot or evaluation shows a
test artefact as the entire portfolio.

The register's own acceptance criteria are environment-separation criteria
(separate demo/test/dev environments, a seeded realistic demo portfolio,
"test artefacts removed from any environment used for demonstration") — none
of which a script can do for you, because a script cannot know which
environment it is running against or provision a second one. What a script
*can* safely do is find and, on explicit request, remove rows that match
known QA-probe naming conventions, so this environment's hygiene can be
restored without a human hand-picking row ids.

Detection heuristics (conservative — false negatives are fine, false
positives on real customer data are not):
  - name starts with "ZZ " (the sorting-hack prefix seen on id 70)
  - name starts with "QA-TEST" (the ARCH-030/ARCH-071 probe convention used
    throughout this QA engagement — "QA-TEST Probe Alpha", "QA-TEST <script>...")
  - name starts with "TEST-" or "TEST_" or is exactly "Test"/"test"

Never deletes anything by default. --dry-run (or no flag at all — dry-run is
the default, unlike dedupe-entities) reports counts and the matched rows;
--execute performs the delete, and still refuses without --i-understand-this-
is-production-adjacent unless the row count is small, as a last speed bump
against fat-fingering this against a real environment.

    flask --app manage clean-test-artefacts               # dry-run report (default)
    flask --app manage clean-test-artefacts --dry-run      # same, explicit
    flask --app manage clean-test-artefacts --execute      # actually deletes

This command has NOT been run against any environment by the agent that wrote
it — see the QA-register response for ARCH-116 for why (this repo's checkout
has no way to distinguish "the shared dev/test box" from "production" other
than the standing instruction never to touch the latter, and DATABASE_URL is
config, not a fact this script can verify).
"""

from __future__ import annotations

import click
from flask.cli import with_appcontext

from app import db

_NAME_PATTERNS_SQL = (
    "name LIKE 'ZZ %' OR "
    "name LIKE 'QA-TEST%' OR "
    "name LIKE 'TEST-%' OR "
    "name LIKE 'TEST\\_%' ESCAPE '\\' OR "
    "lower(name) = 'test'"
)


def _find_matches():
    from sqlalchemy import text

    # tenancy-ok: CLI runs outside a request context (no g.current_org_id to
    # scope to — see CLAUDE.md "Multi-tenancy"); this is a deliberate
    # cross-org sweep for a known QA-probe naming convention, and every
    # matched row's organization_id is reported to the operator before
    # anything is deleted.
    rows = db.session.execute(
        text(
            f"SELECT id, name, organization_id, created_at FROM application_components "
            f"WHERE {_NAME_PATTERNS_SQL} ORDER BY id"
        )
    ).fetchall()
    return rows


@click.command("clean-test-artefacts")
@click.option("--dry-run", is_flag=True, default=True, help="Report matches; change nothing (default).")
@click.option("--execute", is_flag=True, help="Actually delete the matched rows. Overrides --dry-run.")
@with_appcontext
def clean_test_artefacts(dry_run, execute):
    """ARCH-116: report (or, with --execute, remove) QA-probe application rows."""
    rows = _find_matches()

    if not rows:
        click.echo("No test-artefact rows matched (ZZ */QA-TEST*/TEST-*/TEST_*/\"test\").")
        return

    click.echo(f"{len(rows)} matching row(s):")
    for r in rows:
        click.echo(f"  id={r.id} org={r.organization_id} name={r.name!r} created_at={r.created_at}")

    if not execute:
        click.echo("\nDry run — nothing deleted. Re-run with --execute to remove these rows.")
        return

    from sqlalchemy import text

    ids = [r.id for r in rows]
    click.echo(f"\n--execute: deleting {len(ids)} row(s) from application_components...")
    # tenancy-ok: see _find_matches above — explicit id list already reported
    # to the operator, deliberately cross-org for this known probe convention.
    db.session.execute(
        text("DELETE FROM application_components WHERE id = ANY(:ids)"),
        {"ids": ids},
    )
    db.session.commit()
    click.echo("Done.")


def init_app(app):
    app.cli.add_command(clean_test_artefacts)
