"""
Vendor Taxonomy Models

Canonical taxonomy for vendor and product classification.
Provides standardized categorization for MDM and deduplication.

Key Features:
- Canonical vendor names and aliases
- Product taxonomy with hierarchical classification
- Fuzzy matching support for normalization
- Confidence-scored taxonomy mappings
- Integration with external data sources (G2, Crunchbase, Croud)
"""

from __future__ import annotations  # dead-code-ok

import json
from datetime import datetime
from typing import List

from .. import db
from app.models.mixins import TenantMixin


class VendorTaxonomy(TenantMixin, db.Model):
    """
    Canonical vendor taxonomy with aliases and normalization rules.

    Provides master data for vendor deduplication and standardization.
    """

    __tablename__ = "vendor_taxonomy"

    id = db.Column(db.Integer, primary_key=True)

    # Canonical identity
    canonical_name = db.Column(db.String(200), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(200))
    vendor_type = db.Column(db.String(50))  # software_vendor, cloud_provider, systems_integrator

    # Alternative names and aliases
    aliases = db.Column(db.Text)  # JSON array of alternative names
    common_misspellings = db.Column(db.Text)  # JSON array of common errors

    # External identifiers
    g2_id = db.Column(db.String(50))
    crunchbase_id = db.Column(db.String(50))
    croud_id = db.Column(db.String(50))
    linkedin_id = db.Column(db.String(50))

    # Normalization metadata
    normalization_rules = db.Column(db.Text)  # JSON: fuzzy matching rules
    confidence_threshold = db.Column(db.Float, default=0.8)  # Match confidence required

    # Taxonomy classification
    industry_vertical = db.Column(db.String(100))
    primary_domain = db.Column(db.String(100))  # ERP, CRM, HCM, etc.
    sub_domains = db.Column(db.Text)  # JSON array

    # Status and governance
    is_active = db.Column(db.Boolean, default=True)
    is_canonical = db.Column(db.Boolean, default=True)
    merged_into_id = db.Column(db.Integer, db.ForeignKey("vendor_taxonomy.id"))

    # Audit trail
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))
    updated_by = db.Column(db.String(100))

    # Relationships
    merged_into = db.relationship("VendorTaxonomy", remote_side=[id], uselist=False)

    def __repr__(self):
        return f"<VendorTaxonomy {self.canonical_name}>"

    @property
    def aliases_list(self) -> List[str]:
        """Get aliases as a list."""
        if not self.aliases:
            return []
        try:
            return json.loads(self.aliases)
        except (json.JSONDecodeError, TypeError):
            return []

    @aliases_list.setter
    def aliases_list(self, value: List[str]):
        """Set aliases from a list."""
        self.aliases = json.dumps(value) if value else None

    @property
    def common_misspellings_list(self) -> List[str]:
        """Get misspellings as a list."""
        if not self.common_misspellings:
            return []
        try:
            return json.loads(self.common_misspellings)
        except (json.JSONDecodeError, TypeError):
            return []

    @common_misspellings_list.setter
    def common_misspellings_list(self, value: List[str]):
        """Set misspellings from a list."""
        self.common_misspellings = json.dumps(value) if value else None

    @property
    def sub_domains_list(self) -> List[str]:
        """Get sub-domains as a list."""
        if not self.sub_domains:
            return []
        try:
            return json.loads(self.sub_domains)
        except (json.JSONDecodeError, TypeError):
            return []

    @sub_domains_list.setter
    def sub_domains_list(self, value: List[str]):
        """Set sub-domains from a list."""
        self.sub_domains = json.dumps(value) if value else None


class ProductTaxonomy(db.Model):
    """
    Canonical product taxonomy with hierarchical classification.

    Provides standardized product categorization for MDM.
    """

    __tablename__ = "product_taxonomy"

    id = db.Column(db.Integer, primary_key=True)

    # Canonical identity
    canonical_name = db.Column(db.String(200), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(200))
    product_type = db.Column(db.String(50))  # software, service, platform, etc.

    # Alternative names
    aliases = db.Column(db.Text)  # JSON array
    version_patterns = db.Column(db.Text)  # JSON: regex patterns for version identification

    # Taxonomy hierarchy
    category = db.Column(db.String(100))  # ERP, CRM, Database, etc.
    sub_category = db.Column(db.String(100))  # Financials, HCM, etc.
    domain = db.Column(db.String(100))  # Business, Technology, etc.

    # Product metadata
    is_suite = db.Column(db.Boolean, default=False)  # Is this a product suite?
    parent_suite_id = db.Column(db.Integer, db.ForeignKey("product_taxonomy.id"))

    # External identifiers
    g2_product_id = db.Column(db.String(50))
    crunchbase_product_id = db.Column(db.String(50))

    # Status and governance
    is_active = db.Column(db.Boolean, default=True)
    is_canonical = db.Column(db.Boolean, default=True)
    merged_into_id = db.Column(db.Integer, db.ForeignKey("product_taxonomy.id"))

    # Audit trail
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))
    updated_by = db.Column(db.String(100))

    # Relationships
    parent_suite = db.relationship(
        "ProductTaxonomy", foreign_keys=[parent_suite_id], remote_side=[id], uselist=False
    )
    merged_into = db.relationship(
        "ProductTaxonomy", foreign_keys=[merged_into_id], remote_side=[id], uselist=False
    )

    def __repr__(self):
        return f"<ProductTaxonomy {self.canonical_name}>"


class TaxonomyMapping(db.Model):
    """
    Mapping between raw vendor/product names and canonical taxonomy.

    Stores fuzzy matching results with confidence scores.
    """

    __tablename__ = "taxonomy_mappings"

    id = db.Column(db.Integer, primary_key=True)

    # Raw input
    raw_name = db.Column(db.String(200), nullable=False, index=True)
    name_type = db.Column(db.String(20))  # 'vendor' or 'product'

    # Canonical mapping
    canonical_id = db.Column(
        db.Integer, nullable=False
    )  # References vendor_taxonomy or product_taxonomy
    canonical_name = db.Column(db.String(200))

    # Matching metadata
    match_confidence = db.Column(db.Float)  # 0.0 to 1.0
    match_method = db.Column(db.String(50))  # 'exact', 'fuzzy', 'manual', 'ai'
    match_source = db.Column(db.String(50))  # 'g2', 'crunchbase', 'manual', 'ai'

    # Validation
    is_validated = db.Column(db.Boolean, default=False)
    validated_by = db.Column(db.String(100))
    validated_at = db.Column(db.DateTime)

    # Audit trail
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))

    def __repr__(self):
        return (
            f"<TaxonomyMapping {self.raw_name} -> {self.canonical_name} ({self.match_confidence})>"
        )
