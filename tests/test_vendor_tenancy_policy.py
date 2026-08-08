"""Which vendor data is shared and which is per-tenant — as a decision, not an accident.

A sidebar audit showed vendor counts that were identical for every organisation,
which looks exactly like the cross-tenant leak found in the application and
element counts. It is not. The distinction is worth pinning, because both
"fixes" are wrong in one direction:

  * Adding TenantMixin to VendorOrganization would duplicate all 45 vendor
    records per organisation and break its global UNIQUE(name). Everything on it
    is a fact about the vendor in the world — Gartner quadrant position, market
    share, revenue, stock symbol — identical for every customer.
  * Giving VendorProductCapability a tenant column of its own breaks mapper
    initialisation across the whole app. It IS tenant data — a row records how a
    vendor product covers a *tenant-owned* business capability, and all 192 rows
    in production belong to one organisation — but it inherits its tenant from
    the capability it references rather than storing it again ("scoped via
    parent FK", as app/modules/ai_chat/services/multi_domain_chat_service.py
    already puts it).

So: the catalogue is shared; the assessments against it are tenant data reached
only through their capability. Any query that reads the assessment table alone
is cross-tenant, and no ORM filter will save it.
"""

def test_vendor_catalogue_is_deliberately_shared(app):
    """VendorOrganization must stay global — see the module docstring."""
    from app.models.mixins import TenantMixin
    from app.models.vendor.vendor_organization import VendorOrganization

    assert not issubclass(VendorOrganization, TenantMixin), (
        "VendorOrganization gained TenantMixin. It is shared reference data with a "
        "global UNIQUE(name); scoping it duplicates every vendor per organisation. "
        "Tenant-specific vendor data belongs in vendor_contracts, "
        "contract_applications, or VendorProductCapability."
    )


def test_vendor_capability_assessments_are_tenant_scoped(app):
    """VendorProductCapability describes a tenant's capabilities, so it is tenant data.

    The table already carried an organization_id column — declared as a bare
    nullable Integer with no ForeignKey, populated by nothing, filtered on by
    nothing. That missing FK is why the first attempt to add TenantMixin broke
    mapper initialisation app-wide. The bare column is gone and the mixin now
    owns it.
    """
    from app.models.mixins import TenantMixin
    from app.models.vendor.vendor_organization import VendorProductCapability

    assert issubclass(VendorProductCapability, TenantMixin), (
        "VendorProductCapability is not tenant-scoped, but business_capability_id "
        "points at a tenant-owned capability — the row states how a vendor covers "
        "one customer's capability model"
    )

    fks = VendorProductCapability.__table__.c.organization_id.foreign_keys
    assert fks, (
        "organization_id has no ForeignKey. A bare column here is what silently "
        "disabled tenant scoping on this table before, and it makes the mixin's "
        "`organization` relationship unjoinable."
    )
