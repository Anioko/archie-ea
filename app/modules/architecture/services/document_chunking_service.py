"""
Document Chunking Service

Intelligently chunks large documents for LLM analysis while preserving context.
Features:
- Semantic chunking (sentence/paragraph boundaries)
- Overlap windows for context preservation
- Size-aware chunking (respects token limits)
- Hierarchical chunking (sections → paragraphs → sentences)
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a chunk of document text with metadata."""

    text: str
    chunk_index: int
    start_char: int
    end_char: int
    section_title: Optional[str] = None
    estimated_tokens: int = 0
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        # Estimate tokens (rough: 1 token ≈ 4 characters)
        if self.estimated_tokens == 0:
            self.estimated_tokens = len(self.text) // 4


class DocumentChunkingService:
    """
    Service for intelligently chunking large documents for LLM analysis.
    """

    # Default chunk sizes (in characters, approximate)
    DEFAULT_CHUNK_SIZE = 12000  # ~3000 tokens
    MAX_CHUNK_SIZE = 15000  # ~3750 tokens
    OVERLAP_SIZE = 2000  # ~500 tokens overlap between chunks

    def __init__(self, chunk_size: int = None, overlap_size: int = None):
        """
        Initialize chunking service.

        Args:
            chunk_size: Target chunk size in characters (default: 12000)
            overlap_size: Overlap between chunks in characters (default: 2000)
        """
        self.chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE
        self.overlap_size = overlap_size or self.OVERLAP_SIZE

    def chunk_document(
        self, text: str, preserve_structure: bool = True, min_chunk_size: int = 1000
    ) -> List[DocumentChunk]:
        """
        Chunk a document intelligently, preserving structure and context.

        Args:
            text: Full document text
            preserve_structure: Whether to respect section boundaries
            min_chunk_size: Minimum chunk size (chunks smaller than this are merged)

        Returns:
            List of DocumentChunk objects
        """
        if not text or len(text) <= self.chunk_size:
            # Document is small enough, return as single chunk
            return [
                DocumentChunk(
                    text=text,
                    chunk_index=0,
                    start_char=0,
                    end_char=len(text),
                    estimated_tokens=len(text) // 4,
                )
            ]

        chunks = []

        if preserve_structure:
            # Try semantic chunking first (by sections/paragraphs)
            chunks = self._chunk_by_structure(text, min_chunk_size)
        else:
            # Simple sliding window chunking
            chunks = self._chunk_sliding_window(text, min_chunk_size)

        # Post-process: merge very small chunks, ensure overlap
        chunks = self._merge_small_chunks(chunks, min_chunk_size)
        chunks = self._add_overlap(chunks)

        return chunks

    def _chunk_by_structure(self, text: str, min_chunk_size: int) -> List[DocumentChunk]:
        """Chunk document by structural boundaries (sections, paragraphs)."""
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_index = 0
        current_section = None

        # Split by major section markers
        section_pattern = re.compile(
            r"(?:\n\s*\n\s*)(?:#{1,6}\s+|Chapter\s+\d+|Section\s+\d+|^\d+\.\s+[A-Z])", re.MULTILINE
        )

        # Find section boundaries
        sections = list(section_pattern.finditer(text))
        section_starts = [0] + [m.start() for m in sections]
        section_titles = [None] + [m.group().strip() for m in sections]

        for i, (start, title) in enumerate(zip(section_starts, section_titles)):
            if i < len(section_starts) - 1:
                end = section_starts[i + 1]
            else:
                end = len(text)

            section_text = text[start:end]

            # If section is small, add to current chunk
            if len(current_chunk) + len(section_text) <= self.chunk_size:
                current_chunk += section_text
                if title and not current_section:
                    current_section = title
            else:
                # Save current chunk if it has content
                if current_chunk.strip():
                    chunks.append(
                        DocumentChunk(
                            text=current_chunk.strip(),
                            chunk_index=chunk_index,
                            start_char=current_start,
                            end_char=current_start + len(current_chunk),
                            section_title=current_section,
                            metadata={"chunking_method": "structural"},
                        )
                    )
                    chunk_index += 1
                    current_start += len(current_chunk)

                # Start new chunk with this section
                if len(section_text) > self.chunk_size:
                    # Section itself is too large, split it
                    sub_chunks = self._chunk_sliding_window(section_text, min_chunk_size)
                    for sub_chunk in sub_chunks:
                        sub_chunk.chunk_index = chunk_index
                        sub_chunk.start_char = current_start
                        sub_chunk.end_char = current_start + len(sub_chunk.text)
                        sub_chunk.section_title = title
                        chunks.append(sub_chunk)
                        chunk_index += 1
                        current_start += len(sub_chunk.text)
                    current_chunk = ""
                else:
                    current_chunk = section_text
                    current_section = title

        # Add final chunk
        if current_chunk.strip():
            chunks.append(
                DocumentChunk(
                    text=current_chunk.strip(),
                    chunk_index=chunk_index,
                    start_char=current_start,
                    end_char=len(text),
                    section_title=current_section,
                    metadata={"chunking_method": "structural"},
                )
            )

        return chunks

    def _chunk_sliding_window(self, text: str, min_chunk_size: int) -> List[DocumentChunk]:
        """Chunk using sliding window approach."""
        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings near the end
                sentence_end = max(
                    text.rfind(". ", start, end),
                    text.rfind(".\n", start, end),
                    text.rfind("! ", start, end),
                    text.rfind("?\n", start, end),
                )
                if sentence_end > start + min_chunk_size:
                    end = sentence_end + 1

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    DocumentChunk(
                        text=chunk_text,
                        chunk_index=chunk_index,
                        start_char=start,
                        end_char=end,
                        metadata={"chunking_method": "sliding_window"},
                    )
                )
                chunk_index += 1

            start = end

        return chunks

    def _merge_small_chunks(
        self, chunks: List[DocumentChunk], min_chunk_size: int
    ) -> List[DocumentChunk]:
        """Merge chunks that are too small."""
        if not chunks:
            return chunks

        merged = []
        current = chunks[0]

        for next_chunk in chunks[1:]:
            if (
                len(current.text) < min_chunk_size
                and len(current.text) + len(next_chunk.text) <= self.chunk_size
            ):
                # Merge with next chunk
                current = DocumentChunk(
                    text=current.text + "\n\n" + next_chunk.text,
                    chunk_index=current.chunk_index,
                    start_char=current.start_char,
                    end_char=next_chunk.end_char,
                    section_title=current.section_title or next_chunk.section_title,
                    metadata={**current.metadata, **next_chunk.metadata, "merged": True},
                )
            else:
                merged.append(current)
                current = next_chunk

        merged.append(current)
        return merged

    def _add_overlap(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Add overlap between chunks for context preservation."""
        if len(chunks) <= 1:
            return chunks

        overlapped = []
        for i, chunk in enumerate(chunks):
            text = chunk.text

            # Add overlap from previous chunk
            if i > 0:
                prev_chunk = chunks[i - 1]
                overlap_start = max(0, len(prev_chunk.text) - self.overlap_size)
                overlap_text = prev_chunk.text[overlap_start:]
                if overlap_text:
                    text = f"[...context from previous section...]\n{overlap_text}\n\n{text}"

            # Add preview of next chunk
            if i < len(chunks) - 1:
                next_chunk = chunks[i + 1]
                preview_text = next_chunk.text[: min(self.overlap_size // 2, len(next_chunk.text))]
                if preview_text:
                    text = f"{text}\n\n[...preview of next section...]\n{preview_text}"

            overlapped.append(
                DocumentChunk(
                    text=text,
                    chunk_index=chunk.chunk_index,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    section_title=chunk.section_title,
                    metadata={**chunk.metadata, "has_overlap": True},
                )
            )

        return overlapped

    def get_chunk_summary(self, chunks: List[DocumentChunk]) -> Dict:
        """Get summary statistics about chunks."""
        total_chars = sum(len(c.text) for c in chunks)
        total_tokens = sum(c.estimated_tokens for c in chunks)

        return {
            "total_chunks": len(chunks),
            "total_characters": total_chars,
            "total_estimated_tokens": total_tokens,
            "average_chunk_size": total_chars // len(chunks) if chunks else 0,
            "average_tokens_per_chunk": total_tokens // len(chunks) if chunks else 0,
            "chunk_sizes": [len(c.text) for c in chunks],
            "has_overlap": any(c.metadata.get("has_overlap", False) for c in chunks),
        }
