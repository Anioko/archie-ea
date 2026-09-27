"""Genome-patch flow: schema, validator, proposer, applier.

The AI copilot proposes a schema-validated, provenance-bearing patch to the
enterprise genome; the patch is queued through the existing AI approval gate;
only an approved patch is applied to the model by deterministic code. See each
module's docstring, and ADR 0009 / ADR 0010.
"""

from app.modules.genome.patch.applier import (
    apply_genome_patch,
    verify_element_synced,
)
from app.modules.genome.patch.proposer import (
    APPLY_ENTITY_TYPE,
    propose_genome_patch,
)
from app.modules.genome.patch.schema import GENOME_PATCH_SCHEMA
from app.modules.genome.patch.validator import (
    GenomePatchValidationError,
    validate_genome_patch,
    validate_genome_patch_strict,
)

__all__ = [
    "GENOME_PATCH_SCHEMA",
    "validate_genome_patch",
    "validate_genome_patch_strict",
    "GenomePatchValidationError",
    "propose_genome_patch",
    "apply_genome_patch",
    "verify_element_synced",
    "APPLY_ENTITY_TYPE",
]
