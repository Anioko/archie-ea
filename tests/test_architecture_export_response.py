"""Execute the actual export handler with a file-service boundary double.

Authentication/tenant isolation are deliberately not claimed by these tests.
"""
import ast
import os
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, after_this_request, current_app, jsonify, request, send_file
from werkzeug.wsgi import ClosingIterator
import pytest


@pytest.mark.parametrize("format_type,mime,status", [
    ("csv", "text/csv", 200), ("json", "application/json", 200),
    ("xml", "application/json", 400), ("nonsense", "application/json", 400),
])
def test_export_response_contract(tmp_path, format_type, mime, status):
    root = Path(__file__).resolve().parents[1]
    source = root / "app/modules/architecture/routes/architecture_crud_routes.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    handler = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "export_architecture")
    handler.decorator_list = []
    calls = []
    def export_data(kind):
        calls.append(kind)
        path = tmp_path / ("download." + kind)
        path.write_text('{"elements": []}' if kind == "json" else "id,name\n1,QA\n", encoding="utf-8")
        return str(path), path.name
    namespace = dict(after_this_request=after_this_request, current_app=current_app,
                     jsonify=jsonify, request=request, send_file=send_file, os=os,
                     ClosingIterator=ClosingIterator,
                     import_export_service=SimpleNamespace(export_data=export_data))
    exec(compile(ast.Module(body=[handler], type_ignores=[]), str(source), "exec"), namespace)
    app = Flask(__name__)
    app.add_url_rule("/export", view_func=namespace["export_architecture"])
    with app.test_client() as client:
        response = client.get("/export?format=" + format_type)
        try:
            assert response.status_code == status
            assert response.mimetype == mime
            if status == 200:
                assert "attachment" in response.headers["Content-Disposition"]
                assert response.data
                assert calls == [format_type]
                assert (tmp_path / ("download." + format_type)).exists()
            else:
                assert calls == [], "Unsupported format must not silently export CSV"
        finally:
            response.close()
        assert not list(tmp_path.iterdir()), "Export temporary files must be removed after stream close"
