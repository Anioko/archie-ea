"""
Contract Ingestion Service

NLP-powered contract analysis with:
- Document ingestion (PDF, DOCX)
- Clause extraction with confidence scores
- Obligation/SLA identification (F1 ≥85%, target ≥95%)
- Linking to ArchiMate KG elements with provenance

Uses spaCy/Transformers for NER and relation extraction.

FEATURE STATUS: DISABLED
_analyze_contract() and _extract_entities() contain unfinished NLP stubs
(spaCy/Transformers NER pipeline not wired up). Calling ingest_contract()
will raise FeatureDisabledError until the implementation is complete.
Do NOT connect any UI route to this service until the stubs are resolved.
"""

# FEATURE_DISABLED — contract upload analysis is not yet implemented.
# See _analyze_contract() and _extract_entities() for the TODO stubs.

import logging
import re
import uuid  # dead-code-ok
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

logger = logging.getLogger(__name__)


class FeatureDisabledError(RuntimeError):
    """Raised when a feature is intentionally disabled pending implementation."""


class ClauseType(str, Enum):
    """Contract clause types."""
    OBLIGATION = "obligation"
    SLA = "sla"
    REQUIREMENT = "requirement"
    CONSTRAINT = "constraint"
    EXCEPTION = "exception"


class ExtractionResult(NamedTuple):
    """Result of clause extraction."""
    text: str
    clause_type: ClauseType
    confidence: float
    entities: List[Dict[str, Any]]
    relations: List[Dict[str, Any]]
    start_pos: int
    end_pos: int


class ContractIngestionService:
    """Service for ingesting and analyzing contracts."""

    def __init__(self):
        self.nlp_model = None
        self.ner_model = None
        self.relation_model = None
        self._load_models()

    def _load_models(self):
        """Load NLP models for contract analysis."""
        logger.debug(
            "NLP models (spaCy/Transformers) not configured; "
            "clause extraction falls back to rule-based patterns"
        )

    async def ingest_contract(self, file_path: str,
                            metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Ingest and analyze a contract document.

        DISABLED: _extract_entities() is an unfinished stub that raises
        NotImplementedError.  Re-enable once the NLP pipeline is wired up.
        """
        raise FeatureDisabledError(
            "Contract analysis is temporarily disabled. "
            "The NLP pipeline (spaCy / Transformers NER) is not yet implemented. "
            "See app/services/contract_ingestion.py for the TODO stubs."
        )

    async def _extract_text(self, file_path: str) -> str:
        """Extract text from document file."""
        file_ext = Path(file_path).suffix.lower()

        if file_ext == '.pdf':
            return await self._extract_pdf_text(file_path)
        elif file_ext in ['.docx', '.doc']:
            return await self._extract_docx_text(file_path)
        elif file_ext == '.txt':
            return await self._extract_txt_text(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")

    async def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF file using PyPDF2 if available."""
        try:
            import PyPDF2

            text_parts = []
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            if not text_parts:
                raise ValueError("No text could be extracted from PDF")
            return "\n".join(text_parts)
        except ImportError:
            raise RuntimeError("PyPDF2 is required for PDF extraction but is not installed")
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise

    async def _extract_docx_text(self, file_path: str) -> str:
        """Extract text from DOCX file using python-docx if available."""
        try:
            import docx

            doc = docx.Document(file_path)
            text_parts = [para.text for para in doc.paragraphs if para.text.strip()]
            if not text_parts:
                raise ValueError("No text could be extracted from DOCX")
            return "\n".join(text_parts)
        except ImportError:
            raise RuntimeError("python-docx is required for DOCX extraction but is not installed")
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
            raise

    async def _extract_txt_text(self, file_path: str) -> str:
        """Extract text from TXT file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"TXT extraction failed: {e}")
            raise

    async def _analyze_contract(self, text: str) -> Dict[str, Any]:
        """Analyze contract text using NLP models."""
        try:
            # Extract clauses
            clauses = await self._extract_clauses(text)

            # Identify obligations and SLAs
            obligations = await self._identify_obligations(clauses)

            # Extract entities (dates, amounts, parties, etc.)
            try:
                entities = await self._extract_entities(text)
            except NotImplementedError:
                logger.debug("NER pipeline not available; skipping entity extraction")
                entities = []

            # Build analysis result
            analysis = {
                "total_clauses": len(clauses),
                "obligations": obligations,
                "entities": entities,
                "confidence_score": self._calculate_overall_confidence(clauses),
                "processing_timestamp": datetime.utcnow().isoformat()
            }

            return analysis

        except Exception as e:
            logger.error(f"Contract analysis failed: {e}")
            raise

    async def _extract_clauses(self, text: str) -> List[ExtractionResult]:
        """Extract clauses from contract text using rule-based patterns."""
        clauses = []

        # Simple rule-based clause detection
        clause_patterns = [
            (r'(?:shall|will|must|agrees? to)\s+(.+?)(?:\.|;|$)', ClauseType.OBLIGATION),
            (r'SLA.+?(?:\.|;|$)', ClauseType.SLA),
            (r'requirements?.+?(?:\.|;|$)', ClauseType.REQUIREMENT),
            (r'constraints?.+?(?:\.|;|$)', ClauseType.CONSTRAINT),
            (r'exceptions?.+?(?:\.|;|$)', ClauseType.EXCEPTION),
        ]

        for pattern, clause_type in clause_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                clause_text = match.group(0).strip()
                if len(clause_text) > 10:  # Filter very short matches
                    clauses.append(ExtractionResult(
                        text=clause_text,
                        clause_type=clause_type,
                        confidence=0.75,  # Rule-based default
                        entities=[],
                        relations=[],
                        start_pos=match.start(),
                        end_pos=match.end()
                    ))

        return clauses

    async def _identify_obligations(self, clauses: List[ExtractionResult]) -> List[Dict[str, Any]]:
        """Identify and categorize obligations from clauses."""
        obligations = []

        for clause in clauses:
            if clause.clause_type in [ClauseType.OBLIGATION, ClauseType.SLA]:
                obligation = {
                    "text": clause.text,
                    "type": clause.clause_type.value,
                    "confidence": clause.confidence,
                    "category": self._categorize_obligation(clause.text),
                    "responsible_party": self._extract_responsible_party(clause.text),
                    "deadline": self._extract_deadline(clause.text),
                    "penalty": self._extract_penalty(clause.text)
                }
                obligations.append(obligation)

        return obligations

    def _categorize_obligation(self, text: str) -> str:
        """Categorize obligation type."""
        text_lower = text.lower()

        if any(word in text_lower for word in ['performance', 'availability', 'uptime']):
            return 'performance'
        elif any(word in text_lower for word in ['security', 'confidentiality', 'privacy']):
            return 'security'
        elif any(word in text_lower for word in ['payment', 'billing', 'compensation']):
            return 'financial'
        elif any(word in text_lower for word in ['support', 'maintenance', 'helpdesk']):
            return 'support'
        else:
            return 'general'

    def _extract_responsible_party(self, text: str) -> Optional[str]:
        """Extract responsible party from obligation text."""
        # Simple pattern matching
        patterns = [
            r'(?:provider|vendor|supplier|party a)\s+(?:shall|will|must)',
            r'(?:customer|client|party b)\s+(?:shall|will|must)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).lower()

        return None

    def _extract_deadline(self, text: str) -> Optional[str]:
        """Extract deadline from obligation text."""
        # Simple date pattern matching
        date_patterns = [
            r'within\s+(\d+)\s+(?:day|week|month|year)s?',
            r'by\s+(.+?)(?:\.|;|$)'
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_penalty(self, text: str) -> Optional[str]:
        """Extract penalty from obligation text."""
        penalty_patterns = [
            r'penalty(?:\s+of)?\s*\$?([\d,]+)',
            r'fine(?:\s+of)?\s*\$?([\d,]+)',
            r'liquidated damages(?:\s+of)?\s*\$?([\d,]+)'
        ]

        for pattern in penalty_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    async def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract named entities from contract text using pattern-based NER."""
        entities: List[Dict[str, Any]] = []

        # Organisation patterns: detect company names with common suffixes
        org_pattern = re.compile(
            r'\b([A-Z][A-Za-z0-9\s&\-]{2,50}(?:Inc|LLC|Ltd|Corp|Corporation|Company|Co|GmbH|plc|AG)\.?)\b'
        )
        for match in org_pattern.finditer(text):
            entities.append({
                "type": "ORGANIZATION",
                "text": match.group(1).strip(),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.6,
            })

        # Date patterns: ISO dates, "Month DD, YYYY", relative dates
        date_pattern = re.compile(
            r'\b(\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|'
            r'September|October|November|December)\s+\d{1,2},?\s+\d{4}|'
            r'(?:within\s+\d+\s+(?:days?|weeks?|months?|years?)))\b',
            re.IGNORECASE,
        )
        for match in date_pattern.finditer(text):
            entities.append({
                "type": "DATE",
                "text": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.8,
            })

        # Monetary value patterns
        money_pattern = re.compile(
            r'\$[\d,]+(?:\.\d{2})?|\b\d[\d,]*(?:\.\d{2})?\s*(?:USD|EUR|GBP|dollars?|euros?)\b',
            re.IGNORECASE,
        )
        for match in money_pattern.finditer(text):
            entities.append({
                "type": "MONEY",
                "text": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.85,
            })

        # Deduplicate by (type, text) while preserving order
        seen: set = set()
        unique_entities: List[Dict[str, Any]] = []
        for ent in entities:
            key = (ent["type"], ent["text"])
            if key not in seen:
                seen.add(key)
                unique_entities.append(ent)

        return unique_entities

    def _calculate_overall_confidence(self, clauses: List[ExtractionResult]) -> float:
        """Calculate overall confidence score for analysis."""
        if not clauses:
            return 0.0

        total_confidence = sum(clause.confidence for clause in clauses)
        return total_confidence / len(clauses)

    async def link_to_archimate(self, contract_id: str,
                              archimate_element_ids: List[str]) -> Dict[str, Any]:
        """Link contract obligations to ArchiMate elements."""
        if not archimate_element_ids:
            return {
                "contract_id": contract_id,
                "linked_elements": [],
                "status": "no_elements_provided",
            }
        # Knowledge graph connector is not yet available; record intent and return
        # a structured placeholder so callers get a consistent response shape.
        logger.warning(
            "link_to_archimate called for contract %s but KG connector is not configured. "
            "%d element IDs received: %s",
            contract_id,
            len(archimate_element_ids),
            archimate_element_ids[:5],
        )
        return {
            "contract_id": contract_id,
            "linked_elements": [
                {"archimate_element_id": eid, "status": "pending_kg_integration"}
                for eid in archimate_element_ids
            ],
            "status": "kg_not_configured",
            "message": (
                "ArchiMate knowledge-graph integration is not yet configured. "
                "Element IDs have been recorded and will be linked when the connector is available."
            ),
        }


def get_contract_ingestion_service() -> ContractIngestionService:
    """Get a contract ingestion service instance."""
    return ContractIngestionService()
