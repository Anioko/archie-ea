"""
Document processing service for extracting text content from uploaded files.

Supports plain-text-readable formats only (no binary dependencies).
Used by the AI Chat document upload route to extract content for context.
"""

import base64
import logging
import os

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """Extracts text content from uploaded documents using stdlib only."""

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_CONTENT_LENGTH = 50000  # Truncate content beyond this

    SUPPORTED_TYPES = {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".json": "application/json",
        ".xml": "text/xml",
        ".html": "text/html",
        ".py": "text/x-python",
        ".js": "text/javascript",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
    }

    def extract_text(self, file_path: str) -> dict:
        """
        Extract text content from a file.

        Returns dict with keys:
            success (bool): Whether extraction succeeded.
            content (str|None): Extracted text content (truncated to MAX_CONTENT_LENGTH).
            file_type (str|None): MIME type of the file.
            char_count (int): Character count of the full content before truncation.
            truncated (bool): Whether content was truncated.
            error (str|None): Error message if extraction failed.
        """
        result = {
            "success": False,
            "content": None,
            "file_type": None,
            "char_count": 0,
            "truncated": False,
            "error": None,
        }

        # Validate file exists
        if not os.path.isfile(file_path):
            result["error"] = f"File not found: {file_path}"
            logger.warning("Document processing: file not found at %s", file_path)
            return result

        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > self.MAX_FILE_SIZE:
            result["error"] = (
                f"File too large for text extraction ({file_size // (1024 * 1024)}MB). "
                f"Maximum: {self.MAX_FILE_SIZE // (1024 * 1024)}MB"
            )
            logger.warning(
                "Document processing: file too large (%d bytes) at %s",
                file_size,
                file_path,
            )
            return result

        # Determine file type from extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.SUPPORTED_TYPES:
            result["error"] = (
                f"Unsupported file type '{ext}' for text extraction. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_TYPES.keys()))}"
            )
            return result

        result["file_type"] = self.SUPPORTED_TYPES[ext]

        # Read content with encoding fallback
        content = None
        for encoding in ("utf-8", "latin-1"):
            try:
                with open(file_path, "r", encoding=encoding, errors="replace") as f:
                    content = f.read()
                break
            except (OSError, IOError) as e:
                logger.warning(
                    "Document processing: failed to read %s with %s encoding: %s",
                    file_path,
                    encoding,
                    e,
                )
                continue

        if content is None:
            result["error"] = "Failed to read file content with any supported encoding"
            return result

        # Record full char count
        result["char_count"] = len(content)

        # Truncate if needed
        if len(content) > self.MAX_CONTENT_LENGTH:
            content = content[: self.MAX_CONTENT_LENGTH]
            result["truncated"] = True

        result["content"] = content
        result["success"] = True

        logger.info(
            "Document processing: extracted %d chars from %s (truncated=%s)",
            result["char_count"],
            os.path.basename(file_path),
            result["truncated"],
        )

        return result

    # Supported image types for vision/multimodal LLM analysis (ENT-085)
    SUPPORTED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

    # Map file extensions to MIME media types for vision APIs
    _IMAGE_MEDIA_TYPES = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }

    def is_supported(self, filename: str) -> bool:
        """Check if the file type is supported for text extraction."""
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.SUPPORTED_TYPES

    def is_image(self, filename: str) -> bool:
        """Check if file is a supported image type for vision analysis."""
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.SUPPORTED_IMAGE_TYPES

    def prepare_image_for_llm(self, file_path: str) -> dict:
        """Read image file and return base64-encoded data for vision API.

        Returns dict with keys:
            success (bool): Whether preparation succeeded.
            base64_data (str|None): Base64-encoded image data.
            media_type (str|None): MIME type (e.g. 'image/png').
            file_size (int): File size in bytes.
            error (str|None): Error message if preparation failed.
        """
        result = {
            "success": False,
            "base64_data": None,
            "media_type": None,
            "file_size": 0,
            "error": None,
        }

        # Validate file exists
        if not os.path.isfile(file_path):
            result["error"] = f"Image file not found: {file_path}"
            logger.warning("Image processing: file not found at %s", file_path)
            return result

        # Check file size (max 10MB)
        file_size = os.path.getsize(file_path)
        result["file_size"] = file_size
        if file_size > self.MAX_FILE_SIZE:
            result["error"] = (
                f"Image too large ({file_size // (1024 * 1024)}MB). "
                f"Maximum: {self.MAX_FILE_SIZE // (1024 * 1024)}MB"
            )
            logger.warning(
                "Image processing: file too large (%d bytes) at %s",
                file_size,
                file_path,
            )
            return result

        # Determine media type from extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.SUPPORTED_IMAGE_TYPES:
            result["error"] = (
                f"Unsupported image type '{ext}'. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_IMAGE_TYPES))}"
            )
            return result

        result["media_type"] = self._IMAGE_MEDIA_TYPES[ext]

        # Read binary data and base64 encode
        try:
            with open(file_path, "rb") as f:
                raw_data = f.read()
            result["base64_data"] = base64.b64encode(raw_data).decode("ascii")
            result["success"] = True
            logger.info(
                "Image processing: prepared %d bytes from %s (type=%s)",
                file_size,
                os.path.basename(file_path),
                result["media_type"],
            )
        except (OSError, IOError) as e:
            result["error"] = f"Failed to read image file: {e}"
            logger.warning("Image processing: read error at %s: %s", file_path, e)

        return result

    # =========================================================================
    # RAG chunking & embedding (RAG-004)
    # =========================================================================

    CHUNK_TARGET_TOKENS = 512
    CHUNK_OVERLAP_TOKENS = 50
    # Approximate: 1 token ~ 0.75 words, so 512 tokens ~ 384 words.
    # We use word count as a lightweight proxy for token count.
    WORDS_PER_TOKEN = 0.75  # conservative estimate

    def _split_into_chunks(self, text: str) -> list:
        """Split *text* into overlapping chunks of ~512 tokens.

        Strategy:
        1. Split on sentence boundaries ('. ').
        2. Accumulate sentences until the word count reaches the target.
        3. Include a 50-token overlap window from the end of the previous chunk.

        Returns a list of chunk strings.
        """
        target_words = int(self.CHUNK_TARGET_TOKENS * self.WORDS_PER_TOKEN)
        overlap_words = int(self.CHUNK_OVERLAP_TOKENS * self.WORDS_PER_TOKEN)

        # Split into sentences (keep the period with the sentence)
        raw_sentences = text.replace("\n", " ").split(". ")
        sentences = [s.strip() + "." for s in raw_sentences if s.strip()]

        if not sentences:
            return [text] if text.strip() else []

        chunks: list = []
        current_words: list = []
        current_word_count = 0

        for sentence in sentences:
            sentence_words = sentence.split()
            sentence_word_count = len(sentence_words)

            if current_word_count + sentence_word_count > target_words and current_words:
                # Emit current chunk
                chunks.append(" ".join(current_words))

                # Build overlap from the tail of current_words
                overlap: list = []
                overlap_count = 0
                for word in reversed(current_words):
                    if overlap_count >= overlap_words:
                        break
                    overlap.insert(0, word)
                    overlap_count += 1

                current_words = overlap + sentence_words
                current_word_count = sum(1 for _ in current_words)
            else:
                current_words.extend(sentence_words)
                current_word_count += sentence_word_count

        # Flush remaining
        if current_words:
            chunks.append(" ".join(current_words))

        return chunks

    def chunk_and_embed(self, document_id: int, text: str) -> int:
        """Split *text* into ~512-token chunks, embed each, and persist.

        Args:
            document_id: Primary key of the ``AIChatDocumentUpload`` row.
            text: Full extracted text content of the document.

        Returns:
            Number of chunks created.
        """
        from app import db
        from app.models.vector_embeddings import DocumentChunkEmbedding

        chunks = self._split_into_chunks(text)
        if not chunks:
            logger.info("chunk_and_embed: no chunks produced for document %d", document_id)
            return 0

        # Attempt batch embedding generation
        embeddings = None
        try:
            from app.services.pgvector_embedding_service import PgvectorEmbeddingService

            svc = PgvectorEmbeddingService()
            embeddings = svc.generate_embeddings_batch(chunks)
        except Exception:
            logger.warning(
                "chunk_and_embed: embedding generation failed for document %d; "
                "saving chunks without embeddings",
                document_id,
                exc_info=True,
            )

        for idx, chunk_text in enumerate(chunks):
            embedding_vector = None
            if embeddings and idx < len(embeddings):
                embedding_vector = embeddings[idx]

            record = DocumentChunkEmbedding(
                document_id=document_id,
                chunk_index=idx,
                chunk_text=chunk_text,
                embedding=embedding_vector,
            )
            db.session.add(record)

        try:
            db.session.commit()
            logger.info(
                "chunk_and_embed: created %d chunks for document %d",
                len(chunks),
                document_id,
            )
        except Exception:
            db.session.rollback()
            logger.error(
                "chunk_and_embed: failed to persist chunks for document %d",
                document_id,
                exc_info=True,
            )
            return 0

        return len(chunks)

    def retrieve_document_chunks(
        self, query: str, document_id: int = None, limit: int = 5
    ) -> list:
        """Retrieve the most relevant document chunks for *query*.

        Args:
            query: Natural-language query text.
            document_id: If provided, restrict search to this document.
            limit: Maximum number of chunks to return.

        Returns:
            List of dicts with keys ``chunk_text``, ``document_id``,
            ``chunk_index``, ``similarity``.
        """
        from app.models.vector_embeddings import DocumentChunkEmbedding

        # Generate query embedding
        try:
            from app.services.pgvector_embedding_service import PgvectorEmbeddingService

            svc = PgvectorEmbeddingService()
            query_embedding = svc.generate_embedding(query)
        except Exception:
            logger.warning(
                "retrieve_document_chunks: embedding generation failed",
                exc_info=True,
            )
            query_embedding = None

        if not query_embedding:
            logger.info("retrieve_document_chunks: no query embedding; returning empty")
            return []

        try:
            q = (
                DocumentChunkEmbedding.query
                .filter(DocumentChunkEmbedding.embedding.isnot(None))
            )
            if document_id is not None:
                q = q.filter(DocumentChunkEmbedding.document_id == document_id)

            results = (
                q.order_by(
                    DocumentChunkEmbedding.embedding.cosine_distance(query_embedding)
                )
                .limit(limit)
                .all()
            )

            output = []
            for row in results:
                # Compute similarity = 1 - cosine_distance (approximate via Python)
                similarity = None
                try:
                    import numpy as np

                    a = np.array(query_embedding)
                    b = np.array(row.embedding)
                    cos_dist = 1 - float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
                    similarity = round(1 - cos_dist, 4)
                except Exception:  # fabricated-values-ok: similarity calc fallback
                    logger.exception("Failed to operation")
                    pass

                output.append(
                    {
                        "chunk_text": row.chunk_text,
                        "document_id": row.document_id,
                        "chunk_index": row.chunk_index,
                        "similarity": similarity,
                    }
                )
            return output
        except Exception:
            logger.error(
                "retrieve_document_chunks: search failed", exc_info=True
            )
            return []

    def get_supported_types(self) -> list:
        """Return list of supported file extensions."""
        return sorted(self.SUPPORTED_TYPES.keys())
