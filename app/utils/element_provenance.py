"""Element provenance tagging for AI-generated architecture elements.

Tags generated elements with phase, timestamp, and model version
so users can distinguish AI-generated from manually-created elements.
"""

from datetime import datetime, timezone


def tag_provenance(element_dict: dict, phase: str, model_version: str = "deterministic") -> dict:
    """Add provenance metadata to an element dict before persistence.

    Args:
        element_dict: The element data dict (will be modified in-place)
        phase: The generating phase ('A', 'B', ..., 'T')
        model_version: The model/algorithm that generated it

    Returns:
        The element dict with provenance fields added
    """
    element_dict["generated_by"] = f"phase_{phase}"
    element_dict["generated_at"] = datetime.now(timezone.utc).isoformat()
    element_dict["generated_with"] = model_version
    return element_dict


def is_generated(element_dict: dict) -> bool:
    """Check if an element was AI-generated (has provenance metadata)."""
    return bool(element_dict.get("generated_by"))


def strip_provenance(element_dict: dict) -> dict:
    """Remove provenance metadata (for rollback/manual override)."""
    for key in ("generated_by", "generated_at", "generated_with"):
        element_dict.pop(key, None)
    return element_dict
