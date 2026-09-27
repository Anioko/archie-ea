"""Value streams must be tenant-scoped and mirrored into the ArchiMate layer.

Both invariants were broken by the same workaround. ``create_value_stream``
used a Core-level INSERT to dodge an ``after_insert`` listener that read a
column the model did not have. A Core insert fires neither ORM mapper events
nor ``before_flush``, so the row got no ArchiMateElement *and* no
``organization_id``:

  * no ArchiMateElement -> the AI assistant, which reads the ArchiMate layer,
    reported "no value streams modelled" while the value-stream page listed
    them. The product contradicted itself.
  * no organization_id  -> the tenant filter compares with ``=``, which never
    matches NULL, so a value stream created through the UI vanished from the
    list as soon as it was saved.

See app/models/strategy_layer.py::create_archimate_value_stream.
"""

from app.modules.capabilities.services import value_stream_service as vs_service


def _create(name="Order to Cash"):
    return vs_service.create_value_stream({"name": name, "code": "OTC"})


def test_create_value_stream_sets_organization_id(db_session, make_org, tenant_ctx):
    """A value stream created in a tenant context belongs to that tenant."""
    org = make_org("vs-tenancy")

    with tenant_ctx(org.id):
        vs = _create()

    assert vs.organization_id == org.id, (
        "value stream created with organization_id=%r; the tenant filter uses "
        "`= org_id`, which never matches NULL, so the row would be invisible "
        "to the org that just created it" % (vs.organization_id,)
    )


def test_create_value_stream_creates_linked_archimate_element(
    db_session, make_org, tenant_ctx
):
    """ArchiMate is the backbone: the value stream *is* an ArchiMate element."""
    from app.models.models import ArchiMateElement

    org = make_org("vs-archimate")

    with tenant_ctx(org.id):
        vs = _create(name="Procure to Pay")

        assert vs.archimate_element_id is not None, (
            "no ArchiMateElement was created for the value stream; the AI "
            "assistant reads the ArchiMate layer and would report that no "
            "value streams exist"
        )

        element = db_session.get(ArchiMateElement, vs.archimate_element_id)

    assert element is not None
    assert element.name == "Procure to Pay"
    assert element.type == "ValueStream"
    assert element.layer == "Strategy"
    assert element.organization_id == org.id


def test_backfill_links_value_streams_created_before_the_fix(
    db_session, make_org, tenant_ctx
):
    """Rows written by the old Core-insert path get their element retroactively."""
    from app.commands.backfill_value_stream_archimate import (
        backfill_value_stream_archimate_elements,
    )
    from app.models.models import ArchiMateElement
    from app.models.unified_capability import ValueStream

    org = make_org("vs-backfill")

    with tenant_ctx(org.id):
        # Reproduce a pre-fix row exactly: a Core insert fires no mapper events,
        # so it lands with archimate_element_id NULL.
        inserted = db_session.execute(
            ValueStream.__table__.insert().values(
                name="Hire to Retire", organization_id=org.id
            )
        )
        vs_id = inserted.inserted_primary_key[0]
        db_session.flush()

        stats = backfill_value_stream_archimate_elements(org_id=org.id)
        assert stats["linked"] == 1

        db_session.expire_all()
        vs = db_session.get(ValueStream, vs_id)
        assert vs.archimate_element_id is not None

        element = db_session.get(ArchiMateElement, vs.archimate_element_id)
        assert element.name == "Hire to Retire"
        assert element.type == "ValueStream"
        assert element.organization_id == org.id

        # Idempotent: a second run finds nothing left to do and creates no duplicate.
        assert backfill_value_stream_archimate_elements(org_id=org.id)["linked"] == 0
