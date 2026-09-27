"""DEF-067, Capgemini dry-run pass 3: element delete gave a 200-but-still-
listed result on the card path and "Invalid request parameters" on the
detail path. Root-caused to archimate_relationships.source_id/target_id
carrying ON DELETE NO ACTION with no application-side cleanup, so any
element with a relationship raised an IntegrityError on commit that the
route's except swallowed into a misleading message. The route now clears
relationships referencing the element first, and reports a safe (not raw
exception) message on genuine failure.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_delete_equipment_with_relationship_succeeds_and_cleans_up(app, db_session, make_org, tenant_ctx):
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.models.physical_layer import PhysicalEquipment
    from app.models.user import User

    org = make_org("def067-equipment-delete")
    with tenant_ctx(org.id):
        el = PhysicalEquipment(name="ZZ-VERIFY Equipment Delete Test", organization_id=org.id)
        db_session.add(el)
        db_session.commit()
        ae_id = el.archimate_element_id
        el_id = el.id

        other = ArchiMateElement(name="ZZ-VERIFY Other End", type="ApplicationComponent",
                                  organization_id=org.id)
        db_session.add(other)
        db_session.commit()
        db_session.add(ArchiMateRelationship(type="Serving", source_id=ae_id, target_id=other.id))
        db_session.commit()

        user = User(email=f"def067eq-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.post(
                f"/architecture/physical/Equipment/{el_id}/delete",
                headers={"Accept": "application/json"},
                content_type="application/json",
                data="{}",
            )
            assert resp.status_code == 200, resp.get_data(as_text=True)
            body = resp.get_data(as_text=True)
            assert "psycopg2" not in body and "IntegrityError" not in body

            assert db_session.get(PhysicalEquipment, el_id) is None
            assert db_session.get(ArchiMateElement, ae_id) is None
            remaining = ArchiMateRelationship.query.filter(
                (ArchiMateRelationship.source_id == ae_id) | (ArchiMateRelationship.target_id == ae_id)
            ).count()
            assert remaining == 0


@pytest.mark.usefixtures("db_session")
def test_delete_via_archimate_id_also_removes_dedicated_duplicate(app, db_session, make_org, tenant_ctx):
    """DEF-067's actual live failure: production's dashboard card links to
    the ArchiMateElement's own id (a DEF-004 duplicate scenario), which is a
    *different* id than the dedicated model row's id. Deleting via that id
    falls into the `_from_ae` branch, which used to delete only the
    ArchiMateElement — leaving the dedicated row (a different id, still
    holding a NO-ACTION FK into the row just deleted) causing a
    ForeignKeyViolation. Confirmed via production server logs:
    "stakeholders_archimate_element_id_fkey ... Key (id)=(1287) is still
    referenced from table stakeholders" where stakeholders.id=2, not 1287.
    """
    from app.models.motivation import Stakeholder
    from app.models.archimate_core import ArchiMateElement
    from app.models.user import User

    org = make_org("def067-mismatched-ids")
    with tenant_ctx(org.id):
        # Build the exact shape: a Stakeholder row whose own id differs from
        # the ArchiMateElement id it points at.
        stakeholder = Stakeholder(name="ZZ-VERIFY Mismatched IDs")
        db_session.add(stakeholder)
        db_session.commit()
        stakeholder_id = stakeholder.id

        ae = ArchiMateElement(name="ZZ-VERIFY Mismatched IDs", type="Stakeholder",
                               organization_id=org.id)
        db_session.add(ae)
        db_session.commit()
        ae_id = ae.id
        assert ae_id != stakeholder_id, "test setup must produce different ids to reproduce"

        stakeholder.archimate_element_id = ae_id
        db_session.commit()

        user = User(email=f"def067mm-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            # Delete via the ArchiMateElement's own id, exactly as the
            # production dashboard card does for a duplicated element.
            resp = c.post(
                f"/architecture/motivation/Stakeholder/{ae_id}/delete",
                headers={"Accept": "application/json"},
                content_type="application/json",
                data="{}",
            )
            assert resp.status_code == 200, resp.get_data(as_text=True)
            body = resp.get_data(as_text=True)
            assert "psycopg2" not in body and "IntegrityError" not in body

            assert db_session.get(ArchiMateElement, ae_id) is None
            assert db_session.get(Stakeholder, stakeholder_id) is None
