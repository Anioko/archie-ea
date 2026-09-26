"""Element tools — the two MCP tools that read architecture elements.

Every tool reaches data only through ``app.utils.internal_api``. Nothing
here imports a model, a service, or ``db``, and nothing calls a view
function directly — the same contract every MCP tool must follow.
"""
from __future__ import annotations

from typing import Callable, Optional

from app.utils.internal_api import InternalAPIResult, call_internal_api


class Tool:
    def __init__(
        self,
        name: str,
        title: str,
        description: str,
        input_schema: dict,
        required_scope: str,
        handler: Callable[[dict, str], InternalAPIResult],
        source_id: Callable[[dict, InternalAPIResult], Optional[str]],
    ):
        self.name = name
        self.title = title
        self.description = description
        self.input_schema = input_schema
        self.required_scope = required_scope
        self._handler = handler
        self._source_id = source_id

    def call(self, arguments: dict, bearer: str) -> InternalAPIResult:
        return self._handler(arguments, bearer)

    def source_id(self, arguments: dict, result: InternalAPIResult) -> Optional[str]:
        return self._source_id(arguments, result)


def _search_elements(arguments: dict, bearer: str) -> InternalAPIResult:
    params = {}
    for key in ("q", "type", "layer"):
        if arguments.get(key):
            params[key] = arguments[key]
    return call_internal_api("GET", "/architecture/api/elements", params=params, bearer=bearer)


def _get_element(arguments: dict, bearer: str) -> InternalAPIResult:
    element_id = arguments.get("element_id")
    return call_internal_api("GET", f"/architecture/api/elements/{element_id}", bearer=bearer)


SEARCH_ELEMENTS = Tool(
    name="search_elements",
    title="Search architecture elements",
    description="Search architecture elements by name, type, and ArchiMate layer.",
    input_schema={
        "type": "object",
        "properties": {
            "q": {"type": "string", "description": "Case-insensitive name search"},
            "type": {"type": "string", "description": "ArchiMate element type, e.g. ApplicationComponent"},
            "layer": {"type": "string", "description": "ArchiMate layer, e.g. application"},
        },
    },
    required_scope="mcp:read",
    handler=_search_elements,
    source_id=lambda arguments, result: None,
)

GET_ELEMENT = Tool(
    name="get_element",
    title="Get an architecture element",
    description="Get a single architecture element by id.",
    input_schema={
        "type": "object",
        "properties": {
            "element_id": {"type": "integer", "description": "The element's numeric id"},
        },
        "required": ["element_id"],
    },
    required_scope="mcp:read",
    handler=_get_element,
    source_id=lambda arguments, result: str(arguments.get("element_id")) if arguments.get("element_id") else None,
)
