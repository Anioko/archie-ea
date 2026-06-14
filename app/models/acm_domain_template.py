"""ACM Domain Template — static reference data for baseline ArchiMate elements per ACM domain."""
# migration-exempt: table created via db.create_all() per platform migration freeze policy

from app import db


class AcmDomainTemplate(db.Model):
    __tablename__ = "acm_domain_templates"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    domain_code = db.Column(db.String(5), nullable=False, index=True)
    archimate_type = db.Column(db.String(64), nullable=False)
    archimate_layer = db.Column(db.String(16), nullable=False)
    name = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_baseline = db.Column(db.Boolean, default=False)
    is_nfr = db.Column(db.Boolean, default=False)
    is_core_nfr = db.Column(db.Boolean, default=False)
    industry_overlay = db.Column(db.String(32), nullable=True, index=True)
    default_rel_type = db.Column(db.String(64), nullable=True)
    default_rel_target = db.Column(db.String(64), nullable=True)
    sort_order = db.Column(db.Integer, default=0)

    def __repr__(self):
        return "<AcmDomainTemplate %s:%s '%s'>" % (self.domain_code, self.archimate_type, self.name)

    def to_dict(self):
        return {
            "id": self.id,
            "domain_code": self.domain_code,
            "archimate_type": self.archimate_type,
            "archimate_layer": self.archimate_layer,
            "name": self.name,
            "description": self.description,
            "is_baseline": self.is_baseline,
            "is_nfr": self.is_nfr,
            "is_core_nfr": self.is_core_nfr,
            "industry_overlay": self.industry_overlay,
            "default_rel_type": self.default_rel_type,
            "default_rel_target": self.default_rel_target,
            "sort_order": self.sort_order,
        }
