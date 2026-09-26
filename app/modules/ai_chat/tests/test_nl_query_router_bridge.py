"""Regression coverage for NLQueryRouter._call_api after it was refactored to
delegate to app.utils.internal_api.call_internal_api (the shared bridge also
used by MCP tools). Behaviour is unchanged: a GET pattern still calls with
query_string=api_params, a POST pattern still calls with json=api_params, a
200 response still returns its JSON body, and any other status still returns
{} (so the formatter falls through to a "no results" message) — exactly the
same as the inline test_client() implementation this replaced.
"""
from unittest.mock import MagicMock, patch

from app.modules.ai_chat.services.nl_query_router import NLQueryRouter
from app.utils.internal_api import InternalAPIResult


def _router():
    return NLQueryRouter()


class TestCallApiBridgeDelegation:
    def test_get_pattern_success_returns_json_body(self):
        router = _router()
        fake_result = InternalAPIResult(200, {"rows": [1, 2, 3]}, b'{"rows": [1, 2, 3]}', 1.0)

        with patch(
            "app.utils.internal_api.call_internal_api",
            return_value=fake_result,
        ) as mocked:
            data = router._call_api({
                "api_method": "GET",
                "api_path": "/api/applications/table-data",
                "api_params": {"page": 1},
            })

        assert data == {"rows": [1, 2, 3]}
        mocked.assert_called_once_with(
            "GET", "/api/applications/table-data",
            params={"page": 1}, json_body=None, pass_session=True,
        )

    def test_post_pattern_forwards_json_body_not_query_string(self):
        router = _router()
        fake_result = InternalAPIResult(200, {"ok": True}, b'{"ok": true}', 1.0)

        with patch(
            "app.utils.internal_api.call_internal_api",
            return_value=fake_result,
        ) as mocked:
            router._call_api({
                "api_method": "POST",
                "api_path": "/api/some/action",
                "api_params": {"id": 5},
            })

        mocked.assert_called_once_with(
            "POST", "/api/some/action",
            params=None, json_body={"id": 5}, pass_session=True,
        )

    def test_non_200_status_returns_empty_dict(self):
        router = _router()
        fake_result = InternalAPIResult(403, None, b"forbidden", 1.0)

        with patch(
            "app.utils.internal_api.call_internal_api",
            return_value=fake_result,
        ):
            data = router._call_api({
                "api_method": "GET",
                "api_path": "/api/applications/table-data",
                "api_params": {},
            })

        assert data == {}
