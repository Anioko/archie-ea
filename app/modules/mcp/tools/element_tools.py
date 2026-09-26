"""Element search and detail tools: search_elements, get_element.

search_elements wraps the canonical GET /archimate/api/elements/search
route only, not one of the other routes in the codebase that also search
elements. get_element wraps GET /archimate/api/elements/<id>/detail.
"""

from __future__ import annotations

from app.utils.text_sanitization import fence_response_strings
from app.utils.internal_api import call_internal_api
from app.modules.mcp.tools import register_tool


def _call_element_search(query: str, limit: int = 30) -> dict:
    """Call the canonical element search route."""
    _status, data = call_internal_api(
        "GET", "/archimate/api/elements/search",
        query_string={"q": query, "limit": limit},
        pass_session=True,
    )
    return data


def _call_element_detail(element_id: int) -> dict:
    """Call the element detail route."""
    _status, data = call_internal_api(
        "GET", f"/archimate/api/elements/{element_id}/detail",
        pass_session=True,
    )
    return data


@register_tool(
    name="search_elements",
    description="Search ArchiMate elements by name. Returns matching elements "
                "with their id, name, type, and layer — the identifiers the "
                "lens tools need as input.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Name substring to search for (case-insensitive)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return (default 30, max 200)",
            },
        },
        "required": ["query"],
    },
)
def search_elements(args: dict) -> dict:
    query = str(args["query"])
    limit = int(args.get("limit", 30))
    result = _call_element_search(query, limit)
    if result and result.get("data"):
        fence_response_strings(result["data"])
    return result


@register_tool(
    name="get_element",
    description="Get the full detail for one ArchiMate element: its type, "
                "layer, description, linked solutions and capabilities.",
    input_schema={
        "type": "object",
        "properties": {
            "element_id": {
                "type": "integer",
                "description": "The ArchiMate element id to fetch",
            },
        },
        "required": ["element_id"],
    },
)
def get_element(args: dict) -> dict:
    element_id = int(args["element_id"])
    result = _call_element_detail(element_id)
    if isinstance(result, dict):
        fence_response_strings(result)
    return result