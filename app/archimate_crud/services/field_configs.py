"""
ArchiMate Element Field Configurations

This module defines the field schemas for all ArchiMate element types.
It provides a data-driven approach to form generation, replacing template conditionals.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class FieldOption:
    """Represents a select field option."""
    value: str
    label: str


@dataclass
class ElementField:
    """Represents a single form field configuration."""
    name: str
    label: str
    field_type: str  # 'text', 'select', 'textarea'
    required: bool = False
    placeholder: str = ""
    options: List[FieldOption] = field(default_factory=list)
    grid_column: int = 1  # 1 or 2 for grid layout


@dataclass
class ElementTypeConfig:
    """Complete configuration for an ArchiMate element type."""
    element_type: str
    layer: str
    display_name: str
    description: str
    fields: List[ElementField]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for template rendering."""
        return {
            'element_type': self.element_type,
            'layer': self.layer,
            'display_name': self.display_name,
            'description': self.description,
            'fields': [
                {
                    'name': f.name,
                    'label': f.label,
                    'type': f.field_type,
                    'required': f.required,
                    'placeholder': f.placeholder,
                    'options': [{'value': opt.value, 'label': opt.label} for opt in f.options],
                    'grid_column': f.grid_column
                }
                for f in self.fields
            ]
        }


# Field option sets for reuse
DRIVER_TYPES = [
    FieldOption('regulatory', 'Regulatory'),
    FieldOption('competitive', 'Competitive'),
    FieldOption('customer', 'Customer'),
    FieldOption('technology', 'Technology'),
    FieldOption('financial', 'Financial'),
    FieldOption('operational', 'Operational'),
]

DRIVER_SOURCES = [
    FieldOption('external', 'External'),
    FieldOption('internal', 'Internal'),
]

GOAL_TYPES = [
    FieldOption('strategic', 'Strategic'),
    FieldOption('operational', 'Operational'),
    FieldOption('tactical', 'Tactical'),
]

GOAL_CATEGORIES = [
    FieldOption('growth', 'Growth'),
    FieldOption('efficiency', 'Efficiency'),
    FieldOption('innovation', 'Innovation'),
    FieldOption('compliance', 'Compliance'),
    FieldOption('quality', 'Quality'),
]

ACTOR_TYPES = [
    FieldOption('Department', 'Department'),
    FieldOption('Team', 'Team'),
    FieldOption('Business Unit', 'Business Unit'),
    FieldOption('External Partner', 'External Partner'),
    FieldOption('Individual', 'Individual'),
]

STAKEHOLDER_TYPES = [
    FieldOption('internal', 'Internal'),
    FieldOption('external', 'External'),
    FieldOption('executive', 'Executive'),
    FieldOption('operational', 'Operational'),
    FieldOption('regulatory', 'Regulatory'),
]

# Element type configurations
ELEMENT_TYPE_CONFIGS: Dict[str, ElementTypeConfig] = {
    'Driver': ElementTypeConfig(
        element_type='Driver',
        layer='motivation',
        display_name='Driver',
        description='An external or internal condition that motivates the organization to define goals',
        fields=[
            ElementField(
                name='driver_type',
                label='Driver Type',
                field_type='select',
                options=DRIVER_TYPES,
                grid_column=1
            ),
            ElementField(
                name='source',
                label='Source',
                field_type='select',
                options=DRIVER_SOURCES,
                grid_column=2
            ),
        ]
    ),
    
    'Goal': ElementTypeConfig(
        element_type='Goal',
        layer='motivation',
        display_name='Goal',
        description='A high-level statement of intent or direction',
        fields=[
            ElementField(
                name='goal_type',
                label='Goal Type',
                field_type='select',
                options=GOAL_TYPES,
                grid_column=1
            ),
            ElementField(
                name='category',
                label='Category',
                field_type='select',
                options=GOAL_CATEGORIES,
                grid_column=2
            ),
        ]
    ),
    
    'BusinessActor': ElementTypeConfig(
        element_type='BusinessActor',
        layer='business',
        display_name='Business Actor',
        description='An organizational entity that performs behavior',
        fields=[
            ElementField(
                name='actor_type',
                label='Actor Type',
                field_type='select',
                options=ACTOR_TYPES,
                grid_column=1
            ),
            ElementField(
                name='location',
                label='Location',
                field_type='text',
                placeholder='e.g., Headquarters, Remote',
                grid_column=2
            ),
        ]
    ),
    
    'Stakeholder': ElementTypeConfig(
        element_type='Stakeholder',
        layer='motivation',
        display_name='Stakeholder',
        description='An individual, team, or organization with interest in the architecture',
        fields=[
            ElementField(
                name='stakeholder_type',
                label='Stakeholder Type',
                field_type='select',
                options=STAKEHOLDER_TYPES,
                grid_column=1
            ),
            ElementField(
                name='role',
                label='Role',
                field_type='text',
                placeholder='e.g., CFO, Customer',
                grid_column=2
            ),
        ]
    ),
}


def get_element_config(element_type: str) -> Optional[ElementTypeConfig]:
    """
    Get configuration for a specific element type.
    
    Args:
        element_type: The element type name (e.g., 'Driver', 'Goal')
        
    Returns:
        ElementTypeConfig if found, None otherwise
    """
    return ELEMENT_TYPE_CONFIGS.get(element_type)


def get_all_element_types() -> List[str]:
    """Get list of all supported element types."""
    return list(ELEMENT_TYPE_CONFIGS.keys())


def get_element_field_names(element_type: str) -> List[str]:
    """
    Get list of dynamic field names for an element type.
    Used for form initialization and API handling.
    """
    config = get_element_config(element_type)
    if not config:
        return []
    return [f.name for f in config.fields]


def create_empty_form_data(element_type: str) -> Dict[str, str]:
    """
    Create empty form data structure with all fields initialized.
    Used for Alpine.js form initialization.
    """
    config = get_element_config(element_type)
    if not config:
        return {}
    
    data = {'name': '', 'description': ''}
    for field in config.fields:
        data[field.name] = ''
    return data
