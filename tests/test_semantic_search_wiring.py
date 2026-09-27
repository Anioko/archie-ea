"""SemanticSearchService must be obtained through its factory.

Regression test for the finding on 2026-07-30. SemanticSearchService requires a
VectorEmbeddingService, and every caller in the codebase got it wrong:

    workspace_ai_service.py     SemanticSearchService()            -> TypeError
    architecture_generation.py  SemanticSearchService.semantic_search(...)
                                called on the CLASS, so `self` was never bound
                                and `query` was consumed as `self`

Both sites sit inside broad `except Exception` blocks that fall back to a flat
list, so semantic search silently degraded rather than failing. It had almost
certainly never worked in production.

These are static checks on purpose: constructing the real service pulls in the
embedding stack and a FAISS index, which is far too heavy for a unit test, and
the defect being guarded is a wiring mistake visible in the source.
"""

import ast
import io
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SERVICE_MODULE = os.path.join(REPO_ROOT, "app", "services", "semantic_search_service.py")
CALLERS = [
    os.path.join(REPO_ROOT, "app", "modules", "ai_chat", "services", "workspace_ai_service.py"),
    os.path.join(REPO_ROOT, "app", "modules", "architecture_assistant", "architecture_generation.py"),
]


def _parse(path):
    return ast.parse(io.open(path, encoding="utf-8").read(), filename=path)


def test_factory_exists_and_is_module_level():
    tree = _parse(SERVICE_MODULE)
    names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    assert "get_semantic_search_service" in names, (
        "get_semantic_search_service() is the supported way to obtain the service; "
        "callers must not have to know it needs a VectorEmbeddingService"
    )


def test_service_still_requires_its_dependency():
    """The factory exists because the dependency is mandatory - keep that true."""
    tree = _parse(SERVICE_MODULE)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "SemanticSearchService":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    args = [a.arg for a in item.args.args if a.arg != "self"]
                    assert "embedding_service" in args
                    return
    pytest.fail("SemanticSearchService.__init__ not found")


@pytest.mark.parametrize("path", CALLERS, ids=lambda p: os.path.basename(p))
def test_callers_do_not_construct_the_service_directly(path):
    """A bare SemanticSearchService() raises TypeError - the original bug."""
    tree = _parse(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "SemanticSearchService":
                pytest.fail(
                    "%s:%d constructs SemanticSearchService directly; "
                    "use get_semantic_search_service()" % (os.path.basename(path), node.lineno)
                )


@pytest.mark.parametrize("path", CALLERS, ids=lambda p: os.path.basename(p))
def test_semantic_search_is_never_called_on_the_class(path):
    """SemanticSearchService.semantic_search(...) leaves `self` unbound."""
    tree = _parse(path)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "semantic_search"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "SemanticSearchService"
        ):
            pytest.fail(
                "%s:%d calls semantic_search on the CLASS, so `self` is unbound "
                "and `query` is consumed as `self`" % (os.path.basename(path), node.lineno)
            )


def test_factory_is_thread_safe():
    """gthread workers can reach a cold factory concurrently."""
    src = io.open(SERVICE_MODULE, encoding="utf-8").read()
    assert "_service_lock" in src, "factory must guard construction with a lock"
    tree = _parse(SERVICE_MODULE)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "get_semantic_search_service":
            assert any(isinstance(n, ast.With) for n in ast.walk(node)), (
                "expected the lock to be acquired via a `with` block"
            )
            return
    pytest.fail("get_semantic_search_service not found")
