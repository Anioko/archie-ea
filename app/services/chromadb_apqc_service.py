"""
ChromaDB-based APQC Service - Metadata-rich vector similarity

.. deprecated:: 2.0.0
   This service is deprecated. Use :class:`app.services.unified_apqc_service.UnifiedAPQCService` instead.

   Migration:
       # Old way (deprecated):
       from app.services.chromadb_apqc_service import get_chromadb_apqc_service
       service = get_chromadb_apqc_service()

       # New way:
       from app.services.unified_apqc_service import get_unified_apqc_service
       service = get_unified_apqc_service()

Replaces FAISS with ChromaDB for enhanced metadata filtering capabilities.
Uses ChromaDB's document + metadata model for superior APQC process classification.

Key advantages over FAISS:
- Metadata filtering (layer, domain, coverage levels)
- Built-in persistence
- Pure Python (no binary compilation)
- Rich query capabilities with where clauses
- Better Flask integration

NOTE: This module is kept for backward compatibility but should not be used directly.
The UnifiedAPQCService automatically delegates to this service when appropriate.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from flask import has_app_context

from app import db
from app.models.apqc_process import APQCProcess
from app.utils.deprecation import (
    APQC_UNIFIED_GETTER,
    APQC_UNIFIED_SERVICE,
    deprecated_function,
    deprecated_service,
)

logger = logging.getLogger(__name__)

# Module-level deprecation warning
import warnings

warnings.warn(
    "chromadb_apqc_service is deprecated. Use unified_apqc_service instead.",
    DeprecationWarning,
    stacklevel=2,
)


@deprecated_service(
    replacement=APQC_UNIFIED_SERVICE,
    version="2.0.0",
    reason="Consolidated into UnifiedAPQCService for maintainability",
    removal_version="3.0.0",
)
class ChromaDBAPQCService:
    """
    ChromaDB-based APQC classification with rich metadata support.

    .. deprecated:: 2.0.0
       Use :class:`app.services.unified_apqc_service.UnifiedAPQCService` instead.

    Features:
    - Metadata filtering (layer, domain, APQC level)
    - Semantic embeddings via sentence-transformers
    - Persistent storage
    - Rich query capabilities
    - Flask app context integration
    """

    def __init__(self, persist_directory: str = "app/data/chromadb_apqc"):
        self.persist_directory = persist_directory
        self.collection = None
        self.client = None
        self.dimension = 384  # sentence-transformers all-MiniLM-L6-v2 dimension
        self._embedding_model = None
        self._initialize_chromadb()
        # Build collection only when an app context exists to avoid circular imports during startup
        if has_app_context():
            self._build_collection()
        else:
            logger.warning("No Flask app context; skipping ChromaDB collection build during init")

    def _initialize_chromadb(self):
        """Initialize ChromaDB client with proper settings."""
        try:
            # Configure ChromaDB for Flask integration
            settings = Settings(
                persist_directory=self.persist_directory,
                anonymized_telemetry=False,
                allow_reset=False,
            )

            self.client = chromadb.Client(settings)
            logger.info(
                f"ChromaDB client initialized with persist directory: {self.persist_directory}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise

    def _build_collection(self):
        """Build or load the APQC collection."""
        try:
            collection_name = "apqc_processes"

            # Try to get existing collection
            try:
                self.collection = self.client.get_collection(name=collection_name)
                logger.info(f"Loaded existing ChromaDB collection: {collection_name}")
                logger.info(f"Collection has {self.collection.count()} documents")
                return
            except Exception:
                # Collection doesn't exist, create it
                logger.info("Creating new ChromaDB collection for APQC processes")

                # Use sentence-transformers embedding function
                embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )

                self.collection = self.client.create_collection(
                    name=collection_name,
                    embedding_function=embedding_function,
                    metadata={"description": "APQC Process Classification with Metadata"},
                )

                # Populate collection with APQC processes
                self._populate_collection()

        except Exception as e:
            logger.error(f"Error building ChromaDB collection: {e}")
            raise

    def _populate_collection(self):
        """Populate ChromaDB collection with APQC processes."""
        try:
            if not has_app_context():
                logger.warning(
                    "No Flask app context; skipping ChromaDB population to avoid circular imports"
                )
                return

            processes = APQCProcess.query.all()

            if not processes:
                logger.warning("No APQC processes found for ChromaDB indexing")
                return

            documents = []
            metadatas = []
            ids = []

            for process in processes:
                text_parts = [
                    process.process_name or "",
                    process.category_level_1 or "",
                    process.category_level_2 or "",
                    process.process_category or "",
                    process.process_description or "",
                ]
                combined_text = " ".join(filter(None, text_parts))

                document = {
                    "id": str(process.id),
                    "text": combined_text,
                    "metadata": {
                        "process_id": process.id,
                        "process_code": process.process_code,
                        "process_name": process.process_name,
                        "process_description": process.process_description,
                        "category_level_1": process.category_level_1,
                        "category_level_2": process.category_level_2,
                        "category_level_3": process.category_level_3,
                        "process_category": process.process_category,
                        "industry_domain": process.industry_domain,
                        "process_type": process.process_type,
                        "apqc_level": process.apqc_level,
                        "archimate_mapping_level": process.archimate_mapping_level,
                        "benchmark_available": process.benchmark_available,
                        "process_maturity": process.process_maturity,
                        "improvement_priority": process.improvement_priority,
                    },
                }

                metadata = document["metadata"]
                metadata = {k: v for k, v in metadata.items() if v is not None}
                if process.category_level_1:
                    metadata["domain"] = process.category_level_1
                if process.category_level_2:
                    metadata["subdomain"] = process.category_level_2
                if process.apqc_level:
                    metadata["apqc_level_numeric"] = float(process.apqc_level)

                documents.append(document)
                metadatas.append(metadata)
                ids.append(f"apqc_{process.id}")

            batch_size = 100
            for i in range(0, len(documents), batch_size):
                batch_docs = [doc["text"] for doc in documents[i : i + batch_size]]
                batch_metas = metadatas[i : i + batch_size]
                batch_ids = ids[i : i + batch_size]

                self.collection.add(documents=batch_docs, metadatas=batch_metas, ids=batch_ids)

            logger.info(f"ChromaDB collection populated: {len(documents)} APQC processes")

        except Exception as e:
            logger.error(f"Error populating ChromaDB collection: {e}")
            raise

    def _get_embedding_model(self):
        """Lazy-load the sentence transformer model for compatibility."""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Sentence transformer model initialized for ChromaDB compatibility")
            except Exception as e:
                logger.warning(f"Could not initialize sentence transformer: {e}")
                self._embedding_model = False
        return self._embedding_model if self._embedding_model else None

    def search_similar(
        self, query_text: str, top_k: int = 5, where_filter: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar APQC processes using ChromaDB.

        Args:
            query_text: Text to search for
            top_k: Number of results to return
            where_filter: Optional metadata filter (e.g., {"category_level_1": "Finance"})

        Returns:
            List of similar APQC processes with scores
        """
        if self.collection is None:
            logger.warning("ChromaDB collection not available")
            return []

        try:
            # Build query arguments
            query_args = {"query_texts": [query_text], "n_results": top_k}

            # Add metadata filter if provided
            if where_filter:
                query_args["where"] = where_filter

            # Execute query
            results = self.collection.query(**query_args)

            # Format results
            formatted_results = []
            if results["documents"] and results["documents"][0]:
                for i, (doc, metadata, distance) in enumerate(
                    zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
                ):
                    # Convert distance to similarity score (ChromaDB uses cosine distance)
                    similarity_score = 1.0 - distance

                    result = {
                        "process_code": metadata.get("process_code"),
                        "process_name": metadata.get("process_name"),
                        "category_level_1": metadata.get("category_level_1"),
                        "category_level_2": metadata.get("category_level_2"),
                        "process_category": metadata.get("process_category"),
                        "apqc_level": metadata.get("apqc_level"),
                        "level": metadata.get("level"),
                        "existing_id": metadata.get("database_id"),
                        "score": similarity_score,
                        "distance": distance,
                        "source": "chromadb_similarity",
                        "rank": i + 1,
                        "document": doc,  # Include the embedded document for reference
                        "metadata": metadata,  # Include full metadata for advanced use
                    }
                    formatted_results.append(result)

            return formatted_results

        except Exception as e:
            logger.error(f"Error in ChromaDB search: {e}")
            return []

    def classify_text(
        self, text: str, max_results: int = 5, filters: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Classify text using hybrid approach (regex + ChromaDB).

        Args:
            text: Input text to classify
            max_results: Maximum number of results
            filters: Optional metadata filters

        Returns:
            List of APQC matches with scores
        """
        all_results = []

        # Try regex first for structured PCF codes
        regex_matches = self._regex_classify(text)
        if regex_matches:
            all_results.extend(regex_matches)

        # Try ChromaDB for semantic similarity
        remaining_results = max_results - len(all_results)
        if remaining_results > 0:
            chromadb_matches = self.search_similar(
                text, top_k=remaining_results, where_filter=filters
            )
            if chromadb_matches:
                all_results.extend(chromadb_matches)

        # Remove duplicates and sort by score
        seen_codes = set()
        unique_results = []
        for result in all_results:
            code = result.get("process_code")
            if code and code not in seen_codes:
                seen_codes.add(code)
                unique_results.append(result)

        # Sort by score (descending)
        unique_results.sort(key=lambda x: x["score"], reverse=True)

        return unique_results[:max_results]

    def _regex_classify(self, text: str) -> List[Dict[str, Any]]:
        """Extract PCF codes using regex patterns."""
        import re

        matches = []

        try:
            # Look for PCF patterns like "3.2.1 Digital content"
            pcf_pattern = r"(?=\b\d+\.\d+(?:\.\d+)*\s)"
            parts = re.split(pcf_pattern, text)

            for part in parts:
                part = part.strip()
                if part:
                    code_match = re.match(r"^(\d+\.\d+(?:\.\d+)*)\s*(.*)$", part)
                    if code_match:
                        pcf_code = code_match.group(1)
                        process_name = code_match.group(2).strip()

                        # Validate against database
                        process = APQCProcess.query.filter_by(process_code=pcf_code).first()
                        if process:
                            matches.append(
                                {
                                    "process_code": pcf_code,
                                    "process_name": process_name,
                                    "description": process.process_description,
                                    "category_level_1": process.category_level_1,
                                    "category_level_2": process.category_level_2,
                                    "level": process.apqc_level,
                                    "existing_id": process.id,
                                    "score": 1.0,  # High confidence for exact matches
                                    "source": "regex_exact",
                                }
                            )

        except Exception as e:
            logger.error(f"Error in regex classification: {e}")

        return matches

    def query_by_metadata(self, where_filter: Dict, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Query APQC processes using metadata filters only.

        Args:
            where_filter: Metadata filter dictionary
            top_k: Maximum number of results

        Returns:
            List of APQC processes matching the filter
        """
        if self.collection is None:
            logger.warning("ChromaDB collection not available")
            return []

        try:
            # Query with empty text to get metadata-only results
            results = self.collection.query(
                query_texts=[""],  # Empty query for metadata-only search
                where=where_filter,
                n_results=top_k,
            )

            formatted_results = []
            if results["metadatas"] and results["metadatas"][0]:
                for i, metadata in enumerate(results["metadatas"][0]):
                    result = {
                        "process_code": metadata.get("process_code"),
                        "process_name": metadata.get("process_name"),
                        "category_level_1": metadata.get("category_level_1"),
                        "category_level_2": metadata.get("category_level_2"),
                        "process_category": metadata.get("process_category"),
                        "apqc_level": metadata.get("apqc_level"),
                        "level": metadata.get("level"),
                        "existing_id": metadata.get("database_id"),
                        "score": 1.0,  # Perfect match for metadata filter
                        "source": "chromadb_metadata",
                        "rank": i + 1,
                        "metadata": metadata,
                    }
                    formatted_results.append(result)

            return formatted_results

        except Exception as e:
            logger.error(f"Error in ChromaDB metadata query: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get ChromaDB collection statistics."""
        if self.collection is None:
            return {"status": "not_built"}

        try:
            count = self.collection.count()
            return {
                "status": "built",
                "total_documents": count,
                "persist_directory": self.persist_directory,
                "collection_name": self.collection.name,
                "embedding_function": "sentence-transformers/all-MiniLM-L6-v2",
            }
        except Exception as e:
            logger.error(f"Error getting ChromaDB stats: {e}")
            return {"status": "error", "error": str(e)}

    def rebuild_collection(self):
        """Rebuild the entire collection (useful for data updates)."""
        try:
            if self.collection:
                self.client.delete_collection(self.collection.name)
                logger.info("Deleted existing ChromaDB collection")

            self._build_collection()
            logger.info("ChromaDB collection rebuilt successfully")

        except Exception as e:
            logger.error(f"Error rebuilding ChromaDB collection: {e}")
            raise


# Singleton instance
_chromadb_apqc_service = None


@deprecated_function(
    replacement=APQC_UNIFIED_GETTER,
    version="2.0.0",
    reason="Use get_unified_apqc_service() instead",
)
def get_chromadb_apqc_service() -> ChromaDBAPQCService:
    """
    Get the singleton ChromaDB APQC service instance.

    .. deprecated:: 2.0.0
       Use :func:`app.services.unified_apqc_service.get_unified_apqc_service` instead.
    """
    global _chromadb_apqc_service
    if _chromadb_apqc_service is None:
        _chromadb_apqc_service = ChromaDBAPQCService()
    return _chromadb_apqc_service
