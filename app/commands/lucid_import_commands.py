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
    """Read a .json export or a .lucid archive, mirroring the upload route."""
    with open(path, "rb") as handle:
        raw = handle.read()

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
        return json.loads(raw.decode("utf-8"))
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
@click.option("--dry-run", is_flag=True, help="Report what would be written, write nothing.")
@click.option("--event-type", default="BusinessEvent",
              show_default=True, help="BusinessEvent or ApplicationEvent.")
@with_appcontext
def import_lucid(path, org_id, fallback_type, dry_run, event_type):
    """Import a Lucidchart diagram into the ArchiMate repository."""
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.models.organization import Organization
    from app.services.lucid_archimate_transformer import LucidArchiMateTransformer

    org = db.session.get(Organization, org_id)
    if org is None:
        raise click.ClickException(
            f"No organization with id {org_id}. Importing into a tenant that "
            f"does not exist would strand every row.")

    payload = _load_payload(path)
    try:
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
        return

    created = linked = 0
    lucid_id_to_db_id = {}
    skipped = []

    for element in elements:
        name, element_type = element.get("name"), element.get("type")
        if not name or not element_type:
            skipped.append(element.get("id"))
            continue

        existing = ArchiMateElement.query.filter_by(
            organization_id=org_id, name=name, type=element_type).first()
        if existing is not None:
            lucid_id_to_db_id[element["id"]] = existing.id
            linked += 1
            continue

        try:
            # A SAVEPOINT per row. A plain rollback() here would discard every
            # element created so far in this run, not just the one that failed -
            # and lucid_id_to_db_id would then hold ids for rows that no longer
            # exist, quietly attaching relationships to nothing.
            with db.session.begin_nested():
                row = ArchiMateElement(
                    name=name,
                    type=element_type,
                    layer=(element.get("layer") or "other"),
                    description=element.get("description"),
                    custom_properties=element.get("custom_properties") or {},
                    organization_id=org_id,
                )
                db.session.add(row)
                db.session.flush()
            lucid_id_to_db_id[element["id"]] = row.id
            created += 1
        except Exception as exc:  # noqa: BLE001 — report and continue
            click.echo(f"  ! could not create '{name[:60]}': {str(exc)[:110]}")
            skipped.append(element.get("id"))

    rels_created = 0
    rels_skipped = 0
    for relationship in relationships:
        source = lucid_id_to_db_id.get(relationship.get("source_id"))
        target = lucid_id_to_db_id.get(relationship.get("target_id"))
        if not source or not target:
            rels_skipped += 1
            continue

        # Re-running must not duplicate the estate's relationships either.
        exists = ArchiMateRelationship.query.filter_by(
            organization_id=org_id, source_id=source, target_id=target,
            type=relationship.get("type")
        ).first()
        if exists is not None:
            continue

        try:
            with db.session.begin_nested():
                db.session.add(ArchiMateRelationship(
                    type=relationship.get("type"),
                    source_id=source,
                    target_id=target,
                    description=relationship.get("description"),
                    # Both columns are varchar(200); a diagram label can be
                    # longer, and losing the tail beats losing the relationship.
                    access_mode=relationship.get("access_mode"),
                    flow_label=(relationship.get("flow_label") or None) and
                               relationship["flow_label"][:200],
                    custom_label=(relationship.get("custom_label") or None) and
                                 relationship["custom_label"][:200],
                    connection_spec=relationship.get("connection_spec") or {},
                    organization_id=org_id,
                ))
            rels_created += 1
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  ! could not create relationship: {str(exc)[:110]}")

    db.session.commit()

    click.echo(f"\n  elements      created {created}, linked to existing {linked}, "
               f"skipped {len(skipped)}")
    click.echo(f"  relationships created {rels_created}, "
               f"skipped {rels_skipped} (an endpoint did not import)")
    _summarise(elements, relationships)
    click.echo(
        "\n  Review what was guessed:\n"
        "    element types   -> custom_properties->>'lucid_type_source' = 'fallback'\n"
        "    relationships   -> derived_from 'stroke-stripped-label' was inferred "
        "from a line label\n"
    )


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
