from app.modules.mcp.tools.element_tools import GET_ELEMENT, SEARCH_ELEMENTS

TOOL_REGISTRY = {tool.name: tool for tool in (SEARCH_ELEMENTS, GET_ELEMENT)}

__all__ = ["TOOL_REGISTRY", "SEARCH_ELEMENTS", "GET_ELEMENT"]
