"""
SystemSetting — a small key/value store for system-wide settings.

Several services (e.g. the LLM service persisting a user's provider/model
preference) read and write this table via raw SQL with an ON CONFLICT (key)
upsert. The table had no model, so db.create_all() never created it and those
queries failed with `relation "system_settings" does not exist` — which also
poisoned the surrounding request transaction. Defining the model here makes
create_all build the table on a fresh install.
"""

from app import db


class SystemSetting(db.Model):  # migration-exempt
    """System-wide key/value setting."""

    __tablename__ = "system_settings"

    key = db.Column(db.String(255), primary_key=True)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f"<SystemSetting {self.key!r}>"
