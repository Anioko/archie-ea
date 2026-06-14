"""Behavioral Extractor — extracts BFG and SFG from solution documents.

Reads the solution's problem statement and uploaded source documents,
then uses two LLM calls to extract:
  1. Behavioral Flow Graph (BFG): data processing pipelines with steps,
     integration contracts, and quality constraints
  2. Screen Flow Graph (SFG): user journeys with screens, data bindings,
     actions, and transitions

The output is a BehavioralContext that the AABL compiler uses to build
pipeline modules (instead of CRUD) for matched components.

Pipeline position:
  Source Documents → BehavioralExtractor → BehavioralContext
  BehavioralContext + ArchiMate → AABL Compiler → enriched Genome
"""
import io
import json
import logging
import os
import re
from dataclasses import dataclass, field

from app.models.solution_models import Solution

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class PipelineStep:
    name: str
    description: str = ""
    service: str = "internal"  # "internal", "openai", "pdf_ai", etc.
    input_type: str = "any"
    output_type: str = "any"
    integration: str | None = None
    quality_constraint: dict | None = None  # e.g. {"accuracy": 0.995}
    error_handling: str = "raise"  # "raise", "retry", "fallback", "skip"


@dataclass
class Pipeline:
    name: str
    description: str = ""
    trigger: str = "api_call"  # "api_call", "file_upload", "email", "schedule", "event"
    steps: list[PipelineStep] = field(default_factory=list)
    output_type: str = "dict"
    sla: dict | None = None  # e.g. {"max_duration_seconds": 60}
    error_handling: str = "retry_with_backoff"


@dataclass
class ScreenAction:
    label: str
    effect: str = ""
    next_screen: str | None = None
    api_call: str | None = None  # e.g. "POST /api/documents/{id}/submit"


@dataclass
class DataBinding:
    field_name: str
    source: str = ""  # "api", "local_state", "url_param"
    editable: bool = False
    widget: str = "text"  # "text", "number", "dropdown", "file_picker", "progress_bar"
    validation: str | None = None


@dataclass
class Screen:
    name: str
    purpose: str = ""
    route: str = ""  # e.g. "/documents/{id}"
    data_bindings: list[DataBinding] = field(default_factory=list)
    actions: list[ScreenAction] = field(default_factory=list)
    transitions_to: list[str] = field(default_factory=list)
    primary_entity: str | None = None


@dataclass
class IntegrationContract:
    name: str
    service: str  # "openai", "pdf_ai", "imap", etc.
    protocol: str = "rest"  # "rest", "imap", "grpc", "websocket"
    auth_method: str = "bearer"  # "bearer", "api_key", "basic", "none"
    data_format: str = "json"
    base_url: str = ""
    operations: list[str] = field(default_factory=list)


@dataclass
class DataContract:
    name: str
    fields: list[dict] = field(default_factory=list)  # [{name, type, required}]
    used_by_pipelines: list[str] = field(default_factory=list)
    used_by_screens: list[str] = field(default_factory=list)


@dataclass
class BehavioralContext:
    pipelines: list[Pipeline] = field(default_factory=list)
    screens: list[Screen] = field(default_factory=list)
    integrations: list[IntegrationContract] = field(default_factory=list)
    data_contracts: list[DataContract] = field(default_factory=list)
    quality_constraints: list[dict] = field(default_factory=list)
    raw_bfg: dict | None = None
    raw_sfg: dict | None = None


# ---------------------------------------------------------------------------
# Extraction Prompts
# ---------------------------------------------------------------------------

BFG_EXTRACTION_PROMPT = """You are a software architect analyzing a requirements document.
Extract ALL data processing pipelines described in this document.

For each pipeline, identify:
1. Name and description
2. Trigger (what starts it: file_upload, email_arrival, api_call, schedule)
3. Ordered steps — for each step:
   - Name (verb_noun format, e.g. "extract_text", "parse_materials")
   - Description
   - External service if any (e.g. "openai", "pdf_ai", "ocr_service")
   - Input type and output type
   - Quality constraints (accuracy targets, SLA times, error rates)
4. Error handling strategy
5. Integration contracts — external APIs needed with protocol and auth method

Return ONLY valid JSON:
{
  "pipelines": [
    {
      "name": "pipeline_name",
      "description": "what it does end-to-end",
      "trigger": "file_upload",
      "steps": [
        {
          "name": "step_name",
          "description": "what this step does",
          "service": "external_service_name or internal",
          "input_type": "bytes|str|json|SpecificType",
          "output_type": "str|json|SpecificType",
          "quality_constraint": {"accuracy": 0.995} or null
        }
      ],
      "sla": {"max_duration_seconds": 60} or null,
      "error_handling": "retry_with_backoff"
    }
  ],
  "integrations": [
    {
      "name": "service_name",
      "service": "openai",
      "protocol": "rest",
      "auth_method": "bearer",
      "data_format": "json",
      "operations": ["parse_document", "extract_materials"]
    }
  ],
  "quality_constraints": [
    {"metric": "sku_matching_accuracy", "target": 0.995, "description": "..."},
    {"metric": "processing_time", "target_seconds": 60, "description": "..."}
  ]
}

DOCUMENT TEXT:
"""

SFG_EXTRACTION_PROMPT = """You are a UX architect analyzing a requirements document.
Extract ALL user-facing screens and journeys described in this document.

For each screen, identify:
1. Name and purpose
2. Route pattern (e.g. "/documents/{id}")
3. Data displayed — for each field: name, source (api/state), editable?, widget type
4. Actions available — for each: label, effect, which screen it navigates to, API call
5. Primary data entity

Return ONLY valid JSON:
{
  "screens": [
    {
      "name": "Screen Name",
      "purpose": "what the user does here",
      "route": "/path/pattern",
      "primary_entity": "EntityName",
      "data_bindings": [
        {"field_name": "material_name", "source": "api", "editable": false, "widget": "text"},
        {"field_name": "quantity", "source": "api", "editable": true, "widget": "number"}
      ],
      "actions": [
        {"label": "Submit", "effect": "submit_for_processing", "next_screen": "Status View", "api_call": "POST /api/items/{id}/submit"},
        {"label": "Back", "effect": "navigate_back", "next_screen": "Dashboard", "api_call": null}
      ]
    }
  ],
  "data_contracts": [
    {
      "name": "ExtractedMaterial",
      "fields": [
        {"name": "material_name", "type": "string", "required": true},
        {"name": "quantity", "type": "number", "required": true},
        {"name": "unit", "type": "string", "required": true}
      ],
      "used_by_screens": ["Material Review", "Quote Builder"]
    }
  ]
}

DOCUMENT TEXT:
"""


# ---------------------------------------------------------------------------
# Extractor Service
# ---------------------------------------------------------------------------

class BehavioralExtractorService:
    """Extract behavioral context from a solution's documents."""

    def extract(self, solution_id: int) -> BehavioralContext:
        """Main entry point — reads solution docs, calls LLM, returns context."""
        text = self._gather_text(solution_id)
        if not text or len(text.strip()) < 50:
            logger.info("No meaningful text for behavioral extraction (solution %d)", solution_id)
            return BehavioralContext()

        # Truncate to avoid token limits (keep first ~8000 words)
        words = text.split()
        if len(words) > 8000:
            text = " ".join(words[:8000])

        bfg_raw = self._extract_bfg(text)
        sfg_raw = self._extract_sfg(text)

        return self._parse_results(bfg_raw, sfg_raw)

    def _gather_text(self, solution_id: int) -> str:
        """Collect all text from solution: description + uploaded documents."""
        solution = Solution.query.get(solution_id)
        if not solution:
            return ""

        parts = []

        # Problem statement / description
        if solution.description:
            parts.append(solution.description)
        if solution.problem_clarification:
            parts.append(solution.problem_clarification)

        # Uploaded source documents (PDF, DOCX, TXT, MD)
        try:
            from flask import current_app
            upload_dir = os.path.join(
                current_app.root_path, "uploads", "solution_documents", str(solution_id)
            )
            if os.path.isdir(upload_dir):
                for fn in sorted(os.listdir(upload_dir)):
                    fpath = os.path.join(upload_dir, fn)
                    if not os.path.isfile(fpath):
                        continue
                    ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
                    try:
                        text_content = self._read_document(fpath, ext)
                        if text_content and text_content.strip():
                            parts.append(text_content)
                    except Exception as doc_err:
                        logger.debug("Could not read %s: %s", fn, doc_err)
        except Exception as e:
            logger.debug("Could not read source documents: %s", e)

        # Journey state data (capabilities, gaps, options, roadmap, arb_draft)
        if solution.journey_state and isinstance(solution.journey_state, dict):
            js = solution.journey_state
            for key in ("arb_draft", "gaps", "options", "roadmap"):
                val = js.get(key)
                if val:
                    parts.append(json.dumps(val, default=str))

        return "\n\n".join(parts)

    @staticmethod
    def _read_document(fpath: str, ext: str) -> str:
        """Extract text from a document file. Supports .txt, .md, .pdf, .docx."""
        if ext in ("txt", "md", "csv"):
            with open(fpath, encoding="utf-8", errors="ignore") as f:
                return f.read()
        if ext == "pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(fpath)
                return "\n".join(
                    page.extract_text() or "" for page in reader.pages[:20]
                )
            except ImportError:
                logger.debug("pypdf not installed — skipping %s", fpath)
                return ""
        if ext == "docx":
            try:
                import docx as _docx
                doc = _docx.Document(fpath)
                return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except ImportError:
                logger.debug("python-docx not installed — skipping %s", fpath)
                return ""
        # Fallback: try UTF-8 decode
        with open(fpath, encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _extract_bfg(self, text: str) -> dict:
        """Call LLM to extract Behavioral Flow Graph."""
        prompt = BFG_EXTRACTION_PROMPT + text
        return self._call_llm_json(prompt)

    def _extract_sfg(self, text: str) -> dict:
        """Call LLM to extract Screen Flow Graph."""
        prompt = SFG_EXTRACTION_PROMPT + text
        return self._call_llm_json(prompt)

    def _call_llm_json(self, prompt: str) -> dict:
        """Call the configured LLM and parse JSON response."""
        try:
            from app.modules.ai_chat.services.llm_service import LLMService
            provider, model = LLMService._get_configured_provider()
            raw_text, _ = LLMService._call_llm(prompt=prompt, model=model, provider=provider)

            if not raw_text:
                return {}

            # Extract JSON from response (may be wrapped in markdown code blocks
            # or preceded/followed by prose)
            json_str = raw_text.strip()

            # Strip markdown fences (```json ... ``` or ``` ... ```)
            fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", json_str, re.DOTALL)
            if fence_match:
                json_str = fence_match.group(1).strip()

            # If still not valid JSON, find the first { and last }
            if not json_str.startswith("{"):
                start = json_str.find("{")
                if start >= 0:
                    end = json_str.rfind("}")
                    if end > start:
                        json_str = json_str[start:end + 1]

            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("BFG/SFG extraction returned invalid JSON: %s", e)
            return {}
        except Exception as e:
            logger.warning("BFG/SFG extraction LLM call failed: %s", e)
            return {}

    def _parse_results(self, bfg_raw: dict, sfg_raw: dict) -> BehavioralContext:
        """Convert raw LLM JSON into typed BehavioralContext dataclass."""
        pipelines = []
        for p in (bfg_raw.get("pipelines") or []):
            steps = []
            for s in (p.get("steps") or []):
                steps.append(PipelineStep(
                    name=s.get("name", "unknown_step"),
                    description=s.get("description", ""),
                    service=s.get("service", "internal"),
                    input_type=s.get("input_type", "any"),
                    output_type=s.get("output_type", "any"),
                    integration=s.get("service") if s.get("service") != "internal" else None,
                    quality_constraint=s.get("quality_constraint") if isinstance(s.get("quality_constraint"), dict) else None,
                    error_handling=s.get("error_handling", "raise"),
                ))
            pipelines.append(Pipeline(
                name=p.get("name", "unnamed_pipeline"),
                description=p.get("description", ""),
                trigger=p.get("trigger", "api_call"),
                steps=steps,
                output_type=p.get("output_type", "dict"),
                sla=p.get("sla"),
                error_handling=p.get("error_handling", "retry_with_backoff"),
            ))

        integrations = []
        for i in (bfg_raw.get("integrations") or []):
            integrations.append(IntegrationContract(
                name=i.get("name", "unknown"),
                service=i.get("service", "unknown"),
                protocol=i.get("protocol", "rest"),
                auth_method=i.get("auth_method", "bearer"),
                data_format=i.get("data_format", "json"),
                base_url=i.get("base_url", ""),
                operations=i.get("operations") or [],
            ))

        screens = []
        for s in (sfg_raw.get("screens") or []):
            bindings = [
                DataBinding(
                    field_name=b.get("field_name", ""),
                    source=b.get("source", "api"),
                    editable=bool(b.get("editable", False)),
                    widget=b.get("widget", "text"),
                    validation=b.get("validation"),
                )
                for b in (s.get("data_bindings") or [])
            ]
            actions = [
                ScreenAction(
                    label=a.get("label", ""),
                    effect=a.get("effect", ""),
                    next_screen=a.get("next_screen"),
                    api_call=a.get("api_call"),
                )
                for a in (s.get("actions") or [])
            ]
            screens.append(Screen(
                name=s.get("name", "Unnamed Screen"),
                purpose=s.get("purpose", ""),
                route=s.get("route", ""),
                data_bindings=bindings,
                actions=actions,
                transitions_to=[a.next_screen for a in actions if a.next_screen],
                primary_entity=s.get("primary_entity"),
            ))

        data_contracts = []
        for dc in (sfg_raw.get("data_contracts") or []):
            data_contracts.append(DataContract(
                name=dc.get("name", "Unknown"),
                fields=dc.get("fields") or [],
                used_by_screens=dc.get("used_by_screens") or [],
                used_by_pipelines=dc.get("used_by_pipelines") or [],
            ))

        return BehavioralContext(
            pipelines=pipelines,
            screens=screens,
            integrations=integrations,
            data_contracts=data_contracts,
            quality_constraints=bfg_raw.get("quality_constraints") or [],
            raw_bfg=bfg_raw,
            raw_sfg=sfg_raw,
        )
