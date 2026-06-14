"""ACM Cross-Domain Rule — data-driven dependency chain rules between ACM domains."""
# migration-exempt — new table created via db.create_all(), not Alembic (migration freeze)

from app import db


class AcmCrossDomainRule(db.Model):
    __tablename__ = "acm_cross_domain_rules"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    trigger_domain = db.Column(db.String(5), nullable=False, index=True)
    trigger_archimate_type = db.Column(db.String(64), nullable=False)
    trigger_pattern = db.Column(db.String(256), nullable=False)
    rule_type = db.Column(db.String(20), nullable=False, default="create_element")
    target_domain = db.Column(db.String(5), nullable=False)
    target_archimate_type = db.Column(db.String(64), nullable=False)
    name_template = db.Column(db.String(256), nullable=False)
    target_relationship_type = db.Column(db.String(64), nullable=True)
    target_relationship_target = db.Column(db.String(256), nullable=True)
    description = db.Column(db.Text, nullable=True)
    severity = db.Column(db.String(16), nullable=False, default="recommended")
    industry_overlay = db.Column(db.String(32), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return "<AcmCrossDomainRule %s:%s -> %s:%s (%s)>" % (
            self.trigger_domain, self.trigger_archimate_type,
            self.target_domain, self.target_archimate_type, self.severity,
        )

    def matches(self, element_name):
        """Check if an element name matches this rule's trigger pattern."""
        pattern = self.trigger_pattern
        keywords = [k.strip() for k in pattern.split("|")]
        name_lower = (element_name or "").lower()
        return any(kw.lower() in name_lower for kw in keywords)

    def render_name(self, element_name):
        """Render the name_template with the trigger element's name."""
        return self.name_template.replace("{element_name}", element_name or "Unknown")

    def to_dict(self):
        return {
            "id": self.id,
            "trigger_domain": self.trigger_domain,
            "trigger_archimate_type": self.trigger_archimate_type,
            "trigger_pattern": self.trigger_pattern,
            "rule_type": self.rule_type,
            "target_domain": self.target_domain,
            "target_archimate_type": self.target_archimate_type,
            "name_template": self.name_template,
            "target_relationship_type": self.target_relationship_type,
            "target_relationship_target": self.target_relationship_target,
            "description": self.description,
            "severity": self.severity,
            "industry_overlay": self.industry_overlay,
            "is_active": self.is_active,
        }
