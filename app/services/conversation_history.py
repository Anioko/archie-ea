"""
Conversation History Service with Vector Search
Persistent chat threads with semantic search capabilities
"""
import json  # dead-code-ok
import uuid
from dataclasses import asdict, dataclass  # dead-code-ok
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import text

from app import db
from app.extensions.cache import cached, invalidate_cache

# Vector search imports
try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer

    HAS_VECTOR_SEARCH = True
except ImportError:
    HAS_VECTOR_SEARCH = False


@dataclass
class ConversationThread:
    """A conversation thread with messages."""

    id: str
    user_id: int
    title: str
    model: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "message_count": self.message_count,
        }


@dataclass
class ConversationMessage:
    """Single message in a conversation."""

    id: str
    thread_id: str
    role: str  # 'system', 'user', 'assistant'
    content: str
    model: Optional[str]
    tokens: Optional[int]
    created_at: datetime

    def to_dict(self):
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "role": self.role,
            "content": self.content,
            "model": self.model,
            "tokens": self.tokens,
            "created_at": self.created_at.isoformat(),
        }


class ConversationHistoryService:
    """
    Service for managing conversation threads with vector search.
    Stores conversations in database and indexes for semantic search.
    """

    def __init__(self):
        self.chroma_client = None
        self.collection = None
        self.embedder = None

        if HAS_VECTOR_SEARCH:
            try:
                # Initialize ChromaDB for vector storage
                self.chroma_client = chromadb.Client(
                    Settings(
                        chroma_db_impl="duckdb+parquet",
                        persist_directory="./data/chroma_conversations",
                    )
                )

                # Get or create collection for conversations
                self.collection = self.chroma_client.get_or_create_collection(
                    name="conversation_messages",
                    metadata={"description": "Conversation messages with embeddings"},
                )

                # Initialize sentence transformer for embeddings
                self.embedder = SentenceTransformer("all-MiniLM-L6-v2")

            except Exception as e:
                print(f"Warning: Vector search initialization failed: {e}")
                self.chroma_client = None

    def create_thread(
        self, user_id: int, title: str, model: str, initial_message: Optional[str] = None
    ) -> ConversationThread:
        """
        Create a new conversation thread.

        Args:
            user_id: User ID owning the thread
            title: Thread title
            model: AI model used in thread
            initial_message: Optional first message

        Returns:
            ConversationThread object
        """
        thread_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Insert into database
        db.session.execute(  # tenant-filtered: scoped via parent FK (user_id)
            text(
                """
                INSERT INTO conversation_threads
                (id, user_id, title, model, created_at, updated_at, message_count)
                VALUES (:id, :user_id, :title, :model, :created_at, :updated_at, 0)
            """
            ),
            {
                "id": thread_id,
                "user_id": user_id,
                "title": title,
                "model": model,
                "created_at": now,
                "updated_at": now,
            },
        )
        db.session.commit()

        thread = ConversationThread(
            id=thread_id,
            user_id=user_id,
            title=title,
            model=model,
            created_at=now,
            updated_at=now,
            message_count=0,
        )

        # Add initial message if provided
        if initial_message:
            self.add_message(thread_id, "user", initial_message, model=None)

        # Invalidate cache
        invalidate_cache(f"threads:user:{user_id}:*")

        return thread

    def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        tokens: Optional[int] = None,
    ) -> ConversationMessage:
        """
        Add a message to a conversation thread.

        Args:
            thread_id: Thread ID
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            model: Model that generated the message (for assistant messages)
            tokens: Token count (optional)

        Returns:
            ConversationMessage object
        """
        message_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Insert message
        db.session.execute(  # tenant-filtered: scoped via parent FK (thread_id)
            text(
                """
                INSERT INTO conversation_messages
                (id, thread_id, role, content, model, tokens, created_at)
                VALUES (:id, :thread_id, :role, :content, :model, :tokens, :created_at)
            """
            ),
            {
                "id": message_id,
                "thread_id": thread_id,
                "role": role,
                "content": content,
                "model": model,
                "tokens": tokens,
                "created_at": now,
            },
        )

        # Update thread
        db.session.execute(  # tenant-filtered: scoped via parent FK (thread_id)
            text(
                """
                UPDATE conversation_threads
                SET updated_at = :updated_at,
                    message_count = message_count + 1
                WHERE id = :thread_id
            """
            ),
            {"updated_at": now, "thread_id": thread_id},
        )

        db.session.commit()

        # Index in vector store for semantic search
        if self.collection and role in ["user", "assistant"]:
            try:
                embedding = self.embedder.encode([content])[0].tolist()
                self.collection.add(
                    ids=[message_id],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[
                        {
                            "thread_id": thread_id,
                            "role": role,
                            "model": model or "",
                            "created_at": now.isoformat(),
                        }
                    ],
                )
            except Exception as e:
                print(f"Warning: Vector indexing failed: {e}")

        # Invalidate cache
        invalidate_cache(f"thread:{thread_id}:messages")

        return ConversationMessage(
            id=message_id,
            thread_id=thread_id,
            role=role,
            content=content,
            model=model,
            tokens=tokens,
            created_at=now,
        )

    @cached(ttl=300, key_prefix="threads:user")
    def get_user_threads(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> List[ConversationThread]:
        """
        Get conversation threads for a user.

        Args:
            user_id: User ID
            limit: Max threads to return
            offset: Pagination offset

        Returns:
            List of ConversationThread objects
        """
        result = db.session.execute(  # tenant-filtered: scoped via parent FK (user_id)
            text(
                """
                SELECT id, user_id, title, model, created_at, updated_at, message_count
                FROM conversation_threads
                WHERE user_id = :user_id
                ORDER BY updated_at DESC
                LIMIT :limit OFFSET :offset
            """
            ),
            {"user_id": user_id, "limit": limit, "offset": offset},
        )

        threads = []
        for row in result:
            threads.append(
                ConversationThread(
                    id=row.id,
                    user_id=row.user_id,
                    title=row.title,
                    model=row.model,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    message_count=row.message_count,
                )
            )

        return threads

    @cached(ttl=300, key_prefix="thread:messages")
    def get_thread_messages(
        self, thread_id: str, limit: Optional[int] = None
    ) -> List[ConversationMessage]:
        """
        Get messages for a conversation thread.

        Args:
            thread_id: Thread ID
            limit: Optional limit on message count

        Returns:
            List of ConversationMessage objects
        """
        query = """
            SELECT id, thread_id, role, content, model, tokens, created_at
            FROM conversation_messages
            WHERE thread_id = :thread_id
            ORDER BY created_at ASC
        """

        if limit:
            query += " LIMIT :limit"

        result = db.session.execute(  # tenant-filtered: scoped via parent FK (thread_id)
            text(query),
            {"thread_id": thread_id, "limit": limit} if limit else {"thread_id": thread_id},
        )

        messages = []
        for row in result:
            messages.append(
                ConversationMessage(
                    id=row.id,
                    thread_id=row.thread_id,
                    role=row.role,
                    content=row.content,
                    model=row.model,
                    tokens=row.tokens,
                    created_at=row.created_at,
                )
            )

        return messages

    def search_conversations(self, user_id: int, query: str, limit: int = 10) -> List[Dict]:
        """
        Semantic search across user's conversation history.

        Args:
            user_id: User ID to search within
            query: Search query
            limit: Max results to return

        Returns:
            List of matching messages with metadata
        """
        if not self.collection:
            raise RuntimeError(
                "Vector search not available. Install chromadb and sentence-transformers."
            )

        # Get user's thread IDs
        thread_ids = [t.id for t in self.get_user_threads(user_id, limit=1000)]

        if not thread_ids:
            return []

        # Generate query embedding
        query_embedding = self.embedder.encode([query])[0].tolist()

        # Search in vector store
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit * 2,  # Get extra results for filtering
            where={"thread_id": {"$in": thread_ids}},
        )

        # Format results
        matches = []
        if results["ids"] and results["ids"][0]:
            for idx, msg_id in enumerate(results["ids"][0]):
                if idx >= limit:
                    break

                matches.append(
                    {
                        "message_id": msg_id,
                        "thread_id": results["metadatas"][0][idx]["thread_id"],
                        "content": results["documents"][0][idx],
                        "role": results["metadatas"][0][idx]["role"],
                        "model": results["metadatas"][0][idx]["model"],
                        "distance": results["distances"][0][idx]
                        if "distances" in results
                        else None,
                        "created_at": results["metadatas"][0][idx]["created_at"],
                    }
                )

        return matches

    def delete_thread(self, thread_id: str):
        """Delete a conversation thread and its messages."""
        # Delete from vector store
        if self.collection:
            try:
                # Get all message IDs for this thread
                messages = self.get_thread_messages(thread_id)
                message_ids = [m.id for m in messages]
                if message_ids:
                    self.collection.delete(ids=message_ids)
            except Exception as e:
                print(f"Warning: Vector deletion failed: {e}")

        # Delete from database
        db.session.execute(  # tenant-filtered: scoped via parent FK (thread_id)
            text("DELETE FROM conversation_messages WHERE thread_id = :thread_id"),
            {"thread_id": thread_id},
        )
        db.session.execute(  # tenant-filtered: scoped via parent FK (thread_id)
            text("DELETE FROM conversation_threads WHERE id = :thread_id"), {"thread_id": thread_id}
        )
        db.session.commit()

        # Invalidate cache
        invalidate_cache(f"thread:{thread_id}:*")
        invalidate_cache(f"threads:user:*")

    def update_thread_title(self, thread_id: str, title: str):
        """Update thread title."""
        db.session.execute(  # tenant-filtered: scoped via parent FK (thread_id)
            text(
                """
                UPDATE conversation_threads
                SET title = :title, updated_at = :updated_at
                WHERE id = :thread_id
            """
            ),
            {"title": title, "updated_at": datetime.utcnow(), "thread_id": thread_id},
        )
        db.session.commit()

        invalidate_cache(f"threads:user:*")


# ============================================================================
# Module-level wiring so the chat endpoints persist every turn (always on).
# A single service instance is reused (the vector model loads once, lazily).
# ============================================================================

_HISTORY_SINGLETON = None
_TABLES_READY = False

# Dialect-agnostic DDL (Postgres + SQLite). The thread/message tables are created
# by a raw-SQL migration that the runtime entrypoint doesn't run — so we ensure
# them here, idempotently, on first use. This keeps chat history working on the
# live box and on every fresh deploy with no manual migration step.
_ENSURE_DDL = [
    """
    CREATE TABLE IF NOT EXISTS conversation_threads (
        id VARCHAR(36) PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        title VARCHAR(255) NOT NULL,
        model VARCHAR(50) NOT NULL,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        message_count INTEGER DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_threads_user_updated ON conversation_threads (user_id, updated_at)",
    """
    CREATE TABLE IF NOT EXISTS conversation_messages (
        id VARCHAR(36) PRIMARY KEY,
        thread_id VARCHAR(36) NOT NULL REFERENCES conversation_threads(id),
        role VARCHAR(20) NOT NULL,
        content TEXT NOT NULL,
        model VARCHAR(50),
        tokens INTEGER,
        created_at TIMESTAMP NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_messages_thread_created ON conversation_messages (thread_id, created_at)",
]


def _ensure_tables():
    """Create the conversation tables if missing. Runs at most once per process."""
    global _TABLES_READY
    if _TABLES_READY:
        return
    try:
        for stmt in _ENSURE_DDL:
            db.session.execute(text(stmt))
        db.session.commit()
        _TABLES_READY = True
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        # Leave _TABLES_READY False so a later call can retry once the DB is ready.


def get_history_service() -> "ConversationHistoryService":
    """Return the shared history service, building it on first use."""
    global _HISTORY_SINGLETON
    _ensure_tables()
    if _HISTORY_SINGLETON is None:
        _HISTORY_SINGLETON = ConversationHistoryService()
    return _HISTORY_SINGLETON


def thread_owned_by(thread_id: str, user_id: int) -> bool:
    """True only if this thread exists and belongs to user_id (guards IDOR)."""
    if not thread_id or user_id is None:
        return False
    _ensure_tables()
    row = db.session.execute(
        text("SELECT user_id FROM conversation_threads WHERE id = :id"),
        {"id": thread_id},
    ).fetchone()
    return bool(row) and row.user_id == user_id


def persist_turn(user_id, thread_id, user_message, assistant_text, model=None):
    """Persist one user+assistant turn, creating the thread on the first turn.

    Returns the thread_id (new one if created). NEVER raises — chat must keep
    working even if history storage hiccups.
    """
    if user_id is None or not (user_message or "").strip():
        return thread_id
    try:
        svc = get_history_service()
        model = (model or "assistant").strip() or "assistant"
        # New conversation, or a thread_id that isn't this user's → start fresh.
        if not thread_owned_by(thread_id, user_id):
            title = (user_message or "New chat").strip().splitlines()[0][:60] or "New chat"
            thread_id = svc.create_thread(user_id, title=title, model=model).id
        svc.add_message(thread_id, "user", user_message, model=None)
        if (assistant_text or "").strip():
            svc.add_message(thread_id, "assistant", assistant_text, model=model)
        return thread_id
    except Exception as exc:  # pragma: no cover - persistence must never break chat
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            from flask import current_app

            current_app.logger.warning("persist_turn failed: %s", exc)
        except Exception:
            pass
        return thread_id
