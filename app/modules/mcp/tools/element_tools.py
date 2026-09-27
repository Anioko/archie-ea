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
    # The one canonical element search — the same route the product's own
    # entity picker calls (docs/artifacts/reuse-register.yml, id
    # element-picker). Never a duplicate route.
    params = {}
    if arguments.get("q"):
        params["q"] = arguments["q"]
    if arguments.get("limit"):
        params["limit"] = arguments["limit"]
    return call_internal_api(
        "GET", "/archimate/api/elements/search", params=params, bearer=bearer
    )


def _get_element(arguments: dict, bearer: str) -> InternalAPIResult:
    element_id = arguments.get("element_id")
    return call_internal_api(
        "GET", f"/archimate/api/elements/{element_id}/detail", bearer=bearer
    )


SEARCH_ELEMENTS = Tool(
    name="search_elements",
    title="Search architecture elements",
    description="Find architecture elements by name; returns the id each lens question needs.",
    input_schema={
        "type": "object",
        "properties": {
            "q": {"type": "string", "description": "Case-insensitive name search"},
            "limit": {"type": "integer", "description": "Maximum number of results"},
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
