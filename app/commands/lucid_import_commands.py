"""flask import-lucid — load a Lucidchart export into the ArchiMate repository.

The composer's Lucidchart import returns a payload for the browser to persist.
That is right for someone working in the canvas and wrong for the job an
architect actually has at the start of an engagement: take the existing landscape
diagram and pre-populate the repository with it, once, headlessly, so the
capability and application work has something real to hang off.

    flask --app manage import-lucid "To-Be Solution Diagram.json" --dry-run
    flask --app manage import-lucid "To-Be Solution Diagram.json" \
        --fallback-type ApplicationComponent

Accepts the same inputs as the HTTP route: a Lucid JSON export, or a native
.lucid archive (a ZIP holding document.json).

Elements are de-duplicated on (organization_id, name, type), matching the OEF
importer, so re-running against an updated diagram links to what is already
there rather than creating a second copy of the estate.

--org-id is required and is not a formality. The ArchiMateElement model class
does not declare organization_id, but the table has it NOT NULL - one of the
tables mapped by two model classes via extend_existing. A CLI runs outside a
request, so there is no g.current_org_id to fall back on: without an explicit
org every insert fails, and every de-duplication lookup would otherwise reach
across tenants and link this import to another customer's estate.
"""
import json
import os

import click
from flask.cli import with_appcontext

from app import db


def _load_payload(path):
    """Read a .json export, a .lucid archive, or a Visio .vsdx.

    Returns (payload, kind). A .vsdx is handed back as raw bytes because its
    transformer opens the package itself.
    """
    with open(path, "rb") as handle:
        raw = handle.read()

    if path.lower().endswith(".vsdx"):
        return raw, "visio"

    # A native .lucid file is a ZIP whose document.json holds the diagram.
    if raw[:2] == b"PK":
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
            member = next(
                (n for n in names if n.lower().rstrip("/").endswith("document.json")),
                None,
            ) or next((n for n in names if n.lower().endswith(".json")), None)
            if not member:
                raise click.ClickException("The .lucid archive has no document.json.")
            raw = archive.read(member)

    try:
        return json.loads(raw.decode("utf-8")), "lucid"
    except (UnicodeDecodeError, ValueError) as exc:
        raise click.ClickException(f"Not valid Lucidchart JSON: {exc}") from exc


@click.command("import-lucid")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--org-id", type=int, required=True,
              help="Organization to import into. Required: a CLI has no request "
                   "context, so nothing can infer the tenant, and the table "
                   "requires it.")
@click.option(
    "--fallback-type",
    default=None,
    help="Import shapes drawn without ArchiMate stencils as this element type "
         "(e.g. ApplicationComponent). Containers become Grouping. Omit to skip "
         "them, which is the safe default.",
)
@click.option(
    "--dedupe",
    type=click.Choice(["name-type", "name-type-container", "none"]),
    default="name-type",
    show_default=True,
    help="How an incoming element is matched to one already in the repository. "
         "name-type merges same-named elements of the same type - correct for a "
         "repository, but it collapses the five INTERNET nodes on a landscape "
         "diagram into one. name-type-container additionally requires the same "
         "containing Location, so INTERNET in Crefo DC stays distinct from "
         "INTERNET in IBM Cloud. none imports everything as drawn.",
)
@click.option("--link-applications/--no-link-applications", default=True, show_default=True,
              help="Point matching portfolio applications at their imported ArchiMate "
                   "element, so the landscape and the portfolio are the same estate.")
@click.option("--create-applications", is_flag=True,
              help="Also create a portfolio application for every imported "
                   "ApplicationComponent that has none. Off by default: an import "
                   "should not invent portfolio entries unasked.")
@click.option("--dry-run", is_flag=True, help="Report what would be written, write nothing.")
@click.option("--event-type", default="BusinessEvent",
              show_default=True, help="BusinessEvent or ApplicationEvent.")
@with_appcontext
def import_lucid(path, org_id, fallback_type, dedupe, link_applications,
                 create_applications, dry_run, event_type):
    """Import a Lucidchart diagram into the ArchiMate repository."""
    from app.models.organization import Organization
    from app.services.lucid_archimate_transformer import LucidArchiMateTransformer

    org = db.session.get(Organization, org_id)
    if org is None:
        raise click.ClickException(
            f"No organization with id {org_id}. Importing into a tenant that "
            f"does not exist would strand every row.")

    payload, kind = _load_payload(path)
    try:
        if kind == "visio":
            from app.services.visio_archimate_transformer import VisioArchiMateTransformer
            transformer = VisioArchiMateTransformer(
                event_element_type=event_type, fallback_element_type=fallback_type
            )
        else:
            transformer = LucidArchiMateTransformer(
                event_element_type=event_type, fallback_element_type=fallback_type
            )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    result = transformer.transform_document(payload)
    elements = result.get("elements") or []
    relationships = result.get("relationships") or []

    click.echo(f"\n{os.path.basename(path)} -> {result.get('model_name')}")
    click.echo(f"  {len(elements)} element(s), {len(relationships)} relationship(s) parsed")
    for warning in result.get("warnings") or []:
        click.echo(f"  ! {warning}")

    if dry_run:
        click.echo("\n  --dry-run: nothing written.")
        _summarise(elements, relationships)
        _report_conformance(elements, relationships)
        return

    from app.services.lucid_import_service import import_payload

    # One implementation, two front doors. The import screen calls exactly this,
    # so the CLI cannot quietly diverge from what an architect sees in the UI.
    report = import_payload(
        result, org_id=org_id, dedupe=dedupe,
        link_applications=link_applications,
        create_applications=create_applications,
        preview=False,
    )

    counts = report["counts"]["elements"]
    rel_counts = report["counts"]["relationships"]
    apps = report["applications"]

    click.echo("\n  elements      created %d, linked to existing %d, refreshed %d, skipped %d"
               % (counts.get("created", 0), counts.get("linked", 0),
                  counts.get("changed", 0), counts.get("skipped", 0)))
    click.echo("  relationships created %d, linked %d, provenance recorded %d, skipped %d"
               % (rel_counts.get("created", 0), rel_counts.get("linked", 0),
                  rel_counts.get("changed", 0), rel_counts.get("skipped", 0)))
    if link_applications:
        click.echo("  portfolio     linked %d, created %d, already linked %d"
                   % (apps["linked"], apps["created"], apps["already_linked"]))
        if not create_applications and not apps["linked"] and not apps["created"]:
            click.echo("                nothing matched by name - pass --create-applications "
                       "to populate the portfolio from this diagram")

    _summarise(elements, relationships)
    _report_conformance(elements, relationships)
    click.echo(
        "\n  Review what was guessed:\n"
        "    element types -> custom_properties->>'lucid_type_source' = 'fallback'\n"
        "    relationships -> derived_from is set\n"
        "    or open /archimate/import-review\n"
    )


def _link_applications(org_id, element_rows, create_missing):
    """Connect imported ApplicationComponents to the application portfolio.

    Without this the import is a museum: 74 elements in the ArchiMate tables and
    an element catalogue reporting "not linked to any solution: 74". The
    portfolio is where lifecycle, ownership, cost and vendor live, and an
    application landscape diagram is precisely a list of applications - the two
    should not be strangers after an import.

    Matching is by name within the organisation, and only ever fills an EMPTY
    archimate_element_id. An application already pointing at an element was
    linked by a person or an earlier run; silently repointing it would rewrite
    a decision this command did not make.
    """
    from app.models.application_portfolio import ApplicationComponent as PortfolioApp

    linked = created = already = 0
    for element_type, name, element_id in element_rows:
        if element_type != "ApplicationComponent":
            continue
        app_row = PortfolioApp.query.filter_by(
            organization_id=org_id, name=name).first()

        if app_row is None:
            if not create_missing:
                continue
            try:
                with db.session.begin_nested():
                    app_row = PortfolioApp(
                        name=name,
                        organization_id=org_id,
                        archimate_element_id=element_id,
                    )
                    db.session.add(app_row)
                    db.session.flush()
                created += 1
            except Exception as exc:  # noqa: BLE001
                click.echo(f"  ! could not create application '{name[:50]}': {str(exc)[:90]}")
            continue

        if app_row.archimate_element_id:
            already += 1
            continue
        try:
            with db.session.begin_nested():
                app_row.archimate_element_id = element_id
            linked += 1
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  ! could not link '{name[:50]}': {str(exc)[:90]}")

    return linked, created, already


def _conformance(elements, relationships):
    """Check every relationship against the ArchiMate 3.2 matrix.

    An import is the moment a repository fills up with assertions nobody has
    checked. A diagram is drawn to communicate, not to conform: it will contain
    relationships the specification does not allow between those two concept
    types, and the honest thing is to say so at load time rather than let a
    conformance report discover it months later.

    Reported, never rejected. The diagram is the customer's record of their
    estate; refusing to import it because an edge is non-conformant would lose
    real architecture to a modelling technicality.
    """
    try:
        from app.config.archimate_relationship_matrix import (  # noqa: PLC0415
            ALL_ELEMENTS,
            get_valid_relationships,
            is_valid_relationship,
        )
    except Exception:  # noqa: BLE001
        return None

    types = {e.get("id"): e.get("type") for e in elements}
    ok = unknown = 0
    violations = []
    for rel in relationships:
        source = types.get(rel.get("source_id"))
        target = types.get(rel.get("target_id"))
        if not source or not target:
            continue
        if source not in ALL_ELEMENTS or target not in ALL_ELEMENTS:
            unknown += 1
            continue
        if is_valid_relationship(source, target, rel.get("type") or ""):
            ok += 1
        else:
            violations.append((source, rel.get("type"), target,
                               get_valid_relationships(source, target)))
    return {"ok": ok, "unknown": unknown, "violations": violations}


def _report_conformance(elements, relationships):
    report = _conformance(elements, relationships)
    if report is None:
        click.echo("\n  conformance: matrix unavailable, not checked")
        return
    total = report["ok"] + report["unknown"] + len(report["violations"])
    click.echo(f"\n  ArchiMate 3.2 conformance: {report['ok']}/{total} relationship(s) "
               f"permitted by the specification")
    if report["unknown"]:
        click.echo(f"     {report['unknown']} involve a concept the matrix does not model")
    if not report["violations"]:
        return
    click.echo(f"     {len(report['violations'])} not permitted between those concept types:")
    seen = set()
    for source, rel_type, target, allowed in report["violations"]:
        key = (source, rel_type, target)
        if key in seen:
            continue
        seen.add(key)
        suggestion = ", ".join(allowed[:3]) if allowed else "no relationship is permitted"
        click.echo(f"       {source} --{rel_type}--> {target}   (permitted: {suggestion})")
        if len(seen) >= 8:
            click.echo(f"       ... and {len(report['violations']) - 8} more")
            break
    click.echo("     Imported anyway - a diagram is drawn to communicate, not to conform.")


def _summarise(elements, relationships):
    from collections import Counter

    if elements:
        click.echo("\n  by element type:")
        for name, count in Counter(e.get("type") for e in elements).most_common():
            click.echo(f"     {name:<24} {count}")
    if relationships:
        click.echo("  by relationship type:")
        for name, count in Counter(r.get("type") for r in relationships).most_common():
            click.echo(f"     {name:<24} {count}")


def register_lucid_import_commands(app):
    """Register the Lucidchart import CLI command."""
    app.cli.add_command(import_lucid)
