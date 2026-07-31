"""A tenant must not be able to destroy another tenant's documents.

ApplicationDocument carries organization_id but is a plain db.Model, not a
TenantMixin one, so no WHERE organization_id = ... is injected and
.query.get_or_404() returns any tenant's row. Every handler therefore has to
check ownership itself.

Until 2026-07-31 the read path did and the delete path did not:

    download_document_file()  -> verify_file_access(parent_app.organization_id)
    delete_document_file()    -> (nothing)

so any authenticated user could walk integer ids and permanently remove another
tenant's document - the database row and the file on disk. Deletion is not
recoverable, which makes the omission worse on this path than on the read one
that was protected.

Both layouts register a delete route - /applications/... from app/modules/ and
/dashboard/... from the legacy app/application_mgmt/ - so fixing one left the
same hole open under a different URL. This asserts against the URL map for that
reason: it is the only view that sees both.
"""

import inspect
import re

import pytest

pytestmark = pytest.mark.journey

# Handlers reached via these paths mutate a model with no automatic tenant filter,
# so each must scope by organisation itself.
UNSCOPED_MODELS = (
    "ApplicationDocument",
    "ApplicationCapabilityMapping",
    "ApplicationOwner",
    "LicenseEntitlement",
    "ContractApplication",
)

OWNERSHIP_MARKERS = (
    "verify_file_access",
    "organization_id",
    "current_user.organization",
    "_check_access",
    "abort(403",
    # Loading the parent ApplicationComponent counts. It IS a TenantMixin model, so
    # .query.get_or_404() is filtered and a cross-tenant caller gets 404 before the
    # unfiltered child is reached. Without this, the check reports every handler
    # that scopes correctly through its parent - 10 of the 11 it first flagged -
    # and a rule that cries wolf gets muted rather than fixed.
    #
    # Deliberately NOT counting db.session.get(ApplicationComponent, ...): that can
    # be served from the identity map without emitting a SELECT, so the filter is
    # not guaranteed to run.
    "ApplicationComponent.query.get_or_404(",
    "ApplicationComponent.query.get(",
)


@pytest.fixture(scope="module")
def app():
    import os

    os.environ.setdefault("SECRET_KEY", "x" * 32)
    from app import create_app

    return create_app("testing")


def _unwrap(view):
    """Strip login_required/audit_log wrappers to reach the real handler."""
    seen = 0
    while getattr(view, "__wrapped__", None) and seen < 10:
        view = view.__wrapped__
        seen += 1
    return view


def test_every_document_delete_route_checks_tenancy(app):
    """Named explicitly because this one destroys data irreversibly."""
    unchecked = []
    for rule in app.url_map.iter_rules():
        if "documents/" not in str(rule) or "delete" not in str(rule):
            continue
        view = _unwrap(app.view_functions.get(rule.endpoint))
        try:
            src = inspect.getsource(view)
        except (OSError, TypeError):
            continue
        if not any(marker in src for marker in OWNERSHIP_MARKERS):
            unchecked.append(str(rule))

    assert not unchecked, (
        "document delete route(s) with no tenant check: %s\n"
        "ApplicationDocument has no TenantMixin, so get_or_404() will return "
        "another tenant's row and the handler will delete it." % unchecked
    )


def test_mutating_routes_on_unfiltered_models_scope_themselves(app):
    """The general form of the same defect.

    A model without TenantMixin gets no injected filter, so any handler that
    writes to one and does not scope by organisation is reachable across the
    tenant boundary.
    """
    findings = []
    for rule in app.url_map.iter_rules():
        if not (rule.methods - {"HEAD", "OPTIONS", "GET"}):
            continue
        view = _unwrap(app.view_functions.get(rule.endpoint))
        if view is None:
            continue
        try:
            src = inspect.getsource(view)
        except (OSError, TypeError):
            continue
        # \b on the left matters: a plain substring test matches
        # UnifiedApplicationCapabilityMapping.query when looking for
        # ApplicationCapabilityMapping.query. They are different models, and the
        # Unified pair are shared reference data with no organization_id at all -
        # so the unfiltered query there is correct, and reporting it trains the
        # reader to ignore this test.
        touches = [m for m in UNSCOPED_MODELS if re.search(r"\b%s\.query" % m, src)]
        if not touches:
            continue
        if any(marker in src for marker in OWNERSHIP_MARKERS):
            continue
        findings.append("%s -> %s (%s)" % (rule, rule.endpoint, ",".join(touches)))

    assert not findings, (
        "%d mutating route(s) touch a model with no automatic tenant filter and "
        "do not scope by organisation:\n  %s\n\nEither add an ownership check or "
        "give the model TenantMixin." % (len(findings), "\n  ".join(sorted(findings)))
    )
