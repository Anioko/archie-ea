"""Definition of Done models — TPM-010."""
from app import db


class DoDTemplate(db.Model):
    __tablename__ = "dod_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    scope = db.Column(db.String(32), default="story")  # story / sprint / epic
    is_default = db.Column(db.Boolean, default=False)
    criteria = db.Column(db.JSON, default=list)
    # criteria: [{"id": "c1", "text": "...", "mandatory": True}]

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "scope": self.scope,
            "is_default": self.is_default,
            "criteria": self.criteria or [],
        }


class DoDCheck(db.Model):
    __tablename__ = "dod_checks"

    id = db.Column(db.Integer, primary_key=True)
    requirement_id = db.Column(db.Integer, nullable=True)
    sprint_id = db.Column(db.Integer, nullable=True)
    template_id = db.Column(db.Integer, db.ForeignKey("dod_templates.id"))
    checked_criteria = db.Column(db.JSON, default=dict)  # {criterion_id: True/False}
    all_mandatory_met = db.Column(db.Boolean, default=False)

    template = db.relationship("DoDTemplate", lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "requirement_id": self.requirement_id,
            "sprint_id": self.sprint_id,
            "template_id": self.template_id,
            "checked_criteria": self.checked_criteria or {},
            "all_mandatory_met": self.all_mandatory_met,
        }
