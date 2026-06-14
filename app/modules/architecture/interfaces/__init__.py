"""
Architecture service interfaces for dependency injection.

This module defines interfaces to break circular dependencies between
architecture services and other modules.
"""

from .archimate_service_interface import IArchimateService
from .business_layer_service_interface import IBusinessLayerService

__all__ = ['IArchimateService', 'IBusinessLayerService']