"""LiveMigrationService.generate_model_code_patch interpolated an
architect-supplied default_value directly into a generated Python string
literal with no escaping -- a literal '"' would break out of the literal
and corrupt the generated model patch. Found 11 Sep 2026 while triaging the
raw-html-escaping gate.
"""
import ast

from app.modules.codegen.services.live_migration_service import LiveMigrationService


def test_generate_model_code_patch_escapes_quote_in_default():
    svc = LiveMigrationService()
    patch = svc.generate_model_code_patch(
        entity_name="Widget", field_name="label", field_type="string",
        default_value='a" + __import__("os").system("rm -rf /") + "b',
    )
    # The generated patch must still be syntactically valid Python -- it
    # wasn't, before this fix, because the unescaped '"' closed the string
    # literal early and turned the rest into a bare expression.
    module = ast.parse(patch.strip())
    assert isinstance(module.body[0], ast.Assign)
