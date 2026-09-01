"""`migrate_genome` must never silently version-stamp an un-migratable genome.

The original implementation stamped `genome_version = GENOME_VERSION` even when
no migration path matched, relabelling a structurally-old IR as current — silent
corruption the emitters then consumed. The fix raises `GenomeMigrationError`
instead. These tests pin both the safe cases (current / absent version pass
through) and the corruption guard (old version with no path raises).
"""
from __future__ import annotations

import pytest

from app.modules.codegen.services import aabl_compiler
from app.modules.codegen.services.aabl_compiler import (
    GENOME_VERSION,
    GenomeMigrationError,
    migrate_genome,
)


def test_current_version_passes_through_unchanged():
    g = {"genome_version": GENOME_VERSION, "modules": {}}
    assert migrate_genome(g) is g


def test_absent_version_treated_as_baseline():
    """A pre-versioning genome IS the baseline — not corruption, no raise."""
    g = {"modules": {}}
    assert migrate_genome(g) == {"modules": {}}


def test_old_version_with_no_migration_path_raises():
    """The core bug: an old version with no migrator must RAISE, not be stamped."""
    g = {"genome_version": "0.5.0", "modules": {"x": {}}}
    with pytest.raises(GenomeMigrationError):
        migrate_genome(g)
    # And it must NOT have mutated the version forward.
    assert g["genome_version"] == "0.5.0"


def test_registered_migration_path_is_applied(monkeypatch):
    """When a migrator exists and advances the version, it is used."""
    def _bump(genome: dict) -> dict:
        genome = dict(genome)
        genome["genome_version"] = GENOME_VERSION
        genome["_migrated"] = True
        return genome

    monkeypatch.setattr(aabl_compiler, "_GENOME_MIGRATIONS", {"0.9.0": _bump})
    out = migrate_genome({"genome_version": "0.9.0", "modules": {}})
    assert out["genome_version"] == GENOME_VERSION
    assert out["_migrated"] is True


def test_migrator_that_does_not_advance_version_raises(monkeypatch):
    """A broken migrator that fails to advance the version must not loop/corrupt."""
    def _noop(genome: dict) -> dict:
        return genome  # forgot to bump genome_version

    monkeypatch.setattr(aabl_compiler, "_GENOME_MIGRATIONS", {"0.9.0": _noop})
    with pytest.raises(GenomeMigrationError):
        migrate_genome({"genome_version": "0.9.0", "modules": {}})


def test_non_dict_input_is_returned_untouched():
    assert migrate_genome(None) is None
    assert migrate_genome("not a genome") == "not a genome"
