"""
MotivationModelService — keyword/regex extraction of ArchiMate motivation elements.

Extracts MotivationDriver, Goal, and Principle elements from plain text without
any LLM dependency. Results are checked against existing Principle ORM rows to
avoid duplicates.
"""
import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword lists (ArchiMate 3.2 motivation vocabulary)
# ---------------------------------------------------------------------------

# Phrases that signal an *external* driver (regulatory, market, competitive)
_EXTERNAL_DRIVER_PATTERNS = [
    r"\bregulat\w*\b",
    r"\bcomplian\w*\b",
    r"\blegislat\w*\b",
    r"\bmarket\b",
    r"\bcompetit\w*\b",
    r"\bcustomer demand\b",
    r"\bindustry standard\b",
    r"\baudit\b",
    r"\bsecurity threat\b",
    r"\bexternal\b",
    r"\bmandate\b",
]

# Phrases that signal an *internal* driver (cost, efficiency, capability gap)
_INTERNAL_DRIVER_PATTERNS = [
    r"\bcost\b",
    r"\befficienc\w*\b",
    r"\bproductivit\w*\b",
    r"\boperational\b",
    r"\binternal\b",
    r"\bcapabilit\w* gap\b",
    r"\btechnology debt\b",
    r"\btechnical debt\b",
    r"\bperforman\w*\b",
    r"\bscalab\w*\b",
    r"\bprocess improvement\b",
]

# Phrases that signal a goal
_GOAL_PATTERNS = [
    r"\bgoal\b",
    r"\bobjective\b",
    r"\baim\b",
    r"\btarget\b",
    r"\bachiev\w+\b",
    r"\bintend\w*\b",
    r"\bwant to\b",
    r"\bseek to\b",
    r"\bstrategic\b",
    r"\bimprove\b",
    r"\breduce\b",
    r"\bincrease\b",
    r"\bdeliver\b",
    r"\benable\b",
    r"\btransform\b",
]

# Phrases that signal a principle
_PRINCIPLE_PATTERNS = [
    r"\bprinciple\b",
    r"\bstandard\b",
    r"\bpolicy\b",
    r"\bmust\b",
    r"\bshall\b",
    r"\brequire\w*\b",
    r"\bguideline\b",
    r"\barchitecture rule\b",
    r"\bgovernan\w*\b",
    r"\bbest practice\b",
    r"\bcloud.first\b",
    r"\bsecurity.by.design\b",
    r"\bapi.first\b",
    r"\bzero.trust\b",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MULTI_SPACE = re.compile(r"\s+")


def _sentences(text: str) -> List[str]:
    """Split text into sentences on common delimiters."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _slug(sentence: str, max_words: int = 8) -> str:
    """Return a short slug for use as the element name."""
    words = _MULTI_SPACE.sub(" ", sentence).split()
    return " ".join(words[:max_words]).rstrip(".,;:")


def _matches_any(patterns: List[str], text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in patterns)


def _classify_driver_type(sentence: str) -> str:
    """Return 'external' or 'internal' based on keyword signals."""
    ext_score = sum(1 for p in _EXTERNAL_DRIVER_PATTERNS if re.search(p, sentence.lower()))
    int_score = sum(1 for p in _INTERNAL_DRIVER_PATTERNS if re.search(p, sentence.lower()))
    return "external" if ext_score >= int_score else "internal"


def _confidence(drivers: list, goals: list, principles: list, total_sentences: int) -> float:
    """Rough confidence: ratio of sentences that yielded at least one element."""
    hits = len(drivers) + len(goals) + len(principles)
    if total_sentences == 0:
        return 0.0
    raw = min(1.0, hits / max(total_sentences, 1))
    # Scale to a [0.3, 0.9] range — pure regex never reaches 1.0
    return round(0.3 + raw * 0.6, 3)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_motivation_model(text: str, instance_id: int) -> Dict[str, Any]:
    """
    Extract ArchiMate motivation elements from *plain text* using keyword/regex
    matching.  No LLM or network calls are made.

    Args:
        text:        Free-form document text (strategy brief, requirements doc, …)
        instance_id: The solution/architecture instance this extraction belongs to.
                     Used to check for duplicate Principle rows in the DB.

    Returns:
        {
            "drivers":    [{"name": str, "description": str, "type": "external"|"internal"}],
            "goals":      [{"name": str, "description": str, "type": "goal"}],
            "principles": [{"name": str, "description": str, "type": "principle",
                            "existing_id": int|None}],
            "confidence": float,
        }
    """
    if not text or not text.strip():
        return {"drivers": [], "goals": [], "principles": [], "confidence": 0.0}

    sentences = _sentences(text)
    drivers: List[Dict[str, Any]] = []
    goals: List[Dict[str, Any]] = []
    principles: List[Dict[str, Any]] = []

    seen_names: Dict[str, str] = {}  # name_lower -> category, for dedup

    for sentence in sentences:
        is_driver = _matches_any(_EXTERNAL_DRIVER_PATTERNS + _INTERNAL_DRIVER_PATTERNS, sentence)
        is_goal = _matches_any(_GOAL_PATTERNS, sentence)
        is_principle = _matches_any(_PRINCIPLE_PATTERNS, sentence)

        # A sentence can yield at most one element; priority: principle > goal > driver
        if is_principle:
            name = _slug(sentence)
            key = name.lower()
            if key not in seen_names:
                seen_names[key] = "principle"
                principles.append(
                    {"name": name, "description": sentence, "type": "principle", "existing_id": None}
                )
        elif is_goal:
            name = _slug(sentence)
            key = name.lower()
            if key not in seen_names:
                seen_names[key] = "goal"
                goals.append({"name": name, "description": sentence, "type": "goal"})
        elif is_driver:
            name = _slug(sentence)
            key = name.lower()
            if key not in seen_names:
                seen_names[key] = "driver"
                dtype = _classify_driver_type(sentence)
                drivers.append({"name": name, "description": sentence, "type": dtype})

    # Check existing Principle rows for name matches
    _annotate_existing_principles(principles)

    confidence = _confidence(drivers, goals, principles, len(sentences))
    logger.debug(
        "BA-006 extract_motivation_model: instance=%d sentences=%d "
        "drivers=%d goals=%d principles=%d confidence=%.3f",
        instance_id,
        len(sentences),
        len(drivers),
        len(goals),
        len(principles),
        confidence,
    )

    return {
        "drivers": drivers,
        "goals": goals,
        "principles": principles,
        "confidence": confidence,
    }


def _annotate_existing_principles(principles: List[Dict[str, Any]]) -> None:
    """
    For each extracted principle, check whether a Principle with the same name
    already exists in the DB and populate existing_id if found.

    Silently no-ops when there is no application context (e.g., unit tests
    running outside Flask).
    """
    if not principles:
        return
    try:
        from app.models.models import Principle  # noqa: PLC0415
        from app import db  # noqa: PLC0415

        names = [p["name"].lower() for p in principles]
        existing = (
            db.session.query(Principle.id, Principle.name)
            .filter(db.func.lower(Principle.name).in_(names))
            .all()
        )
        existing_map = {row.name.lower(): row.id for row in existing}
        for principle in principles:
            principle["existing_id"] = existing_map.get(principle["name"].lower())
    except Exception as exc:  # noqa: BLE001
        logger.debug("_annotate_existing_principles skipped: %s", exc)
