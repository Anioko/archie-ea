"""
Backward-compatibility shim.  # mass-deletion-ok

All models previously defined here now live in the canonical module:
  app/models/solution_models.py

This file only re-exports from that module so existing imports continue
to work without changes.
"""
from .solution_models import (  # noqa: F401
    Solution,
    SolutionPattern,
    SolutionContract,
    SolutionCapabilityMapping,
    SolutionArchiMateElement,
    SolutionFitGapEntry,
    solution_applications,
    solution_vendor_products,
    solution_value_streams,
    solution_work_packages,
    solution_deliverables,
    solution_pattern_applications,
    solution_contracts,
    contract_vendor_products,
)

__all__ = [
    "Solution",
    "SolutionPattern",
    "SolutionContract",
    "SolutionCapabilityMapping",
    "SolutionArchiMateElement",
    "SolutionFitGapEntry",
    "solution_applications",
    "solution_vendor_products",
    "solution_value_streams",
    "solution_work_packages",
    "solution_deliverables",
    "solution_pattern_applications",
    "solution_contracts",
    "contract_vendor_products",
]
