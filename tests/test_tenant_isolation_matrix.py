"""Prove tenant isolation empirically, and pin the models that opt out.

Multi-tenant leakage is the defect that ends an enterprise deal, and this
codebase enforces isolation through a SQLAlchemy event listener rather than
through query code - so nothing in a route tells you whether it is working. It
either applies or it silently does not.

This file asserts three things:

  1. TenantMixin actually filters. Two organisations, rows in each, and a query
     from inside one request context must never return the other's row. That is
     a positive control on the mechanism, not on any particular route.
  2. The set of models carrying organization_id WITHOUT the mixin is a fixed,
     justified list. Adding a new one is a decision someone has to make
     explicitly, not something that happens by omission.
  3. Bulk UPDATE and DELETE are documented as bypassing the filter entirely, and
     that remains true - so the documentation stays honest and anyone writing a
     bulk write knows they must scope it themselves.
  4. Every db.Model class under app/, including one with no organization_id
     column, is tenant-scoped, listed in INTENTIONALLY_GLOBAL with a reason, or
     named in a baseline of classifications still to be made. The baseline is a
     ratchet: it may only shrink, and a new model cannot be added to it.

The gap this closes was real: ApplicationDocument carries organization_id but no
mixin, and the delete handler forgot to scope, so any authenticated user could
destroy any tenant's document by walking integer ids.
"""

import os
import uuid

import pytest

pytestmark = pytest.mark.journey


# Models that are deliberately NOT tenant-scoped by TenantMixin: they carry
# organization_id without the mixin, or (WITHOUT_ORGANIZATION_COLUMN) have no
# organisation column at all. Each needs a reason, because the default answer
# for tenant data is the mixin.
INTENTIONALLY_GLOBAL = {
    # Authentication and platform administration must resolve across tenants.
    "User": "login resolves by email before an org context exists",
    "AuditLog": "platform-wide audit trail; scoping it would hide cross-tenant events",
    "SSOConfig": "read during authentication, before a tenant is known",
    "Subscription": "billing is administered platform-side",
    "UsageEvent": "metering is aggregated platform-side",
    "OrgRole": "role definitions are resolved during authorisation setup",
    "UserSession": (
        "a session row is looked up by sid on every authenticated request, before "
        "a tenant context exists, and revocation on logout or password change must "
        "reach the row regardless of the tenant filter; every query is keyed by "
        "sid or user_id and organization_id is kept for attribution only"
    ),
    # Child rows reached only through a TenantMixin parent, which scopes them.
    "ApplicationCapabilityMapping": "reached via ApplicationComponent, which is scoped",
    "ApplicationVersioning": "reached via ApplicationComponent, which is scoped",
    "DeploymentPipeline": "reached via ApplicationComponent, which is scoped",
    "ApplicationPerformanceMetrics": "reached via ApplicationComponent, which is scoped",
    "ApplicationOwner": "queried by user_id, which already implies one tenant",
    "ApplicationDocument": "reached via ApplicationComponent; handlers verify ownership",
    "ContractApplication": "join row between two scoped parents",
    # VendorProductCapability was listed here on the reasoning that the vendor
    # catalogue is shared. The catalogue is — VendorOrganization stays global —
    # but an assessment of how a product covers a business_capability is not:
    # that capability is tenant-owned, so the row describes one customer's
    # model. It now carries TenantMixin. See tests/test_vendor_tenancy_policy.py.
    "VendorProductPricing": "vendor catalogue is shared reference data",
    "SolutionScoringConfig": "scoring defaults are platform-level",
    "OrgConnectorConfig": "queried by explicit organization_id in every caller",
    "DevOpsConnectorConfig": "queried by explicit organization_id in every caller",
    "LucidchartConnectorConfig": "queried by explicit organization_id in every caller",
    # Wave-4 Phase B (ARB/EA tenant partitioning): these 3 are shared catalogs/
    # templates, not per-tenant governance data — see docs/superpowers/plans/
    # 2026-08-13-tenancy-wave-4.md Task 3. Their organization_id column exists
    # (Phase A, for schema symmetry with the sibling per-tenant models) but is
    # unused; TenantMixin would hide them from every org.
    "ARBGovernanceStandard": "shared governance standards catalogue, not org-owned",
    "ARBWorkflowStage": "shared workflow stage catalogue, not org-owned",
    "EAWorkflowDefinition": "shared workflow template catalogue, not org-owned",
    "ArtefactShareLink": (
        "owner actions explicitly scope by organization_id; the unauthenticated "
        "public token flow derives scope from the link"
    ),
    # Review queue children. ReviewQueueItem is the tenant-scoped parent.
    "ReviewDecision": (
        "no route or service may load a decision by id. A decision is loaded only "
        "through its ReviewQueueItem, which is tenant-scoped: the decisions route "
        "loads the parent under the tenant filter first and then reads by "
        "review_item_id, and a decision is created from a parent loaded the same "
        "way. A primary-key lookup can return a row already held in the session "
        "without applying the tenant filter, so a lookup by decision id would not "
        "be fenced; test_review_decisions_are_only_loaded_through_the_tenant_"
        "scoped_parent pins this"
    ),
    "ReviewQueueStatistics": (
        "no route or service reads or writes it; the statistics endpoints count the "
        "tenant-scoped ReviewQueueItem rows directly. Give it TenantMixin before "
        "any code stores per-organisation aggregates in it"
    ),
    "ErrorEvent": (
        "operational telemetry about the platform, not tenant data — a platform "
        "admin needs to see every organisation's errors to tell 'one customer hit "
        "a bug' from 'the deploy just broke everything'; organization_id/user_id "
        "are plain nullable columns kept for attribution, not filtering (see the "
        "model's own docstring, app/models/error_event.py)"
    ),
}


# Entries above that have no organization_id column on purpose: they are reached
# only through a tenant-scoped parent, or nothing reads them. Every other entry
# is a model that carries organization_id and deliberately does not get
# TenantMixin, and is flagged here when it stops carrying the column.
WITHOUT_ORGANIZATION_COLUMN = {"ReviewDecision", "ReviewQueueStatistics"}


UNCLASSIFIED_BASELINE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tenancy_unclassified_models.txt"
)


def _model_survey():
    """Every db.Model class under app/, as {name: {"paths", "tenant", "organization_column"}}.

    One survey for every check in this file. A class is a model when it lists
    db.Model as a base or inherits from another model class. It is tenant-scoped
    when TenantMixin is among its bases or it inherits from a scoped class, and
    it carries an organisation column when its own body assigns organization_id.
    A name defined in more than one place counts as scoped only if every
    definition is, and as carrying the column if any definition does.
    """
    import ast
    import io

    definitions = []  # (name, path, base names, lists db.Model directly, has organization_id)
    for dirpath, dirnames, filenames in os.walk("app"):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "tests")]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename).replace(os.sep, "/")
            try:
                tree = ast.parse(io.open(path, encoding="utf-8", errors="ignore").read())
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                bases, direct = set(), False
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.add(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.add(base.attr)
                        if base.attr == "Model" and getattr(base.value, "id", None) == "db":
                            direct = True
                column = False
                for statement in node.body:
                    if isinstance(statement, ast.Assign):
                        column = column or any(
                            isinstance(t, ast.Name) and t.id == "organization_id"
                            for t in statement.targets
                        )
                    elif isinstance(statement, ast.AnnAssign):
                        column = column or (
                            isinstance(statement.target, ast.Name)
                            and statement.target.id == "organization_id"
                        )
                definitions.append((node.name, path, bases, direct, column))

    model_names = {name for name, _p, _b, direct, _c in definitions if direct}
    tenant_names = {name for name, _p, bases, _d, _c in definitions if "TenantMixin" in bases}
    changed = True
    while changed:
        changed = False
        for name, _path, bases, _direct, _column in definitions:
            if name not in model_names and bases & model_names:
                model_names.add(name)
                changed = True
            if name not in tenant_names and bases & tenant_names:
                tenant_names.add(name)
                changed = True

    models = {}
    for name, path, bases, _direct, column in definitions:
        if name not in model_names:
            continue
        entry = models.setdefault(
            name, {"paths": set(), "tenant": True, "organization_column": False}
        )
        entry["paths"].add(path)
        entry["organization_column"] = entry["organization_column"] or column
        if "TenantMixin" not in bases and not bases & tenant_names:
            entry["tenant"] = False
    return {
        name: {
            "paths": sorted(entry["paths"]),
            "tenant": entry["tenant"],
            "organization_column": entry["organization_column"],
        }
        for name, entry in models.items()
    }


def _unprotected(models):
    """{name: path} of models that carry organization_id without TenantMixin."""
    return {
        name: entry["paths"][0]
        for name, entry in models.items()
        if entry["organization_column"] and not entry["tenant"]
    }


def _unclassified_models():
    """Models that are neither tenant-scoped nor listed in INTENTIONALLY_GLOBAL."""
    return {
        name: entry["paths"]
        for name, entry in _model_survey().items()
        if not entry["tenant"] and name not in INTENTIONALLY_GLOBAL
    }


def _unclassified_baseline():
    """Names still awaiting a tenancy classification (one per line, # comments)."""
    import io

    with io.open(UNCLASSIFIED_BASELINE, encoding="utf-8") as handle:
        return {
            line.strip() for line in handle if line.strip() and not line.startswith("#")
        }


def test_every_unscoped_model_is_a_deliberate_decision():
    """A new model must not silently join the unprotected set.

    Omitting TenantMixin is invisible in review - the model looks complete and
    the column is there. This turns the omission into a failing test that has to
    be answered with a reason.
    """
    unprotected = _unprotected(_model_survey())
    undocumented = sorted(set(unprotected) - set(INTENTIONALLY_GLOBAL))
    assert not undocumented, (
        "%d model(s) carry organization_id without TenantMixin and without a "
        "reason:\n  %s\n\nEither add TenantMixin, or add an entry to "
        "INTENTIONALLY_GLOBAL explaining why this data is not tenant-scoped."
        % (len(undocumented), "\n  ".join("%s (%s)" % (m, unprotected[m]) for m in undocumented))
    )


def test_the_justification_list_has_not_gone_stale():
    """An entry that no longer describes its model is misleading documentation."""
    models = _model_survey()
    listed = set(INTENTIONALLY_GLOBAL)

    gone = sorted(listed - set(models))
    assert not gone, "these justifications name models that no longer exist: %s" % gone

    now_tenant = sorted(name for name in listed if models[name]["tenant"])
    assert not now_tenant, (
        "these models now have TenantMixin but are still listed as intentionally "
        "global: %s - remove the entries" % now_tenant
    )

    lost_column = sorted(
        name for name in listed - WITHOUT_ORGANIZATION_COLUMN
        if not models[name]["organization_column"]
    )
    assert not lost_column, (
        "these entries are for models that carry organization_id, and they no longer "
        "do: %s - remove the entries, or, if the model has no organisation column on "
        "purpose, add it to WITHOUT_ORGANIZATION_COLUMN with the reason in its entry"
        % lost_column
    )

    unlisted = sorted(WITHOUT_ORGANIZATION_COLUMN - listed)
    assert not unlisted, (
        "WITHOUT_ORGANIZATION_COLUMN names models that have no INTENTIONALLY_GLOBAL "
        "entry: %s" % unlisted
    )
    gained_column = sorted(
        name for name in WITHOUT_ORGANIZATION_COLUMN if models[name]["organization_column"]
    )
    assert not gained_column, (
        "these models have no organisation column on purpose but now declare "
        "organization_id: %s - decide whether they should have TenantMixin, and move "
        "them out of WITHOUT_ORGANIZATION_COLUMN" % gained_column
    )


def test_no_model_joins_the_estate_unclassified():
    """Every model is tenant-scoped or carries a recorded decision.

    The automatic tenant filter applies to TenantMixin models, so a model
    without it has to be scoped by each caller. The models still to be classified
    are recorded in tenancy_unclassified_models.txt; a model that is not in it,
    not tenant-scoped and not in INTENTIONALLY_GLOBAL fails here.
    """
    paths = _unclassified_models()
    new = sorted(set(paths) - _unclassified_baseline())
    assert not new, (
        "%d model(s) are neither tenant-scoped nor classified:\n  %s\n\n"
        "The automatic tenant filter applies only to TenantMixin models. Either "
        "give it TenantMixin (a nullable organization_id "
        "column plus a backfill, as ReviewQueueItem does), or add it to "
        "INTENTIONALLY_GLOBAL in this file with the reason it is not tenant data, "
        "for example that it is reached only through a scoped parent. Do not add "
        "it to tenancy_unclassified_models.txt."
        % (len(new), "\n  ".join("%s (%s)" % (m, ", ".join(paths[m])) for m in new))
    )


def test_the_unclassified_baseline_only_shrinks():
    """Ratchet: a classified model leaves the baseline, so the count only falls."""
    current = set(_unclassified_models())
    stale = sorted(_unclassified_baseline() - current)
    assert not stale, (
        "%d model(s) in tenancy_unclassified_models.txt are now tenant-scoped, "
        "listed in INTENTIONALLY_GLOBAL, or no longer exist - remove these lines "
        "so the count keeps falling:\n  %s" % (len(stale), "\n  ".join(stale))
    )


def test_review_queue_models_are_classified():
    """The review queue models are tenant-scoped or explained, not unclassified."""
    models = _model_survey()
    assert models["ReviewQueueItem"]["tenant"], (
        "ReviewQueueItem must inherit TenantMixin so the tenant filter applies to it")
    for name in ("ReviewDecision", "ReviewQueueStatistics"):
        assert name in INTENTIONALLY_GLOBAL, "%s needs a documented tenancy decision" % name
        assert name in WITHOUT_ORGANIZATION_COLUMN
    unclassified = set(_unclassified_models()) | _unclassified_baseline()
    for name in ("ReviewQueueItem", "ReviewDecision", "ReviewQueueStatistics"):
        assert name not in unclassified, "%s is still awaiting a classification" % name


def _references_to(name):
    """{(file, function): [AST nodes]} for every use of a model class outside its module."""
    import ast
    import io

    found = {}

    class Visitor(ast.NodeVisitor):
        def __init__(self, path):
            self.path, self.functions = path, []

        def _function(self, node):
            self.functions.append(node.name)
            self.generic_visit(node)
            self.functions.pop()

        visit_FunctionDef = visit_AsyncFunctionDef = _function

        def _record(self, node):
            where = (self.path, self.functions[-1] if self.functions else "<module>")
            found.setdefault(where, []).append(node)

        def visit_Name(self, node):
            if node.id == name:
                self._record(node)

        def visit_Attribute(self, node):
            if node.attr == name:
                self._record(node)
            self.generic_visit(node)

    for dirpath, dirnames, filenames in os.walk("app"):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "tests")]
        for filename in filenames:
            path = os.path.join(dirpath, filename).replace(os.sep, "/")
            if not filename.endswith(".py") or path == "app/models/confidence_review.py":
                continue
            try:
                tree = ast.parse(io.open(path, encoding="utf-8", errors="ignore").read())
            except (OSError, SyntaxError):
                continue
            Visitor(path).visit(tree)
    return found


def _first_line(path, function, guard_call, guard_argument):
    """Line of the first call to ``guard_call(guard_argument, ...)`` inside a function."""
    import ast
    import io

    tree = ast.parse(io.open(path, encoding="utf-8").read())
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function:
            for call in ast.walk(node):
                if (
                    isinstance(call, ast.Call)
                    and getattr(call.func, "id", getattr(call.func, "attr", None)) == guard_call
                    and call.args
                    and getattr(call.args[0], "id", None) == guard_argument
                ):
                    lines.append(call.lineno)
    return min(lines) if lines else None


def test_review_decisions_are_only_loaded_through_the_tenant_scoped_parent():
    """No route or service loads a ReviewDecision by id.

    ReviewDecision has no organisation column of its own; it is fenced through
    its tenant-scoped ReviewQueueItem. That holds only while a decision is read
    after its parent has been loaded under the tenant filter, and only by the
    parent's id. A primary-key lookup can return a row already held in the
    session without applying the tenant filter, so a lookup by decision id would
    not be fenced. This pins the two places that touch the model and the shape of
    their use.
    """
    found = _references_to("ReviewDecision")
    reader = ("app/api/confidence_review_routes.py", "get_review_item_decisions")
    writer = ("app/services/confidence_review_service.py", "submit_review_decision")
    assert set(found) == {reader, writer}, (
        "ReviewDecision may only be used by the decisions route (reading) and "
        "submit_review_decision (creating); found it in: %s. Load decisions through "
        "their tenant-scoped ReviewQueueItem, never by the decision's own id, or give "
        "ReviewDecision TenantMixin." % sorted(found)
    )

    # Reading: the parent is loaded first, and decisions are selected by the
    # parent's id only.
    parent = _first_line(reader[0], reader[1], "require_entity", "ReviewQueueItem")
    assert parent is not None, "the decisions route must load its ReviewQueueItem first"
    assert all(node.lineno > parent for node in found[reader])

    # Creating: the parent is loaded first too, and the constructor is the only use.
    parent = _first_line(writer[0], writer[1], "load_entity", "ReviewQueueItem")
    assert parent is not None, "submit_review_decision must load its ReviewQueueItem first"
    assert all(node.lineno > parent for node in found[writer])


def test_the_decisions_route_selects_decisions_by_the_parents_id_only():
    """The one read of ReviewDecision filters on review_item_id and nothing else."""
    import ast
    import io

    path, function = "app/api/confidence_review_routes.py", "get_review_item_decisions"
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    node = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == function
    )
    chains = []
    for call in ast.walk(node):
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
            continue
        root = call.func.value
        while isinstance(root, (ast.Attribute, ast.Call)):
            root = root.value if isinstance(root, ast.Attribute) else root.func
        if getattr(root, "id", None) == "ReviewDecision":
            chains.append(call)
    methods = {call.func.attr for call in chains}
    assert methods <= {"filter_by", "order_by", "desc", "all"}, (
        "the decisions route may only filter_by, order_by, desc and all on ReviewDecision; "
        "found %s" % sorted(methods)
    )
    for call in chains:
        if call.func.attr == "filter_by":
            assert {k.arg for k in call.keywords} == {"review_item_id"}, (
                "decisions must be selected by review_item_id only"
            )


@pytest.fixture(scope="module")
def app():
    import os

    os.environ.setdefault("SECRET_KEY", "x" * 32)
    from app import create_app, db

    application = create_app("testing")
    with application.app_context():
        db.create_all()
    return application


def test_tenant_mixin_actually_filters_reads(app):
    """The positive control: prove the mechanism, not a route that uses it.

    Isolation here is an ORM event listener. If it stopped applying, every route
    would keep returning 200 and quietly serve other tenants' rows.
    """
    from app import db
    from app.models.application_portfolio import ApplicationComponent
    from app.models.organization import Organization

    marker = uuid.uuid4().hex[:8]
    with app.app_context():
        org_a = Organization(name="Iso A %s" % marker, slug="iso-a-%s" % marker)
        org_b = Organization(name="Iso B %s" % marker, slug="iso-b-%s" % marker)
        db.session.add_all([org_a, org_b])
        db.session.commit()
        a_id, b_id = org_a.id, org_b.id

        db.session.add_all([
            ApplicationComponent(name="A-only %s" % marker, organization_id=a_id),
            ApplicationComponent(name="B-only %s" % marker, organization_id=b_id),
        ])
        db.session.commit()

    # Inside a request bound to org A, org B's row must be invisible.
    with app.test_request_context():
        from flask import g

        g.current_org_id = a_id
        visible = {c.name for c in ApplicationComponent.query.filter(
            ApplicationComponent.name.like("%" + marker)).all()}

    assert ("A-only %s" % marker) in visible, (
        "tenant A cannot see its own row - the filter is over-applying")
    assert ("B-only %s" % marker) not in visible, (
        "TENANT LEAK: a request scoped to org %d returned org %d's row. "
        "The isolation listener is not applying." % (a_id, b_id))


def test_bulk_delete_is_tenant_filtered(app):
    """ADR-0003 gap 1 is closed: a bulk DELETE cannot cross tenants.

    This test previously pinned the opposite — do_orm_execute returned early for
    non-SELECT, so a bulk DELETE carried no tenant predicate — and its own
    docstring said that if it ever started passing, CLAUDE.md and the callers
    relying on that guidance needed revisiting. That is exactly what happened:
    the listener now applies with_loader_criteria to ORM-enabled UPDATE and
    DELETE as well, CLAUDE.md's bulk-write paragraph has been rewritten, and the
    two strict xfails in tests/test_tenant_isolation.py are plain passes.

    Bulk writes should still carry organization_id explicitly as
    defence-in-depth: raw SQL and anything outside a request context remain
    unfiltered (gap 2, by design).
    """
    from app import db
    from app.models.application_portfolio import ApplicationComponent
    from app.models.organization import Organization

    marker = uuid.uuid4().hex[:8]
    with app.app_context():
        org_a = Organization(name="Bulk A %s" % marker, slug="bulk-a-%s" % marker)
        org_b = Organization(name="Bulk B %s" % marker, slug="bulk-b-%s" % marker)
        db.session.add_all([org_a, org_b])
        db.session.commit()
        a_id, b_id = org_a.id, org_b.id
        db.session.add(ApplicationComponent(name="bulk-target %s" % marker,
                                            organization_id=b_id))
        db.session.commit()

    with app.test_request_context():
        from flask import g

        g.current_org_id = a_id
        # Bulk delete issued from tenant A, targeting a row owned by B, with no
        # organization_id of its own in the predicate — the mechanism must supply it.
        deleted = ApplicationComponent.query.filter(
            ApplicationComponent.name == "bulk-target %s" % marker
        ).delete(synchronize_session=False)
        db.session.commit()

    assert deleted == 0, (
        "TENANT LEAK: a bulk DELETE issued in org %d's context matched org %d's "
        "row. do_orm_execute is not applying the tenant filter to DELETE." % (a_id, b_id))

    # And the row is genuinely still there, read back as its owner.
    with app.test_request_context():
        from flask import g

        g.current_org_id = b_id
        survivor = ApplicationComponent.query.filter(
            ApplicationComponent.name == "bulk-target %s" % marker
        ).one_or_none()
        assert survivor is not None, "org B's row was destroyed by org A's bulk delete"

    # This test commits real rows; clean them up rather than leaving residue in
    # the shared test database (the 540 stale organisations in it came from
    # exactly this pattern).
    with app.app_context():
        ApplicationComponent.query.filter(
            ApplicationComponent.name == "bulk-target %s" % marker
        ).delete(synchronize_session=False)
        Organization.query.filter(Organization.id.in_([a_id, b_id])).delete(
            synchronize_session=False)
        db.session.commit()
