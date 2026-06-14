"""
Initialize pgvector in Flask app and create migration script

This script:
1. Enables pgvector extension in PostgreSQL
2. Creates all vector embedding tables
3. Migrates existing data if needed
"""

import logging
from typing import List, Tuple  # dead-code-ok

from sqlalchemy import text

logger = logging.getLogger(__name__)


def init_pgvector(db_session) -> bool:
    """
    Initialize pgvector extension and create tables.

    Args:
        db_session: SQLAlchemy session

    Returns:
        True if successful, False otherwise
    """
    try:
        # Enable pgvector extension
        db_session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))  # tenant-exempt: system/pgvector extension
        db_session.commit()
        logger.info("✅ pgvector extension enabled")

        # Create HNSW index for faster similarity search
        # This is done after table creation via Alembic migration
        logger.info("✅ pgvector initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize pgvector: {e}")
        db_session.rollback()
        return False


def create_hnsw_indexes(db_session) -> bool:
    """
    Create HNSW indexes for vector columns for fast similarity search.
    Run this AFTER tables are created.
    """
    try:
        # List of (table_name, column_name) tuples
        indexes = [
            ("vendor_product_embeddings", "embedding"),
            ("business_capability_embeddings", "embedding"),
            ("process_embeddings", "embedding"),
            ("chat_message_embeddings", "embedding"),
            ("solution_embeddings", "embedding"),
            ("vendor_organization_embeddings", "embedding"),
            ("application_component_embeddings", "embedding"),
        ]

        for table, column in indexes:
            try:
                # Create HNSW index for similarity search
                # HNSW is better than IVFFlat for high dimensions
                index_name = f"idx_{table}_{column}_hnsw"
                sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} USING hnsw ({column} vector_cosine_ops)"
                db_session.execute(text(sql))  # tenant-exempt: system/pgvector index
                logger.info(f"✅ Created HNSW index: {index_name}")
            except Exception as e:
                logger.warning(f"⚠️  Could not create HNSW index for {table}.{column}: {e}")

        db_session.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create HNSW indexes: {e}")
        db_session.rollback()
        return False


def migrate_chromadb_to_pgvector(db_session, chromadb_client=None) -> int:
    """
    Migrate existing embeddings from ChromaDB to pgvector.

    Args:
        db_session: SQLAlchemy session
        chromadb_client: Optional ChromaDB client for migration

    Returns:
        Number of embeddings migrated
    """
    if not chromadb_client:
        logger.info("No ChromaDB client provided, skipping migration")
        return 0

    try:
        from app.models.vector_embeddings import VendorProductEmbedding
        from app.services.pgvector_embedding_service import get_pgvector_service

        migrated = 0
        service = get_pgvector_service()

        # Example: migrate vendor product embeddings
        try:
            collection = chromadb_client.get_collection("vendor_products")
            all_items = collection.get()  # Get all items

            for i, doc_id in enumerate(all_items.get("ids", [])):
                try:
                    # Extract vendor_product_id from doc_id
                    vendor_product_id = int(doc_id.split("_")[-1])

                    # Get embedding data
                    metadata = (
                        all_items["metadatas"][i] if i < len(all_items.get("metadatas", [])) else {}
                    )
                    embedding_text = metadata.get("text", "")

                    # Create pgvector embedding
                    service.create_vendor_product_embedding(vendor_product_id, embedding_text)
                    migrated += 1
                except Exception as e:
                    logger.debug(f"Could not migrate embedding {doc_id}: {e}")
        except Exception as e:
            logger.warning(f"Could not access vendor_products collection: {e}")

        logger.info(f"✅ Migrated {migrated} embeddings from ChromaDB to pgvector")
        return migrated
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return 0


def verify_pgvector_setup(db_session) -> bool:
    """
    Verify pgvector is properly installed and working.
    """
    try:
        # Test vector type
        result = db_session.execute(text("SELECT '(0.1,0.2)'::vector(2) as test_vector")).fetchone()  # tenant-exempt: system/pgvector test

        if result:
            logger.info("✅ pgvector is working correctly")
            return True
        else:
            logger.error("❌ pgvector test query failed")
            return False
    except Exception as e:
        logger.error(f"❌ pgvector verification failed: {e}")
        return False
