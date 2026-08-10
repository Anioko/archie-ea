"""AI chat conversation history — thread and message tables.

These two tables existed only in ``migrations/versions/add_conversation_tables.py``.
Deploys do not run ``flask db upgrade`` (see CLAUDE.md, "Schema management"), and
``create_all()`` cannot create a table no model declares — so a fresh database had
neither table and every ``/ai-chat/threads`` call raised ``UndefinedTable``. See
``docs/known-issues/conversation-tables-not-created-on-fresh-install.md``.

Declaring the models fixes that: ``flask init-db`` creates the tables and
``flask reconcile-schema`` keeps their columns in line, exactly as for every other
table.

Two deliberate constraints on this module:

* **The shapes below mirror the migration's DDL and the live production tables.**
  Column names, types, lengths, nullability, foreign keys and indexes all match.
  Anything extra here would make ``reconcile-schema`` try to ALTER a table that
  already holds production data.

* **No ``TenantMixin``.** These tables have no ``organization_id`` column in
  production, and are scoped by ``user_id`` instead — which is what
  ``app/services/conversation_history.py`` filters on. Adding ``TenantMixin``
  would declare a column production does not have (so ``reconcile-schema`` would
  try to add it) and would inject ``WHERE organization_id = ...`` into ORM reads
  of a column that does not exist. A user belongs to exactly one organisation, so
  filtering by ``user_id`` already confines a thread to one tenant.

``app/services/conversation_history.py`` keeps its raw SQL. These classes exist so
the tables get created, not to replace that service.
"""

from .. import db

__all__ = ["ConversationThreadRecord", "ConversationMessageRecord"]


class ConversationThreadRecord(db.Model):
    """One AI chat conversation, owned by a user.

    Named ``...Record`` to avoid colliding with the ``ConversationThread``
    dataclass that ``app/services/conversation_history.py`` returns to callers;
    the two describe the same row but this one is the mapped table.
    """

    __tablename__ = "conversation_threads"

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    # Nullable with a server-side 0, matching the live table. The counter is
    # maintained by the service's UPDATE, not by the ORM.
    message_count = db.Column(db.Integer, default=0, server_default=db.text("0"))

    __table_args__ = (
        # Serves the history rail's only query:
        # WHERE user_id = :user_id ORDER BY updated_at DESC.
        db.Index("idx_threads_user_updated", "user_id", "updated_at"),
    )

    def __repr__(self):
        return f"<ConversationThreadRecord {self.id} user={self.user_id}>"


class ConversationMessageRecord(db.Model):
    """One message inside a conversation thread."""

    __tablename__ = "conversation_messages"

    id = db.Column(db.String(36), primary_key=True)
    thread_id = db.Column(
        db.String(36), db.ForeignKey("conversation_threads.id"), nullable=False
    )
    role = db.Column(db.String(20), nullable=False)  # 'system' | 'user' | 'assistant'
    content = db.Column(db.Text, nullable=False)
    model = db.Column(db.String(50), nullable=True)
    tokens = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        # Serves the transcript query: WHERE thread_id = :id ORDER BY created_at.
        db.Index("idx_messages_thread_created", "thread_id", "created_at"),
    )

    def __repr__(self):
        return f"<ConversationMessageRecord {self.id} thread={self.thread_id} {self.role}>"
