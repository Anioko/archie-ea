"""The documented scale-benchmark command must be able to import Archie."""

from pathlib import Path


def test_benchmark_launcher_adds_repository_root_before_importing_app():
    source = Path("scripts/benchmark_scale.py").read_text(encoding="utf-8")

    path_setup = "sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))"
    assert path_setup in source
    assert source.index(path_setup) < source.index("from app import create_app, db")
