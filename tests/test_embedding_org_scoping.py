"""Cross-tenant isolation and schema tests for organisation-scoped embeddings.

Every embedding table except document_chunk_embeddings (which already has
TenantMixin) must now carry an organisation_id column that can be used to scope
semantic searches to a single tenant.

Adds a nullable organisation column on the seven unscoped tables,
backfilled per organisation from the owning record where possible.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")

# The eight embedding tables
_EMBEDDING_TABLES = (
    "vendor_product_embeddings",
    "business_capability_embeddings",
    "process_embeddings",
    "chat_message_embeddings",
    "solution_embeddings",
    "vendor_organization_embeddings",
    "application_component_embeddings",
    "document_chunk_embeddings",
)


@pytest.fixture(scope="session", autouse=True)
def _ensure_embedding_org_columns(app):
    """Ensure the seven unscoped embedding tables carry organization_id.

    db.create_all() creates tables but never adds columns to existing ones,
    so the ORM columns from our model change must be reconciled before tests
    that actually insert data can work.
    """
    from sqlalchemy import inspect, text

    from app import db

    with app.app_context():
        inspector = inspect(db.engine)
        for table_name in _EMBEDDING_TABLES:
            cols = {c["name"] for c in inspector.get_columns(table_name)}
            if "organization_id" not in cols:
                db.session.execute(
                    text(
                        f'ALTER TABLE "{table_name}" '
                        f"ADD COLUMN IF NOT EXISTS organization_id "
                        f"INTEGER REFERENCES organizations(id) ON DELETE CASCADE"
                    )
                )

        # Migrate unique constraints from single-FK to composite (FK, org) so
        # two organisations can each have an embedding for the same entity.
        _COMPOSITE_UQ_MIGRATIONS = {
            "business_capability_embeddings": (
                "uq_capability_embedding",
                ["business_capability_id", "organization_id"],
            ),
        }
        for tbl, (uq_name, columns) in _COMPOSITE_UQ_MIGRATIONS.items():
            # Drop old single-column constraint
            db.session.execute(
                text(
                    f'ALTER TABLE "{tbl}" DROP CONSTRAINT IF EXISTS "{uq_name}"'
                )
            )
            # Create composite constraint
            col_list = ", ".join(f'"{c}"' for c in columns)
            db.session.execute(
                text(
                    f'ALTER TABLE "{tbl}" ADD CONSTRAINT "{uq_name}" '
                    f"UNIQUE ({col_list})"
                )
            )
        db.session.commit()


# ── Schema tests ───────────────────────────────────────────────────────────────


def test_all_embedding_tables_have_organization_id_column(app):
    """Every embedding model declares an organisation_id column (nullable)."""
    import app.models.vector_embeddings as m

    with app.app_context():
        models = [
            m.VendorProductEmbedding,
            m.BusinessCapabilityEmbedding,
            m.ProcessEmbedding,
            m.ChatMessageEmbedding,
            m.SolutionEmbedding,
            m.VendorOrganizationEmbedding,
            m.ApplicationComponentEmbedding,
            m.DocumentChunkEmbedding,
        ]
        for model_cls in models:
            col = model_cls.__table__.c.get("organization_id")
            assert col is not None, (
                f"{model_cls.__name__} is missing its organization_id column"
            )
            # DocumentChunkEmbedding uses TenantMixin which sets NOT NULL;
            # the seven other tables must be nullable (backfill-safe).
            if model_cls is not m.DocumentChunkEmbedding:
                assert col.nullable, (
                    f"{model_cls.__name__}.organization_id must be nullable"
                )


@pytest.mark.parametrize(
    "model_class",
    [
        "VendorProductEmbedding",
        "BusinessCapabilityEmbedding",
        "ProcessEmbedding",
        "ChatMessageEmbedding",
        "SolutionEmbedding",
        "VendorOrganizationEmbedding",
        "ApplicationComponentEmbedding",
    ],
)
def test_embedding_model_declares_organization_id(db_session, model_class):
    """Each model class declares the nullable organisation FK."""
    import app.models.vector_embeddings as m

    cls = getattr(m, model_class)
    col = cls.__table__.c.get("organization_id")
    assert col is not None, f"{model_class}.organization_id is missing"
    assert col.nullable, f"{model_class}.organization_id must be nullable"


# ── Cross-tenant isolation tests ──────────────────────────────────────────────


def _make_org_scoped_entity(db_session, model_class, org_id, **extra):
    """Create one embedding row for a given organisation.

    Uses the FK chain to create the owning entity first where needed.
    """
    from app.models.vector_embeddings import (
        ApplicationComponentEmbedding,
        BusinessCapabilityEmbedding,
        ChatMessageEmbedding,
        ProcessEmbedding,
        SolutionEmbedding,
        VendorOrganizationEmbedding,
        VendorProductEmbedding,
    )

    mapping = {
        "vendor_product": (
            VendorProductEmbedding,
            _make_vendor_product_embedding,
        ),
        "business_capability": (
            BusinessCapabilityEmbedding,
            _make_capability_embedding,
        ),
        "process": (ProcessEmbedding, _make_process_embedding),
        "chat_message": (
            ChatMessageEmbedding,
            _make_chat_message_embedding,
        ),
        "solution": (SolutionEmbedding, _make_solution_embedding),
        "vendor_organization": (
            VendorOrganizationEmbedding,
            _make_vendor_org_embedding,
        ),
        "application_component": (
            ApplicationComponentEmbedding,
            _make_app_component_embedding,
        ),
    }

    # Use the factory to create embedding with explicit org
    impl = mapping.get(model_class)
    if impl is None:
        pytest.fail(f"Unknown model class: {model_class}")

    row = impl[1](db_session, org_id)
    return row


def _make_business_capability(db_session, org_id):
    from app.models.business_capabilities import BusinessCapability

    bcap = BusinessCapability(
        organization_id=org_id,
        name=f"Test Capability {org_id}",
        code=f"TC-{org_id}",
        level=1,
    )
    db_session.add(bcap)
    db_session.flush()
    return bcap


def _make_capability_embedding(db_session, org_id):
    from app.models.vector_embeddings import BusinessCapabilityEmbedding

    bcap = _make_business_capability(db_session, org_id)
    emb = BusinessCapabilityEmbedding(
        business_capability_id=bcap.id,
        embedding_text=f"Org {org_id} capability text",
        organization_id=org_id,
    )
    db_session.add(emb)
    db_session.flush()
    return emb


def _make_solution(db_session, org_id):
    from app.models.solution_models import Solution

    sol = Solution(
        organization_id=org_id,
        name=f"Test Solution {org_id}",
    )
    db_session.add(sol)
    db_session.flush()
    return sol


def _make_solution_embedding(db_session, org_id):
    from app.models.vector_embeddings import SolutionEmbedding

    sol = _make_solution(db_session, org_id)
    emb = SolutionEmbedding(
        solution_id=sol.id,
        embedding_text=f"Org {org_id} solution text",
        organization_id=org_id,
    )
    db_session.add(emb)
    db_session.flush()
    return emb


def _make_application_component(db_session, org_id):
    from app.models.application_portfolio import ApplicationComponent

    appc = ApplicationComponent(
        organization_id=org_id,
        name=f"Test App {org_id}",
    )
    db_session.add(appc)
    db_session.flush()
    return appc


def _make_app_component_embedding(db_session, org_id):
    from app.models.vector_embeddings import ApplicationComponentEmbedding

    appc = _make_application_component(db_session, org_id)
    emb = ApplicationComponentEmbedding(
        application_component_id=appc.id,
        embedding_text=f"Org {org_id} app text",
        organization_id=org_id,
    )
    db_session.add(emb)
    db_session.flush()
    return emb


def _make_user(db_session, org_id):
    from app.models.user import User

    user = User(
        email=f"user_{org_id}@example.com",
        first_name="Test",
        last_name=f"User_{org_id}",
        organization_id=org_id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_chat_message_embedding(db_session, org_id):
    from app.models.vector_embeddings import ChatMessageEmbedding

    user = _make_user(db_session, org_id)
    emb = ChatMessageEmbedding(
        user_id=user.id,
        chat_session_id=f"sess-{org_id}",
        message_text=f"Org {org_id} message",
        message_role="user",
        organization_id=org_id,
    )
    db_session.add(emb)
    db_session.flush()
    return emb


def _make_vendor_product_embedding(db_session, org_id):
    """Vendor product embeddings are shared reference data (no org)."""
    from app.models.vector_embeddings import VendorProductEmbedding
    from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

    vendor = VendorOrganization(
        name=f"TestVendor-{org_id}",
        code=f"TV-{org_id}",
        seed_source_id=f"auto-{org_id}",
    )
    db_session.add(vendor)
    db_session.flush()
    product = VendorProduct(
        vendor_organization_id=vendor.id, name=f"TestProduct-{org_id}"
    )
    db_session.add(product)
    db_session.flush()
    emb = VendorProductEmbedding(
        vendor_product_id=product.id,
        embedding_text=f"Org {org_id} vendor product text",
        organization_id=org_id,
    )
    db_session.add(emb)
    db_session.flush()
    return emb


def _make_process_embedding(db_session, org_id):
    """Process embeddings are shared reference data (no org)."""
    from app.models.industry_apqc import IndustryAPQCFramework, IndustryAPQCProcess
    from app.models.vector_embeddings import ProcessEmbedding

    fw = IndustryAPQCFramework(
        industry_code=f"IND-{org_id}",
        industry_name=f"Industry {org_id}",
    )
    db_session.add(fw)
    db_session.flush()
    proc = IndustryAPQCProcess(
        industry_framework_id=fw.id,
        industry_process_code=f"TP-{org_id}",
        industry_process_name=f"TestProcess-{org_id}",
    )
    db_session.add(proc)
    db_session.flush()
    emb = ProcessEmbedding(
        process_id=proc.id,
        embedding_text=f"Org {org_id} process text",
        organization_id=org_id,
    )
    db_session.add(emb)
    db_session.flush()
    return emb


def _make_vendor_org_embedding(db_session, org_id):
    """Vendor org embeddings are shared reference data (no org)."""
    from app.models.vector_embeddings import VendorOrganizationEmbedding
    from app.models.vendor.vendor_organization import VendorOrganization

    vendor = VendorOrganization(
        name=f"VendorOrg-{org_id}",
        code=f"VO-{org_id}",
        seed_source_id=f"auto-{org_id}",
    )
    db_session.add(vendor)
    db_session.flush()
    emb = VendorOrganizationEmbedding(
        vendor_organization_id=vendor.id,
        embedding_text=f"Org {org_id} vendor text",
        organization_id=org_id,
    )
    db_session.add(emb)
    db_session.flush()
    return emb


@pytest.mark.parametrize(
    "model_key",
    [
        "business_capability",
        "solution",
        "application_component",
        "chat_message",
        "vendor_product",
        "process",
        "vendor_organization",
    ],
)
def test_embedding_select_respects_org_id(db_session, make_org, tenant_ctx, model_key):
    """A SELECT on org A's embedding table must not return org B's rows.

    Uses the production reader (PgvectorEmbeddingService) where available,
    or the scoped_embedding_query helper for tables without a dedicated reader.
    """
    org_a, org_b = make_org("a"), make_org("b")

    _make_org_scoped_entity(db_session, model_key, org_a.id)
    b_row = _make_org_scoped_entity(db_session, model_key, org_b.id)

    from app.services.pgvector_embedding_service import (
        PgvectorEmbeddingService,
        scoped_embedding_query,
    )
    from app.models.vector_embeddings import (
        ApplicationComponentEmbedding,
        BusinessCapabilityEmbedding,
        ChatMessageEmbedding,
        ProcessEmbedding,
        SolutionEmbedding,
        VendorOrganizationEmbedding,
        VendorProductEmbedding,
    )

    model_map = {
        "vendor_product": VendorProductEmbedding,
        "business_capability": BusinessCapabilityEmbedding,
        "process": ProcessEmbedding,
        "chat_message": ChatMessageEmbedding,
        "solution": SolutionEmbedding,
        "vendor_organization": VendorOrganizationEmbedding,
        "application_component": ApplicationComponentEmbedding,
    }
    model = model_map[model_key]

    with tenant_ctx(org_a.id):
        # Use the production scoped_embedding_query helper
        visible_ids = {r.id for r in scoped_embedding_query(model).all()}

    assert b_row.id not in visible_ids, (
        f"TENANT LEAK: org A can see org B's {model_key} embedding "
        f"(b_row.id={b_row.id} found in org A's query)"
    )


@pytest.mark.parametrize(
    "model_key",
    [
        "business_capability",
        "solution",
        "application_component",
        "chat_message",
        "vendor_product",
        "process",
        "vendor_organization",
    ],
)
def test_embedding_org_column_is_backfillable(
    db_session, make_org, model_key
):
    """The organization_id column accepts org values via direct assignment."""
    org = make_org("test")
    emb = _make_org_scoped_entity(db_session, model_key, org.id)
    assert emb.organization_id == org.id, (
        f"{model_key}: organization_id should be {org.id}, "
        f"got {emb.organization_id}"
    )


# ── Backfill test ──────────────────────────────────────────────────────────────


def test_backfill_embedding_organizations_fills_tenant_scoped_tables(
    db_session, make_org, app
):
    """_backfill_embedding_organizations fills org on rows whose FK chain
    reaches a tenant-scoped parent (business_capability, solution,
    application_component, user)."""
    from sqlalchemy import inspect

    from app.commands.reconcile_schema import _backfill_embedding_organizations

    org = make_org("backfill-test")
    from app.models.business_capabilities import BusinessCapability
    from app.models.solution_models import Solution
    from app.models.application_portfolio import ApplicationComponent
    from app.models.user import User
    from app.models.vector_embeddings import (
        ApplicationComponentEmbedding,
        BusinessCapabilityEmbedding,
        ChatMessageEmbedding,
        SolutionEmbedding,
    )

    # Create parent entities
    bcap = BusinessCapability(
        organization_id=org.id, name="B", code="B01", level=1
    )
    db_session.add(bcap)
    db_session.flush()

    sol = Solution(organization_id=org.id, name="S")
    db_session.add(sol)
    db_session.flush()

    appc = ApplicationComponent(organization_id=org.id, name="A")
    db_session.add(appc)
    db_session.flush()

    user = User(
        email="backfill@example.com",
        first_name="B",
        last_name="Fill",
        organization_id=org.id,
    )
    db_session.add(user)
    db_session.flush()

    # Create embeddings WITHOUT organization_id set (simulate pre-migration state)
    b_emb = BusinessCapabilityEmbedding(
        business_capability_id=bcap.id, embedding_text="test"
    )
    db_session.add(b_emb)
    s_emb = SolutionEmbedding(solution_id=sol.id, embedding_text="test")
    db_session.add(s_emb)
    a_emb = ApplicationComponentEmbedding(
        application_component_id=appc.id, embedding_text="test"
    )
    db_session.add(a_emb)
    c_emb = ChatMessageEmbedding(
        user_id=user.id,
        chat_session_id="sess-bf",
        message_text="test",
        message_role="user",
    )
    db_session.add(c_emb)
    db_session.flush()

    assert b_emb.organization_id is None
    assert s_emb.organization_id is None
    assert a_emb.organization_id is None
    assert c_emb.organization_id is None

    # Get existing table names via app context
    with app.app_context():
        from app import db as app_db
        inspector = inspect(app_db.engine)
        existing_tables = set(inspector.get_table_names())

        added, failed = [], []
        _backfill_embedding_organizations(
            dry_run=False,
            existing_tables=existing_tables,
            added=added,
            failed=failed,
        )

    db_session.refresh(b_emb)
    db_session.refresh(s_emb)
    db_session.refresh(a_emb)
    db_session.refresh(c_emb)

    assert b_emb.organization_id == org.id, (
        f"BusinessCapabilityEmbedding not backfilled: {b_emb.organization_id}"
    )
    assert s_emb.organization_id == org.id, (
        f"SolutionEmbedding not backfilled: {s_emb.organization_id}"
    )
    assert a_emb.organization_id == org.id, (
        f"ApplicationComponentEmbedding not backfilled: {a_emb.organization_id}"
    )
    assert c_emb.organization_id == org.id, (
        f"ChatMessageEmbedding not backfilled: {c_emb.organization_id}"
    )
    assert not failed, (
        f"backfill reported failures: {failed}"
    )


def test_backfill_embedding_organizations_skips_shared_tables(
    db_session, app
):
    """Shared-reference embedding tables have no org provenance; backfill
    reports but does not fail."""
    from sqlalchemy import inspect

    from app.commands.reconcile_schema import _backfill_embedding_organizations

    with app.app_context():
        from app import db as app_db
        inspector = inspect(app_db.engine)
        existing_tables = {t for t in _EMBEDDING_TABLES if t in inspector.get_table_names()}

        added, failed = [], []
        _backfill_embedding_organizations(
            dry_run=False,
            existing_tables=existing_tables,
            added=added,
            failed=failed,
        )

# No failures expected for shared-reference tables (they stay NULL
        # by design, no org provenance available -- not a bug).
        shared_failures = [f for f in failed if any(
            t in f for t in _EMBEDDING_TABLES
        )]
        assert not shared_failures, (
            "shared-reference embedding tables should not produce failures"
        )


# ── Organisation-scoped read path tests ────────────────────────────────────
# These verify that each read path in pgvector_embedding_service.py respects
# the organisation boundary. They would fail on code that queries without the
# organisation_id filter.


def _make_unscoped_bcap_embedding(db_session, org_id):
    """Create a BusinessCapabilityEmbedding row WITHOUT organisation_id
    (simulates pre-migration state)."""
    from app.models.business_capabilities import BusinessCapability
    from app.models.vector_embeddings import BusinessCapabilityEmbedding
    bcap = BusinessCapability(
        organization_id=org_id, name=f"ScopedCap {org_id}",
        code=f"SC-{org_id}", level=1,
    )
    db_session.add(bcap)
    db_session.flush()
    emb = BusinessCapabilityEmbedding(
        business_capability_id=bcap.id,
        embedding_text=f"org {org_id} capability",
        embedding=[0.1] * 384,
    )
    db_session.add(emb)
    db_session.flush()
    return emb, bcap


def test_search_capabilities_scoped_to_org(db_session, make_org, tenant_ctx):
    """search_capabilities must not return another org's capability embeddings."""
    org_a = make_org("search-cap-a")
    org_b = make_org("search-cap-b")
    emb_a, _ = _make_unscoped_bcap_embedding(db_session, org_a.id)
    emb_b, _ = _make_unscoped_bcap_embedding(db_session, org_b.id)

    from app.services.pgvector_embedding_service import PgvectorEmbeddingService
    svc = PgvectorEmbeddingService()

    with tenant_ctx(org_a.id):
        # Clear any cached embedding model to avoid generation errors;
        # the test path is _search_embeddings_python which does not need it.
        results = svc.search_capabilities("org a capability", limit=50, threshold=0.0)

    b_ids = {r[0] for r in results if r[0] == getattr(emb_b, 'business_capability_id', None)}
    assert not b_ids, (
        f"search_capabilities leaked org B's capability (b_cap_id={emb_b.business_capability_id})"
    )


def test_search_applications_scoped_to_org(db_session, make_org, tenant_ctx):
    """search_applications must not return another org's app embeddings."""
    from app.models.vector_embeddings import ApplicationComponentEmbedding
    org_a = make_org("search-app-a")
    org_b = make_org("search-app-b")

    from app.models.application_portfolio import ApplicationComponent
    appc_a = ApplicationComponent(organization_id=org_a.id, name=f"AppA-{org_a.id}")
    db_session.add(appc_a)
    db_session.flush()
    appc_b = ApplicationComponent(organization_id=org_b.id, name=f"AppB-{org_b.id}")
    db_session.add(appc_b)
    db_session.flush()

    emb_a = ApplicationComponentEmbedding(
        application_component_id=appc_a.id, embedding_text="org a app",
        embedding=[0.1] * 384,
    )
    db_session.add(emb_a)
    db_session.flush()
    emb_b = ApplicationComponentEmbedding(
        application_component_id=appc_b.id, embedding_text="org b app",
        embedding=[0.1] * 384,
    )
    db_session.add(emb_b)
    db_session.flush()

    from app.services.pgvector_embedding_service import PgvectorEmbeddingService
    svc = PgvectorEmbeddingService()

    with tenant_ctx(org_a.id):
        results = svc.search_applications("org a app", limit=50, threshold=0.0)

    b_ids = {r[0] for r in results if r[0] == emb_b.application_component_id}
    assert not b_ids, (
        f"search_applications leaked org B's app (app_id={emb_b.application_component_id})"
    )


def test_search_vendor_products_scoped_to_org(db_session, make_org, tenant_ctx):
    """search_vendor_products must not return another org's vendor product embeddings."""
    from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct
    from app.models.vector_embeddings import VendorProductEmbedding

    org_a = make_org("search-vp-a")
    org_b = make_org("search-vp-b")

    vendor_a = VendorOrganization(name=f"VendorA-{org_a.id}", code=f"VA-{org_a.id}", seed_source_id=f"ss-{org_a.id}")
    db_session.add(vendor_a)
    db_session.flush()
    product_a = VendorProduct(vendor_organization_id=vendor_a.id, name=f"ProdA-{org_a.id}")
    db_session.add(product_a)
    db_session.flush()
    emb_a = VendorProductEmbedding(
        vendor_product_id=product_a.id, embedding_text="org a product",
        embedding=[0.1] * 384, organization_id=org_a.id,
    )
    db_session.add(emb_a)
    db_session.flush()

    vendor_b = VendorOrganization(name=f"VendorB-{org_b.id}", code=f"VB-{org_b.id}", seed_source_id=f"ss-{org_b.id}")
    db_session.add(vendor_b)
    db_session.flush()
    product_b = VendorProduct(vendor_organization_id=vendor_b.id, name=f"ProdB-{org_b.id}")
    db_session.add(product_b)
    db_session.flush()
    emb_b = VendorProductEmbedding(
        vendor_product_id=product_b.id, embedding_text="org b product",
        embedding=[0.1] * 384, organization_id=org_b.id,
    )
    db_session.add(emb_b)
    db_session.flush()

    from app.services.pgvector_embedding_service import PgvectorEmbeddingService
    svc = PgvectorEmbeddingService()

    with tenant_ctx(org_a.id):
        results = svc.search_vendor_products("org a product", limit=50, threshold=0.0)

    b_ids = {r[0] for r in results if r[0] == emb_b.vendor_product_id}
    assert not b_ids, (
        f"search_vendor_products leaked org B's product (vp_id={emb_b.vendor_product_id})"
    )


def test_search_chat_history_scoped_to_org(db_session, make_org, tenant_ctx):
    """search_chat_history must not return another org's chat embeddings
    even when both rows share the same session_id."""
    from app.models.vector_embeddings import ChatMessageEmbedding

    org_a = make_org("chat-scope-a")
    org_b = make_org("chat-scope-b")

    from app.models.user import User
    user_a = User(email=f"chat-a@{org_a.id}.com", first_name="ChatA", last_name="User", organization_id=org_a.id)
    db_session.add(user_a)
    db_session.flush()

    # Both rows in the SAME session, different orgs
    emb_a = ChatMessageEmbedding(
        chat_session_id="shared-session", user_id=user_a.id,
        message_text="org a message", message_role="user",
        embedding=[0.1] * 384, organization_id=org_a.id,
    )
    db_session.add(emb_a)
    db_session.flush()

    emb_b = ChatMessageEmbedding(
        chat_session_id="shared-session", user_id=user_a.id,
        message_text="org b message", message_role="user",
        embedding=[0.1] * 384, organization_id=org_b.id,
    )
    db_session.add(emb_b)
    db_session.flush()

    from app.services.pgvector_embedding_service import PgvectorEmbeddingService
    svc = PgvectorEmbeddingService()

    with tenant_ctx(org_a.id):
        results = svc.search_chat_history("org a", chat_session_id="shared-session", limit=50, threshold=0.0)

    # search_chat_history returns dicts; check no message from org_b appears
    b_texts = [r["message"] for r in results if "org b" in r.get("message", "")]
    assert not b_texts, (
        f"search_chat_history leaked org B's messages: {b_texts}"
    )


def test_embedding_stats_scoped_to_org(db_session, make_org, tenant_ctx):
    """get_embedding_stats must count only the current organisation's rows."""
    from app.models.vector_embeddings import (
        BusinessCapabilityEmbedding,
        ProcessEmbedding,
    )

    org_a = make_org("stats-org-a")
    org_b = make_org("stats-org-b")

    # Create embedding rows for each org using inline models
    from app.models.business_capabilities import BusinessCapability
    bcap_a = BusinessCapability(
        organization_id=org_a.id, name="StatsCapA", code="SCA", level=1,
    )
    db_session.add(bcap_a)
    db_session.flush()
    emb_a = BusinessCapabilityEmbedding(
        business_capability_id=bcap_a.id, embedding_text="stats a",
        organization_id=org_a.id,
    )
    db_session.add(emb_a)
    db_session.flush()

    bcap_b = BusinessCapability(
        organization_id=org_b.id, name="StatsCapB", code="SCB", level=1,
    )
    db_session.add(bcap_b)
    db_session.flush()
    emb_b = BusinessCapabilityEmbedding(
        business_capability_id=bcap_b.id, embedding_text="stats b",
        organization_id=org_b.id,
    )
    db_session.add(emb_b)
    db_session.flush()

    from app.services.pgvector_embedding_service import PgvectorEmbeddingService
    svc = PgvectorEmbeddingService()

    with tenant_ctx(org_a.id):
        stats = svc.get_embedding_stats()

    assert stats.get("capability_embeddings", 0) == 1, (
        f"org A should see 1 capability embedding, got {stats.get('capability_embeddings')}"
    )


def test_generate_and_store_delete_respects_org(db_session, make_org, tenant_ctx):
    """generate_and_store's delete-before-insert uses the parent row's org."""
    from app.models.vector_embeddings import BusinessCapabilityEmbedding

    org_a = make_org("genstore-a")
    org_b = make_org("genstore-b")

    from app.models.business_capabilities import BusinessCapability
    bcap = BusinessCapability(
        organization_id=org_b.id, name="GenStoreCap", code="GSC", level=1,
    )
    db_session.add(bcap)
    db_session.flush()

    # Create an embedding row for org_b's entity
    emb_b = BusinessCapabilityEmbedding(
        business_capability_id=bcap.id, embedding_text="belongs to b",
        organization_id=org_b.id,
    )
    db_session.add(emb_b)
    db_session.flush()

    from app.services.pgvector_embedding_service import PgvectorEmbeddingService
    svc = PgvectorEmbeddingService()

    with tenant_ctx(org_a.id):
        # generate_and_store deletes by parent id alone and re-creates
        # with the parent row's org (org_b, not the caller's org_a)
        new_emb = svc.generate_and_store(
            entity_type="capability",
            entity_id=bcap.id,
            text="should use parent org",
            embedding_model_cls=BusinessCapabilityEmbedding,
            fk_field="business_capability_id",
        )

    assert new_emb is not None, "generate_and_store returned None"
    assert new_emb.organization_id == org_b.id, (
        f"generate_and_store should use parent row's org ({org_b.id}), "
        f"got {new_emb.organization_id}"
    )