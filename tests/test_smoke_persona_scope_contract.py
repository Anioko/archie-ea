"""The browser qualification matrix must cover every product persona."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _literal_assignment(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constants = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not node.targets:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(node.value, ast.Constant):
            constants[target.id] = node.value.value
        if target.id == name and isinstance(node.value, (ast.List, ast.Tuple)):
            values = []
            for element in node.value.elts:
                if isinstance(element, ast.Constant):
                    values.append(element.value)
                elif isinstance(element, ast.Name):
                    values.append(constants[element.id])
            return values
    raise AssertionError(f"{name} not found in {path}")


def test_smoke_archetypes_equal_every_valid_enterprise_role():
    valid = _literal_assignment(ROOT / "app/models/user.py", "VALID_ROLES")
    smoke = _literal_assignment(ROOT / "tests/smoke/conftest.py", "ARCHETYPES")

    assert set(smoke) == set(valid), (
        "browser qualification silently omits product personas: "
        f"missing={sorted(set(valid) - set(smoke))}, "
        f"unknown={sorted(set(smoke) - set(valid))}"
    )


def test_each_smoke_archetype_has_a_signature_journey():
    module = ast.parse(
        (ROOT / "tests/smoke/test_archetype_journeys.py").read_text(encoding="utf-8")
    )
    journey = next(
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "JOURNEY" for target in node.targets)
    )
    smoke = _literal_assignment(ROOT / "tests/smoke/conftest.py", "ARCHETYPES")

    assert set(journey) == set(smoke)
    assert all(paths for paths in journey.values())


def test_smoke_personas_do_not_all_receive_administrator_permissions():
    source = (ROOT / "tests/smoke/conftest.py").read_text(encoding="utf-8")

    assert 'architect_role = Role.query.filter_by(name="Architect").one()' in source
    assert 'administrator_role = Role.query.filter_by(name="Administrator").one()' in source
    assert 'if archetype == "platform_admin" else architect_role' in source
