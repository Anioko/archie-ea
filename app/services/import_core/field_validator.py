"""
Shared Field Validator for Import Systems

Common field validation functionality for import operations.
Used by both unified applications import and batch import systems.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Union

from .date_parser import parse_flexible_date


class ImportFieldValidator:
    """
    Unified field validator for import operations.
    
    Provides consistent validation for different field types:
    - Text fields
    - Numeric fields (integers, decimals)
    - Date fields
    - Boolean fields
    - Email fields
    - URL fields
    """
    
    # Field type definitions
    FIELD_TYPES = {
        'text': str,
        'integer': int,
        'decimal': Decimal,
        'date': datetime,
        'boolean': bool,
        'email': str,
        'url': str,
        'choice': str
    }
    
    @staticmethod
    def validate_field(
        value: Any,
        field_name: str,
        field_type: str,
        required: bool = False,
        choices: Optional[List[str]] = None,
        date_format: str = 'iso',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Validate a single field value.
        
        Args:
            value: Value to validate
            field_name: Name of the field
            field_type: Type of field (text, integer, decimal, date, boolean, email, url, choice)
            required: Whether field is required
            choices: List of valid choices (for choice fields)
            date_format: Date format for date fields (iso, dmy, mdy)
            **kwargs: Additional validation parameters
            
        Returns:
            Validation result with valid flag and processed value
        """
        result = {
            'valid': True,
            'value': value,
            'error': None,
            'warning': None
        }
        
        # Check if value is empty
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                result['valid'] = False
                result['error'] = f"{field_name} is required"
            else:
                result['value'] = None
            return result
        
        # Convert to string for processing
        if not isinstance(value, str):
            value_str = str(value)
        else:
            value_str = value.strip()
        
        # Validate based on field type
        try:
            if field_type == 'text':
                result['value'] = ImportFieldValidator._validate_text(value_str, **kwargs)
            elif field_type == 'integer':
                result['value'] = ImportFieldValidator._validate_integer(value_str, **kwargs)
            elif field_type == 'decimal':
                result['value'] = ImportFieldValidator._validate_decimal(value_str, **kwargs)
            elif field_type == 'date':
                result['value'] = ImportFieldValidator._validate_date(value_str, date_format, **kwargs)
            elif field_type == 'boolean':
                result['value'] = ImportFieldValidator._validate_boolean(value_str, **kwargs)
            elif field_type == 'email':
                result['value'] = ImportFieldValidator._validate_email(value_str, **kwargs)
            elif field_type == 'url':
                result['value'] = ImportFieldValidator._validate_url(value_str, **kwargs)
            elif field_type == 'choice':
                result['value'] = ImportFieldValidator._validate_choice(value_str, choices, **kwargs)
            else:
                result['valid'] = False
                result['error'] = f"Unknown field type: {field_type}"
                
        except ValueError as e:
            result['valid'] = False
            result['error'] = f"Invalid {field_name}: {str(e)}"
        except Exception as e:
            result['valid'] = False
            result['error'] = f"Error validating {field_name}: {str(e)}"
        
        return result
    
    @staticmethod
    def _validate_text(value: str, max_length: Optional[int] = None, **kwargs) -> str:
        """Validate text field."""
        if max_length and len(value) > max_length:
            raise ValueError(f"Text exceeds maximum length of {max_length}")
        return value
    
    @staticmethod
    def _validate_integer(value: str, min_value: Optional[int] = None, max_value: Optional[int] = None, **kwargs) -> int:
        """Validate integer field."""
        try:
            int_value = int(value)
        except ValueError:
            raise ValueError(f"'{value}' is not a valid integer")
        
        if min_value is not None and int_value < min_value:
            raise ValueError(f"Value {int_value} is less than minimum {min_value}")
        
        if max_value is not None and int_value > max_value:
            raise ValueError(f"Value {int_value} is greater than maximum {max_value}")
        
        return int_value
    
    @staticmethod
    def _validate_decimal(value: str, min_value: Optional[float] = None, max_value: Optional[float] = None, **kwargs) -> Decimal:
        """Validate decimal field."""
        # Handle European format (1.234,56) by replacing comma with dot if appropriate
        if ',' in value and '.' not in value:
            # Likely European format
            value = value.replace(',', '.')
        elif ',' in value and '.' in value:
            # Mixed format - assume last separator is decimal
            if value.rfind(',') > value.rfind('.'):
                value = value.replace('.', '').replace(',', '.')
        
        try:
            decimal_value = Decimal(value)
        except (InvalidOperation, ValueError):
            raise ValueError(f"'{value}' is not a valid decimal number")
        
        if min_value is not None and decimal_value < Decimal(str(min_value)):
            raise ValueError(f"Value {decimal_value} is less than minimum {min_value}")
        
        if max_value is not None and decimal_value > Decimal(str(max_value)):
            raise ValueError(f"Value {decimal_value} is greater than maximum {max_value}")
        
        return decimal_value
    
    @staticmethod
    def _validate_date(value: str, date_format: str = 'iso', **kwargs) -> Optional[datetime]:
        """Validate date field."""
        parsed_date = parse_flexible_date(value, date_format)
        if parsed_date is None:
            raise ValueError(f"'{value}' is not a valid date")
        return parsed_date
    
    @staticmethod
    def _validate_boolean(value: str, **kwargs) -> bool:
        """Validate boolean field."""
        true_values = ['true', '1', 'yes', 'on', 'enabled', 'active']
        false_values = ['false', '0', 'no', 'off', 'disabled', 'inactive']
        
        value_lower = value.lower()
        
        if value_lower in true_values:
            return True
        elif value_lower in false_values:
            return False
        else:
            raise ValueError(f"'{value}' is not a valid boolean (use: true/false, yes/no, 1/0)")
    
    @staticmethod
    def _validate_email(value: str, **kwargs) -> str:
        """Validate email field."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_pattern, value):
            raise ValueError(f"'{value}' is not a valid email address")
        
        return value.lower()
    
    @staticmethod
    def _validate_url(value: str, **kwargs) -> str:
        """Validate URL field."""
        url_pattern = r'^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$'
        
        if not re.match(url_pattern, value, re.IGNORECASE):
            raise ValueError(f"'{value}' is not a valid URL (must start with http:// or https://)")
        
        return value
    
    @staticmethod
    def _validate_choice(value: str, choices: Optional[List[str]], **kwargs) -> str:
        """Validate choice field."""
        if not choices:
            raise ValueError("No choices provided for choice field")
        
        value_lower = value.lower()
        valid_choices_lower = [choice.lower() for choice in choices]
        
        if value_lower not in valid_choices_lower:
            raise ValueError(f"'{value}' is not a valid choice. Valid choices: {', '.join(choices)}")
        
        # Return the original case from choices
        for choice in choices:
            if choice.lower() == value_lower:
                return choice
        
        return value  # Fallback
    
    @staticmethod
    def validate_row(
        row_data: Dict[str, Any],
        field_definitions: Dict[str, Dict[str, Any]],
        date_format: str = 'iso'
    ) -> Dict[str, Any]:
        """
        Validate an entire row of data.
        
        Args:
            row_data: Row data dictionary
            field_definitions: Field validation definitions
            date_format: Date format for date fields
            
        Returns:
            Validation result with processed data and errors
        """
        result = {
            'valid': True,
            'processed_data': {},
            'errors': {},
            'warnings': {}
        }
        
        for field_name, field_def in field_definitions.items():
            field_value = row_data.get(field_name)
            field_type = field_def.get('type', 'text')
            required = field_def.get('required', False)
            choices = field_def.get('choices')
            
            # Validate field
            validation_result = ImportFieldValidator.validate_field(
                field_value,
                field_name,
                field_type,
                required=required,
                choices=choices,
                date_format=date_format,
                **field_def
            )
            
            if validation_result['valid']:
                result['processed_data'][field_name] = validation_result['value']
                if validation_result['warning']:
                    result['warnings'][field_name] = validation_result['warning']
            else:
                result['valid'] = False
                result['errors'][field_name] = validation_result['error']
        
        return result
    
    @staticmethod
    def get_common_field_definitions() -> Dict[str, Dict[str, Any]]:
        """
        Get common field definitions for application imports.
        
        Returns:
            Dictionary of field definitions
        """
        return {
            # Text fields
            'name': {'type': 'text', 'required': True, 'max_length': 255},
            'description': {'type': 'text', 'required': False, 'max_length': 2000},
            'vendor': {'type': 'text', 'required': False, 'max_length': 255},
            'business_owner': {'type': 'text', 'required': False, 'max_length': 255},
            'technical_owner': {'type': 'text', 'required': False, 'max_length': 255},
            'support_team': {'type': 'text', 'required': False, 'max_length': 255},
            'application_code': {'type': 'text', 'required': False, 'max_length': 100},
            
            # Choice fields
            'lifecycle_status': {
                'type': 'choice',
                'required': False,
                'choices': ['Active', 'Inactive', 'Retired', 'Decommissioned', 'Planned']
            },
            'criticality': {
                'type': 'choice',
                'required': False,
                'choices': ['High', 'Medium', 'Low', 'Critical']
            },
            'business_domain': {
                'type': 'choice',
                'required': False,
                'choices': ['Finance', 'HR', 'Operations', 'IT', 'Sales', 'Marketing', 'Legal', 'Other']
            },
            
            # Numeric fields
            'user_base_size': {'type': 'integer', 'required': False, 'min_value': 0},
            'concurrent_users_max': {'type': 'integer', 'required': False, 'min_value': 0},
            'total_cost_of_ownership': {'type': 'decimal', 'required': False, 'min_value': 0},
            'license_cost': {'type': 'decimal', 'required': False, 'min_value': 0},
            'maintenance_cost': {'type': 'decimal', 'required': False, 'min_value': 0},
            'interfaces_count': {'type': 'integer', 'required': False, 'min_value': 0},
            'availability_target': {'type': 'decimal', 'required': False, 'min_value': 0, 'max_value': 100},
            
            # Date fields
            'go_live_date': {'type': 'date', 'required': False},
            'planned_retirement_date': {'type': 'date', 'required': False},
            'end_of_life_date': {'type': 'date', 'required': False},
            'last_security_audit_date': {'type': 'date', 'required': False},
            'last_penetration_test_date': {'type': 'date', 'required': False},
            
            # Boolean fields
            'disaster_recovery_enabled': {'type': 'boolean', 'required': False},
            'gdpr_compliant': {'type': 'boolean', 'required': False},
            'encryption_in_transit': {'type': 'boolean', 'required': False},
            
            # Email fields
            'business_owner_email': {'type': 'email', 'required': False},
            'technical_owner_email': {'type': 'email', 'required': False},
            
            # URL fields
            'api_documentation': {'type': 'url', 'required': False},
            'main_url': {'type': 'url', 'required': False},
        }


# Convenience functions for common operations
def validate_import_field(value: Any, field_name: str, field_type: str, **kwargs) -> Dict[str, Any]:
    """Convenience function to validate a single field."""
    return ImportFieldValidator.validate_field(value, field_name, field_type, **kwargs)


def validate_import_row(row_data: Dict[str, Any], field_definitions: Dict[str, Dict[str, Any]], date_format: str = 'iso') -> Dict[str, Any]:
    """Convenience function to validate a row of data."""
    return ImportFieldValidator.validate_row(row_data, field_definitions, date_format)
