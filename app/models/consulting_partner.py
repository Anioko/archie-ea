"""
Consulting Partner Models

Separate from technology vendors - these are professional services firms
that provide implementation, strategy, and advisory services.
"""

from datetime import datetime

from app import db


class ConsultingPartner(db.Model):
    """
    Consulting Partner/Professional Services Firm

    Separate from technology vendors - provides implementation, strategy,
    and advisory services for enterprise architecture and digital transformation.
    """

    __tablename__ = "consulting_partners"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Firm identity
    name = db.Column(db.String(200), nullable=False, unique=True, index=True)
    firm_type = db.Column(db.String(50))  # CONSULTING, SYSTEM_INTEGRATOR, DIGITAL_AGENCY, etc.
    headquarters_location = db.Column(db.String(100))
    website = db.Column(db.String(500))

    # Market intelligence
    market_position = db.Column(db.String(50))  # LEADER, CHALLENGER, NICHE
    company_size = db.Column(db.String(50))  # ENTERPRISE, MID_MARKET, SMB
    founded_year = db.Column(db.Integer)
    annual_revenue = db.Column(db.Float)  # In billions USD
    employee_count = db.Column(db.Integer)

    # Specialization and expertise
    specialization = db.Column(db.JSON)  # List of specializations
    industry_focus = db.Column(db.JSON)  # List of industries served
    apqc_expertise = db.Column(db.JSON)  # List of APQC process codes
    vendor_partners = db.Column(db.JSON)  # List of vendor partners
    geographic_coverage = db.Column(db.JSON)  # List of regions/countries

    # Service offerings
    service_types = db.Column(db.JSON)  # Strategy, Implementation, Managed Services, etc.
    pricing_model = db.Column(db.String(50))  # Fixed price, T&M, Retainer, etc.
    average_project_size = db.Column(db.String(50))  # Small, Medium, Large, Enterprise

    # Quality and certifications
    certifications = db.Column(db.JSON)  # ISO, CMMI, etc.
    quality_ratings = db.Column(db.JSON)  # Client satisfaction, etc.
    awards_recognition = db.Column(db.JSON)  # Industry awards

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    created_by = db.relationship("User", backref="created_consulting_partners")

    # Vendor-Consulting relationships
    vendor_partnerships = db.relationship(
        "VendorOrganization",
        secondary="consulting_vendor_partnerships",
        backref="consulting_partners",
    )

    def __repr__(self):
        return f"<ConsultingPartner {self.name} ({self.firm_type})>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "firm_type": self.firm_type,
            "headquarters_location": self.headquarters_location,
            "website": self.website,
            "market_position": self.market_position,
            "company_size": self.company_size,
            "founded_year": self.founded_year,
            "annual_revenue": self.annual_revenue,
            "employee_count": self.employee_count,
            "specialization": self.specialization,
            "industry_focus": self.industry_focus,
            "apqc_expertise": self.apqc_expertise,
            "vendor_partners": self.vendor_partners,
            "geographic_coverage": self.geographic_coverage,
            "service_types": self.service_types,
            "pricing_model": self.pricing_model,
            "average_project_size": self.average_project_size,
            "certifications": self.certifications,
            "quality_ratings": self.quality_ratings,
            "awards_recognition": self.awards_recognition,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def get_by_firm_type(cls, firm_type):
        """Get consulting partners by firm type."""
        return cls.query.filter_by(firm_type=firm_type).all()

    @classmethod
    def get_by_apqc_expertise(cls, apqc_process_code):
        """Get consulting partners with expertise in specific APQC process."""
        return cls.query.filter(cls.apqc_expertise.contains([apqc_process_code])).all()

    @classmethod
    def get_by_vendor_partner(cls, vendor_name):
        """Get consulting partners that work with specific vendor."""
        return cls.query.filter(cls.vendor_partners.contains([vendor_name])).all()

    @classmethod
    def get_by_geographic_coverage(cls, region):
        """Get consulting partners serving specific region."""
        return cls.query.filter(cls.geographic_coverage.contains([region])).all()


# Junction table for consulting-vendor partnerships
consulting_vendor_partnerships = db.Table(
    "consulting_vendor_partnerships",
    db.Column(
        "consulting_partner_id",
        db.Integer,
        db.ForeignKey("consulting_partners.id"),
        primary_key=True,
    ),
    db.Column(
        "vendor_organization_id",
        db.Integer,
        db.ForeignKey("vendor_organizations.id"),
        primary_key=True,
    ),
    db.Column("partnership_type", db.String(50)),  # PREFERRED, CERTIFIED, STRATEGIC
    db.Column("expertise_level", db.String(20)),  # EXPERT, ADVANCED, BASIC
    db.Column("project_count", db.Integer, default=0),  # Number of joint projects
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)
