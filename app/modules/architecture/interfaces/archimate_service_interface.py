"""
Interface for Archimate services to enable dependency injection and break circular dependencies.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class IArchimateService(ABC):
    """Interface for Archimate-related services."""
    
    @abstractmethod
    def get_archimate_elements(self, model_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get Archimate elements by model type."""
        pass
    
    @abstractmethod
    def get_element_relationships(self, element_id: str) -> List[Dict[str, Any]]:
        """Get relationships for a specific Archimate element."""
        pass
    
    @abstractmethod
    def analyze_capability_gaps(self, capability_id: str) -> Dict[str, Any]:
        """Analyze capability gaps for a specific capability."""
        pass
    
    @abstractmethod
    def create_archimate_view(self, view_data: Dict[str, Any]) -> str:
        """Create a new Archimate view."""
        pass
    
    @abstractmethod
    def validate_archimate_model(self, model_data: Dict[str, Any]) -> bool:
        """Validate an Archimate model."""
        pass