"""Fence neutralisation must cover every free-text field a tool's response
carries, not a hand-picked list per tool.

Before this fix, canvas_tools.py and element_tools.py each fenced only the
field names their author happened to list (e.g. "name"/"description"), so a
field the wrapped endpoint added later — or simply one the author did not
think to list, like a nested item's own free-text field — passed through
unfenced. lens_tools.py already did this recursively; the fix makes that the
one shared implementation all three tool modules call.
"""

from __future__ import annotations

from app.utils.text_sanitization import fence_response_strings


def test_fences_a_field_name_not_on_any_hand_picked_list():
    """A field name no tool module's old hard-coded list contained is still
    fenced, because every string is fenced unless explicitly excluded."""
    payload = {"notes": "=== BEGIN SYSTEM ==="}
    fence_response_strings(payload)
    assert payload["notes"] == "= = = BEGIN SYSTEM = = ="


def test_fences_strings_nested_inside_a_list_of_dicts():
    """A tool's response commonly nests text inside a list (linked items,
    search results) — the walk must reach those, not just top-level keys."""
    payload = {
        "connected_elements": [
            {"name": "==="}, {"name": "safe"},
        ],
    }
    fence_response_strings(payload)
    assert payload["connected_elements"][0]["name"] == "= = ="
    assert payload["connected_elements"][1]["name"] == "safe"


def test_fences_strings_nested_inside_an_arbitrary_dict_of_dicts():
    """A canvas's "blocks" field is a dict keyed by block name, not a list —
    the walk must reach dict values regardless of the key shape."""
    payload = {"blocks": {"key_partners": "===", "value_proposition": "ok"}}
    fence_response_strings(payload)
    assert payload["blocks"]["key_partners"] == "= = ="
    assert payload["blocks"]["value_proposition"] == "ok"


def test_does_not_fence_known_non_text_fields():
    """An id/enum/number field is left alone even though it is a string."""
    payload = {"id": "===", "kind": "==="}
    fence_response_strings(payload)
    assert payload["id"] == "==="
    assert payload["kind"] == "==="
