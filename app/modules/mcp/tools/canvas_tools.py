"""Canvas tools: list_canvases, get_canvas.

list_canvases wraps the Business Model Canvas list and Business Case list
JSON API endpoints. get_canvas wraps the detail JSON API endpoints.
"""

from __future__ import annotations

from app.utils.text_sanitization import fence_response_strings
from app.utils.internal_api import call_internal_api
from app.modules.mcp.tools import register_tool


def _call_canvas_list() -> dict:
    """Call the Business Model Canvas and Business Case list JSON APIs."""
    _status, bmc_data = call_internal_api(
        "GET", "/business-model/api/list", pass_session=True
    )
    _status, bc_data = call_internal_api(
        "GET", "/business-case/api/list", pass_session=True
    )

    bmc_list = (bmc_data.get("data") or []) if isinstance(bmc_data, dict) else []
    bc_list = (bc_data.get("data") or []) if isinstance(bc_data, dict) else []
    fence_response_strings(bmc_list)
    fence_response_strings(bc_list)

    return {
        "business_model_canvases": bmc_list,
        "business_cases": bc_list,
    }


@register_tool(
    name="list_canvases",
    description="List all Business Model Canvases and Business Cases "
                "for the current organisation.",
    input_schema={
        "type": "object",
        "properties": {},
    },
)
def list_canvases(args: dict) -> dict:
    return _call_canvas_list()


@register_tool(
    name="get_canvas",
    description="Get the full detail of one Business Model Canvas or Business Case.",
    input_schema={
        "type": "object",
        "properties": {
            "canvas_type": {
                "type": "string",
                "description": "Either 'business_model' or 'business_case'",
                "enum": ["business_model", "business_case"],
            },
            "canvas_id": {
                "type": "integer",
                "description": "The canvas or business case id",
            },
        },
        "required": ["canvas_type", "canvas_id"],
    },
)
def get_canvas(args: dict) -> dict:
    canvas_type = str(args["canvas_type"])
    canvas_id = int(args["canvas_id"])

    if canvas_type == "business_model":
        status, data = call_internal_api(
            "GET", f"/business-model/api/{canvas_id}", pass_session=True
        )
        if status != 200 or not (isinstance(data, dict) and data.get("success")):
            return {"success": False, "error": {"code": "NOT_FOUND", "message": "Business Model Canvas not found"}}
        canvas_data = data["data"]
        fence_response_strings(canvas_data)
        return {"success": True, "data": canvas_data}

    elif canvas_type == "business_case":
        status, data = call_internal_api(
            "GET", f"/business-case/api/{canvas_id}", pass_session=True
        )
        if status != 200 or not (isinstance(data, dict) and data.get("success")):
            return {"success": False, "error": {"code": "NOT_FOUND", "message": "Business Case not found"}}
        case_data = data["data"]
        fence_response_strings(case_data)
        return {"success": True, "data": case_data}

    return {"success": False, "error": {"code": "INVALID_PARAMETER",
            "message": f"Unknown canvas_type: {canvas_type}"}}