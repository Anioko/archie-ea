"""Behavioral Code Pattern Library — maps BFG pipeline signatures to code patterns.

Each pattern defines:
  - signature: ordered list of step types that identify the pattern
  - template_id: which Jinja2 template set to use for code generation
  - default_integrations: external services typically involved
  - generates: what code artifacts this pattern produces

The matching algorithm computes semantic overlap between a BFG pipeline's
steps and each pattern's signature. Threshold-based selection avoids
false positives — unmatched pipelines fall through to CRUD.
"""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern Definitions
# ---------------------------------------------------------------------------

PIPELINE_PATTERNS: dict[str, dict[str, Any]] = {
    "document_ingestion": {
        "description": "Upload document, extract text, parse with AI, output structured data",
        "signature_keywords": [
            "upload", "document", "pdf", "extract", "parse", "ocr",
            "text", "conversion", "ai", "llm", "structured", "json",
        ],
        "step_types": ["file_upload", "text_extraction", "ai_parsing", "structured_output"],
        "default_integrations": {
            "text_extractor": {"protocol": "rest", "candidates": ["pdf.ai", "document_ai", "tika"]},
            "ai_parser": {"protocol": "rest", "candidates": ["openai", "anthropic", "gemini"]},
        },
        "generates": {
            "backend": ["upload_endpoint", "extraction_service", "parser_service", "result_schema"],
            "frontend": ["upload_dropzone", "extraction_progress", "result_viewer"],
            "tests": ["upload_test", "extraction_accuracy_test", "sla_test"],
        },
        "template_id": "pipeline_document_ingestion",
    },
    "email_processing": {
        "description": "Monitor email inbox, extract attachments, process, notify agent",
        "signature_keywords": [
            "email", "inbox", "imap", "smtp", "attachment", "order",
            "notification", "agent", "notify", "catch", "receive",
        ],
        "step_types": ["email_monitoring", "attachment_extraction", "processing", "notification"],
        "default_integrations": {
            "email_service": {"protocol": "imap", "candidates": ["imap", "exchange", "gmail_api"]},
            "notification": {"protocol": "rest", "candidates": ["smtp", "sendgrid", "sns"]},
        },
        "generates": {
            "backend": ["email_listener", "attachment_handler", "processing_queue", "notification_service"],
            "frontend": ["inbox_dashboard", "processing_status"],
            "tests": ["email_ingestion_test", "notification_test"],
        },
        "template_id": "pipeline_email_processing",
    },
    "catalog_matching": {
        "description": "Match extracted items against a reference catalog with accuracy targets",
        "signature_keywords": [
            "match", "catalog", "sku", "product", "reference", "accuracy",
            "fuzzy", "similarity", "lookup", "categorize", "taxonomy",
        ],
        "step_types": ["item_extraction", "catalog_lookup", "fuzzy_match", "confidence_filter"],
        "default_integrations": {},
        "generates": {
            "backend": ["matching_service", "catalog_loader", "similarity_scorer"],
            "frontend": ["match_review_table"],
            "tests": ["accuracy_test", "matching_test"],
        },
        "template_id": "pipeline_catalog_matching",
    },
    "llm_integration": {
        "description": "Send text to LLM API, parse structured response, validate output",
        "signature_keywords": [
            "llm", "ai", "gpt", "chatgpt", "claude", "openai", "anthropic",
            "prompt", "assistant", "interpret", "generate", "inference",
        ],
        "step_types": ["prompt_construction", "api_call", "response_parsing", "validation"],
        "default_integrations": {
            "llm_provider": {"protocol": "rest", "candidates": ["openai", "anthropic", "gemini"]},
        },
        "generates": {
            "backend": ["llm_client", "prompt_builder", "response_parser", "retry_handler"],
            "tests": ["llm_response_test", "structured_output_test"],
        },
        "template_id": "pipeline_llm_integration",
    },
    "data_transformation": {
        "description": "Transform data between formats with validation and enrichment",
        "signature_keywords": [
            "transform", "convert", "map", "enrich", "validate",
            "normalize", "clean", "format", "structure",
        ],
        "step_types": ["input_validation", "transformation", "enrichment", "output_validation"],
        "default_integrations": {},
        "generates": {
            "backend": ["transformer_service", "validator", "enrichment_service"],
            "tests": ["transformation_test", "validation_test"],
        },
        "template_id": "pipeline_data_transformation",
    },
    "approval_workflow": {
        "description": "Submit item for review, route to approver, capture decision, notify",
        "signature_keywords": [
            "approve", "reject", "review", "submit", "decision",
            "workflow", "escalate", "routing", "queue",
        ],
        "step_types": ["submission", "routing", "review", "decision", "notification"],
        "default_integrations": {
            "notification": {"protocol": "rest", "candidates": ["smtp", "sendgrid", "slack"]},
        },
        "generates": {
            "backend": ["submission_endpoint", "routing_service", "decision_endpoint", "notification_service"],
            "frontend": ["review_queue", "review_detail", "approval_buttons"],
            "tests": ["workflow_test", "routing_test"],
        },
        "template_id": "pipeline_approval_workflow",
    },
}

# ---------------------------------------------------------------------------
# Screen Flow Patterns (SFG)
# ---------------------------------------------------------------------------

SCREEN_PATTERNS: dict[str, dict[str, Any]] = {
    "file_upload_with_progress": {
        "description": "Drag-and-drop file upload with real-time processing progress",
        "signature_keywords": ["upload", "file", "document", "progress", "processing", "drag", "drop"],
        "components": ["UploadDropzone", "ProgressBar", "StatusPoller"],
        "data_flow": "file → upload endpoint → poll status → show result",
        "template_id": "screen_upload_flow",
    },
    "editable_data_table": {
        "description": "Table with inline editing, bulk actions, and export",
        "signature_keywords": ["table", "list", "edit", "review", "material", "item", "quantity", "row"],
        "components": ["DataTable", "InlineEditCell", "BulkActionBar", "FilterBar"],
        "data_flow": "fetch list → display table → edit cell → save → refresh",
        "template_id": "screen_editable_table",
    },
    "dashboard_with_metrics": {
        "description": "Overview dashboard with metric cards and status indicators",
        "signature_keywords": ["dashboard", "overview", "metric", "status", "summary", "count", "chart"],
        "components": ["MetricCard", "StatusBadge", "ActivityFeed"],
        "data_flow": "fetch metrics → display cards → auto-refresh",
        "template_id": "screen_dashboard",
    },
    "detail_view_with_actions": {
        "description": "Single item detail view with contextual action buttons",
        "signature_keywords": ["detail", "view", "single", "action", "approve", "reject", "edit"],
        "components": ["DetailHeader", "PropertyGrid", "ActionBar", "AuditTrail"],
        "data_flow": "fetch item → display properties → action → update status",
        "template_id": "screen_detail_view",
    },
}

# ---------------------------------------------------------------------------
# Matching Algorithm
# ---------------------------------------------------------------------------


def match_pipeline_to_pattern(
    pipeline: dict,
    threshold: float = 0.3,
) -> tuple[str | None, float]:
    """Match a BFG pipeline to the best behavioral code pattern.

    Args:
        pipeline: dict with keys 'name', 'description', 'steps' (list of step dicts)
        threshold: minimum score to accept a match (0-1)

    Returns:
        (pattern_id, score) or (None, 0) if no match above threshold
    """
    pipeline_text = _pipeline_to_text(pipeline)
    pipeline_tokens = _tokenize(pipeline_text)

    best_pattern = None
    best_score = 0.0

    for pattern_id, pattern in PIPELINE_PATTERNS.items():
        sig_tokens = set(pattern["signature_keywords"])
        overlap = len(pipeline_tokens & sig_tokens)
        if not sig_tokens:
            continue
        score = overlap / len(sig_tokens)
        if score > best_score:
            best_score = score
            best_pattern = pattern_id

    if best_score >= threshold:
        return best_pattern, best_score
    return None, 0.0


def match_screen_to_pattern(
    screen: dict,
    threshold: float = 0.3,
) -> tuple[str | None, float]:
    """Match an SFG screen to the best screen pattern."""
    screen_text = f"{screen.get('name', '')} {screen.get('purpose', '')} {screen.get('description', '')}"
    for action in screen.get("actions", []):
        screen_text += f" {action.get('label', '')} {action.get('effect', '')}"
    screen_tokens = _tokenize(screen_text)

    best_pattern = None
    best_score = 0.0

    for pattern_id, pattern in SCREEN_PATTERNS.items():
        sig_tokens = set(pattern["signature_keywords"])
        overlap = len(screen_tokens & sig_tokens)
        if not sig_tokens:
            continue
        score = overlap / len(sig_tokens)
        if score > best_score:
            best_score = score
            best_pattern = pattern_id

    if best_score >= threshold:
        return best_pattern, best_score
    return None, 0.0


def match_module_to_pipeline(
    component_name: str,
    component_description: str,
    pipelines: list[dict],
) -> dict | None:
    """Check if an ArchiMate component matches any extracted BFG pipeline step.

    Used by the AABL compiler to decide whether a module should be
    a pipeline service (behavioral) or a CRUD entity (structural).
    """
    comp_tokens = _tokenize(f"{component_name} {component_description}")

    for pipeline in pipelines:
        for step in pipeline.get("steps", []):
            step_tokens = _tokenize(
                f"{step.get('name', '')} {step.get('description', '')} {step.get('service', '')}"
            )
            if not step_tokens:
                continue
            overlap = len(comp_tokens & step_tokens) / max(len(step_tokens), 1)
            if overlap > 0.4:
                return pipeline

    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "to", "of",
    "in", "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "and", "or", "but", "not", "no", "all", "each", "every", "this", "that",
    "it", "its", "they", "them", "their", "we", "our", "you", "your",
})


def _tokenize(text: str) -> set[str]:
    """Lowercase, split, remove stop words, return token set."""
    tokens = set(re.split(r"[\s_\-/.,;:()]+", text.lower()))
    return tokens - _STOP_WORDS - {""}


def _pipeline_to_text(pipeline: dict) -> str:
    """Flatten a pipeline dict into searchable text."""
    parts = [
        pipeline.get("name", ""),
        pipeline.get("description", ""),
        pipeline.get("trigger", ""),
    ]
    for step in pipeline.get("steps", []):
        parts.append(step.get("name", ""))
        parts.append(step.get("description", ""))
        parts.append(step.get("service", ""))
        parts.append(step.get("input_type", ""))
        parts.append(step.get("output_type", ""))
    return " ".join(parts)
