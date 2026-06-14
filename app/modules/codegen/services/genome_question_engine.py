"""
GenomeQuestionEngine — selects the next plain-English question to ask a non-technical
user based on which required genome fields are still empty.

No LLM required. Pure logic driven by QUESTION_PRIORITY.
"""
from __future__ import annotations

from typing import Any, Optional


QUESTION_PRIORITY: list[tuple[str, str, str, bool]] = [
    (
        "problem.statement",
        "Tell me about the app you want to build — what problem does it solve and who will use it?",
        "critical",
        True,
    ),
    (
        "modules",
        "What kinds of information will the app manage? For example: appointments, orders, patients, products?",
        "critical",
        True,
    ),
    (
        "infrastructure.auth",
        "How will users log in — username and password, Google, Microsoft, or something specific to your industry?",
        "critical",
        True,
    ),
    (
        "security.multi_tenancy",
        "Will different organisations use this app with their own separate data, or is it one shared system?",
        "high",
        False,
    ),
    (
        "infrastructure.database",
        "Do you have a preference for how data is stored, or should we choose the most suitable option?",
        "high",
        False,
    ),
    (
        "notifications",
        "When something important happens, should users be notified automatically? If so, by email, SMS, or in-app?",
        "medium",
        False,
    ),
    (
        "workers",
        "Does anything need to happen automatically in the background — like sending reports or syncing data on a schedule?",
        "medium",
        False,
    ),
    (
        "file_storage",
        "Will users need to upload or attach files — like documents, images, or reports?",
        "medium",
        False,
    ),
    (
        "payments",
        "Does the app need to handle any payments or billing?",
        "medium",
        False,
    ),
    (
        "compliance",
        "Does this app handle sensitive data — like health records, financial information, or personal data covered by GDPR?",
        "medium",
        False,
    ),
    (
        "deployment",
        "Where should this app run — cloud (AWS, Azure, Google Cloud), on-premise, or should we choose?",
        "low",
        False,
    ),
]

REQUIRED_FOR_GENERATION = [
    fp for fp, _, _, req in QUESTION_PRIORITY if req
]


def _field_present(genome: dict[str, Any], field_path: str) -> bool:
    """Check if a dotted field path has a non-empty value in the genome."""
    parts = field_path.split(".")
    current: Any = genome
    for part in parts:
        if not isinstance(current, dict):
            return False
        current = current.get(part)
        if current is None:
            return False
    if isinstance(current, (dict, list)):
        return len(current) > 0
    if isinstance(current, str):
        return len(current.strip()) > 0
    return current is not None


class GenomeQuestionEngine:
    """Selects the next question to ask based on genome completeness."""

    def next_question(self, genome: dict[str, Any]) -> Optional[dict[str, Any]]:
        for field_path, question_text, priority, _ in QUESTION_PRIORITY:
            if not _field_present(genome, field_path):
                return {"field": field_path, "text": question_text, "priority": priority}
        return None

    def completeness_pct(self, genome: dict[str, Any]) -> int:
        if not genome:
            return 0
        filled = sum(1 for fp in REQUIRED_FOR_GENERATION if _field_present(genome, fp))
        return int((filled / len(REQUIRED_FOR_GENERATION)) * 100)

    def ready_to_generate(self, genome: dict[str, Any]) -> bool:
        return all(_field_present(genome, fp) for fp in REQUIRED_FOR_GENERATION)

    def missing_required_fields(self, genome: dict[str, Any]) -> list[str]:
        return [fp for fp in REQUIRED_FOR_GENERATION if not _field_present(genome, fp)]
