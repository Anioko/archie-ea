"""AI clause extraction for vendor contracts.

Every VendorContract field the form covers today is typed by hand - dates,
notice period, auto-renew, value, currency, owner. This gives the Procurement
persona a way to paste the contract text and get a structured first pass, which
the user then reviews and applies field-by-field (or all at once) before saving
through the normal form. Nothing here writes to the database; extraction is
pure text-in, JSON-out.

Follows the prompt -> JSON -> validate pattern in
app/services/application_pattern_classifier_service.py::_llm_classify_batch
(markdown-fence tolerance, no silent fallback to fabricated data).

CLAUDE.md's never-invent-data rule applies directly here: a contract's real
notice period is either in the text or it isn't. When it isn't, the field must
be None so the form renders it as an empty input the user fills in themselves
- never a guess that looks like it was read off the page.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

MAX_CONTRACT_TEXT_CHARS = 40_000

# Keys the caller may expect on a successful extraction. Every value is either
# the type noted or null - the LLM is instructed never to guess, and this
# service does not fill gaps either.
EXTRACTED_FIELDS = (
    "contract_name",       # str | null
    "contract_number",     # str | null
    "vendor_name",         # str | null
    "start_date",          # str (YYYY-MM-DD) | null
    "end_date",             # str (YYYY-MM-DD) | null
    "renewal_date",         # str (YYYY-MM-DD) | null
    "notice_period_days",   # int | null
    "auto_renewal",          # bool | null
    "contract_value",        # number | null
    "currency",               # str (ISO 4217-ish, e.g. "USD") | null
    "payment_terms",          # str | null
    "termination_clause_summary",   # str | null
    "liability_cap",                 # str | null - often a formula/amount, kept as text
    "risk_flags",                     # list[str] | null
)


class ContractExtractionError(Exception):
    """Raised when the LLM call fails or its response cannot be trusted as JSON."""


def _strip_markdown_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(ln for ln in lines if not ln.strip().startswith("```"))
    return raw.strip()


def _build_prompt(text: str) -> str:
    return (
        "You are an enterprise contract analyst. Read the contract text below and "
        "extract ONLY facts that are explicitly present in it. Do not infer, "
        "estimate or guess a value that is not stated - if a field is not present "
        "in the text, its value MUST be null. A plausible-looking guess is worse "
        "than null, because the reader cannot tell the two apart.\n\n"
        "Respond with STRICT JSON ONLY (no markdown fences, no commentary), a single "
        "object with exactly these keys:\n"
        '  "contract_name": string or null\n'
        '  "contract_number": string or null\n'
        '  "vendor_name": string or null\n'
        '  "start_date": string "YYYY-MM-DD" or null\n'
        '  "end_date": string "YYYY-MM-DD" or null\n'
        '  "renewal_date": string "YYYY-MM-DD" or null\n'
        '  "notice_period_days": integer or null (convert e.g. "90 days notice" -> 90; '
        '"3 months notice" -> 90)\n'
        '  "auto_renewal": true, false, or null (null only if the text never addresses '
        "renewal at all)\n"
        '  "contract_value": number or null (total contract value, no currency symbol)\n'
        '  "currency": string or null (ISO-style code, e.g. "USD", "GBP", "EUR")\n'
        '  "payment_terms": string or null (e.g. "Net 30")\n'
        '  "termination_clause_summary": string or null (one or two sentences)\n'
        '  "liability_cap": string or null (as stated - amount or formula)\n'
        '  "risk_flags": array of short strings or null (e.g. unusual indemnity, '
        "unlimited liability, unilateral price escalation - only flag what the text "
        "actually supports)\n\n"
        "Contract text:\n"
        "---\n" + text + "\n---\n\n"
        "JSON:"
    )


def _validate_and_normalize(parsed: dict) -> dict:
    if not isinstance(parsed, dict):
        raise ContractExtractionError("LLM response is not a JSON object")

    result = {}
    for key in EXTRACTED_FIELDS:
        result[key] = parsed.get(key, None)

    # Type-coerce defensively rather than trusting the model's output; anything
    # that doesn't fit the expected shape becomes null rather than a value that
    # would render wrong (e.g. a stray string in a boolean field).
    if result["auto_renewal"] is not None and not isinstance(result["auto_renewal"], bool):
        result["auto_renewal"] = None

    if result["notice_period_days"] is not None:
        try:
            result["notice_period_days"] = int(result["notice_period_days"])
        except (TypeError, ValueError):
            result["notice_period_days"] = None

    if result["contract_value"] is not None:
        try:
            result["contract_value"] = float(result["contract_value"])
        except (TypeError, ValueError):
            result["contract_value"] = None

    if result["risk_flags"] is not None:
        if isinstance(result["risk_flags"], list):
            result["risk_flags"] = [str(f) for f in result["risk_flags"] if f]
            if not result["risk_flags"]:
                result["risk_flags"] = None
        else:
            result["risk_flags"] = None

    for key in ("start_date", "end_date", "renewal_date"):
        value = result[key]
        if value is not None and not isinstance(value, str):
            result[key] = None

    for key in (
        "contract_name", "contract_number", "vendor_name", "currency",
        "payment_terms", "termination_clause_summary", "liability_cap",
    ):
        value = result[key]
        if value is not None and not isinstance(value, str):
            result[key] = str(value)

    return result


def extract_contract_terms(text: str, timeout: Optional[float] = 60.0) -> dict:
    """Extract structured contract terms from pasted contract text.

    Returns a dict with exactly the keys in EXTRACTED_FIELDS. Any field the
    text does not state comes back as None - never a fabricated value.

    Raises ContractExtractionError on an LLM failure or a response that cannot
    be parsed/validated as the expected JSON shape. Callers must surface this
    as an explicit failure (502), never fall back to a synthesized result.
    """
    text = (text or "").strip()
    if not text:
        raise ContractExtractionError("text is required")

    prompt = _build_prompt(text[:MAX_CONTRACT_TEXT_CHARS])

    try:
        raw = LLMService.generate_from_prompt(prompt, use_cache=False, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - re-raised as a typed, callable-facing error
        logger.exception("Contract clause extraction LLM call failed")
        raise ContractExtractionError(str(exc)) from exc

    cleaned = _strip_markdown_fences(raw or "")
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Contract extraction returned non-JSON response: %r", cleaned[:500])
        raise ContractExtractionError(
            "The AI response could not be parsed as JSON"
        ) from exc

    return _validate_and_normalize(parsed)
