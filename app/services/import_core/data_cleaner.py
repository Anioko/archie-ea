"""
Shared Data Cleaner for Import Systems

Common data cleaning functionality for import operations.
Used by both unified applications import and batch import systems.
"""

import re
from typing import Any, Dict, List, Optional

from .field_validator import ImportFieldValidator


class ImportDataCleaner:
    """
    Unified data cleaner for import operations.
    
    Provides consistent data cleaning across all import systems:
    - String cleaning and normalization
    - Vendor name standardization
    - Numeric value cleaning
    - Boolean value normalization
    - Date format standardization
    """
    
    # Common vendor name variations
    VENDOR_MAPPINGS = {
        # Microsoft variations
        'microsoft': 'Microsoft',
        'ms': 'Microsoft',
        'msft': 'Microsoft',
        
        # Oracle variations
        'oracle': 'Oracle',
        'oracle corp': 'Oracle',
        'oracle corporation': 'Oracle',
        
        # SAP variations
        'sap': 'SAP',
        'sap se': 'SAP',
        'sap ag': 'SAP',
        
        # IBM variations
        'ibm': 'IBM',
        'international business machines': 'IBM',
        
        # Amazon variations
        'amazon': 'Amazon',
        'amazon web services': 'AWS',
        'aws': 'AWS',
        
        # Google variations
        'google': 'Google',
        'alphabet': 'Google',
        'alphabet inc': 'Google',
        
        # Salesforce variations
        'salesforce': 'Salesforce',
        'salesforce.com': 'Salesforce',
        'sfdc': 'Salesforce',
    }
    
    @staticmethod
    def clean_string(value: Any) -> Optional[str]:
        """
        Clean and normalize string values.
        
        Args:
            value: Value to clean
            
        Returns:
            Cleaned string or None if empty/invalid
        """
        if value is None:
            return None
        
        if not isinstance(value, str):
            value = str(value)
        
        # Remove leading/trailing whitespace
        cleaned = value.strip()
        
        # Remove extra internal whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Return None if empty after cleaning
        if not cleaned:
            return None
        
        return cleaned
    
    @staticmethod
    def clean_vendor_name(vendor_name: Any) -> Optional[str]:
        """
        Clean and standardize vendor names.
        
        Args:
            vendor_name: Vendor name to clean
            
        Returns:
            Standardized vendor name or None if empty
        """
        if vendor_name is None:
            return None
        
        # Clean string first
        cleaned = ImportDataCleaner.clean_string(vendor_name)
        if not cleaned:
            return None
        
        # Convert to lowercase for matching
        cleaned_lower = cleaned.lower()
        
        # Check vendor mappings
        for variant, standard in ImportDataCleaner.VENDOR_MAPPINGS.items():
            if variant in cleaned_lower:
                return standard
        
        # Capitalize properly (title case with exceptions)
        words = cleaned.split()
        capitalized_words = []
        
        for word in words:
            # Keep common abbreviations uppercase
            if word.upper() in ['IBM', 'AWS', 'SAP', 'MSFT', 'HR', 'IT', 'CEO', 'CFO', 'CTO']:
                capitalized_words.append(word.upper())
            # Keep common patterns
            elif re.match(r'^[A-Z]+$', word):  # All caps
                capitalized_words.append(word)
            else:
                capitalized_words.append(word.capitalize())
        
        return ' '.join(capitalized_words)
    
    @staticmethod
    def clean_numeric_value(value: Any, field_type: str = 'decimal') -> Optional[Any]:
        """
        Clean numeric values.
        
        Args:
            value: Value to clean
            field_type: Type of field ('integer' or 'decimal')
            
        Returns:
            Cleaned numeric value or None if invalid
        """
        if value is None:
            return None
        
        if isinstance(value, str):
            # Remove whitespace
            cleaned = value.strip()
            
            # Handle European format (1.234,56 -> 1234.56)
            if ',' in cleaned and '.' not in cleaned:
                # Likely European decimal format
                cleaned = cleaned.replace(',', '.')
            elif ',' in cleaned and '.' in cleaned:
                # Mixed format - determine which is decimal separator
                if cleaned.rfind(',') > cleaned.rfind('.'):
                    # Comma is decimal separator
                    cleaned = cleaned.replace('.', '').replace(',', '.')
            
            # Remove currency symbols and other non-numeric characters
            cleaned = re.sub(r'[^\d\.\-+]', '', cleaned)
            
            if not cleaned:
                return None
            
            try:
                if field_type == 'integer':
                    return int(float(cleaned))  # Convert via float to handle decimals
                elif field_type == 'decimal':
                    from decimal import Decimal
                    return Decimal(cleaned)
            except (ValueError, TypeError):
                return None
        
        elif isinstance(value, (int, float)):
            return value
        
        return None
    
    @staticmethod
    def clean_boolean_value(value: Any) -> Optional[bool]:
        """
        Clean and normalize boolean values.
        
        Args:
            value: Value to clean
            
        Returns:
            Normalized boolean or None if invalid
        """
        if value is None:
            return None
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            cleaned = value.strip().lower()
            
            # True values
            if cleaned in ['true', '1', 'yes', 'on', 'enabled', 'active', 'y']:
                return True
            # False values
            elif cleaned in ['false', '0', 'no', 'off', 'disabled', 'inactive', 'n']:
                return False
            # Numeric values
            elif cleaned.isdigit():
                return bool(int(cleaned))
        
        elif isinstance(value, (int, float)):
            return bool(value)
        
        return None
    
    @staticmethod
    def clean_email(email: Any) -> Optional[str]:
        """
        Clean and validate email addresses.
        
        Args:
            email: Email address to clean
            
        Returns:
            Cleaned email or None if invalid
        """
        if email is None:
            return None
        
        # Clean string
        cleaned = ImportDataCleaner.clean_string(email)
        if not cleaned:
            return None
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, cleaned):
            return None
        
        return cleaned.lower()
    
    @staticmethod
    def clean_url(url: Any) -> Optional[str]:
        """
        Clean and validate URLs.
        
        Args:
            url: URL to clean
            
        Returns:
            Cleaned URL or None if invalid
        """
        if url is None:
            return None
        
        # Clean string
        cleaned = ImportDataCleaner.clean_string(url)
        if not cleaned:
            return None
        
        # Add protocol if missing
        if not cleaned.startswith(('http://', 'https://')):
            cleaned = 'https://' + cleaned
        
        # Basic URL validation
        url_pattern = r'^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$'
        if not re.match(url_pattern, cleaned, re.IGNORECASE):
            return None
        
        return cleaned
    
    @staticmethod
    def clean_choice_value(value: Any, choices: List[str]) -> Optional[str]:
        """
        Clean and validate choice field values.
        
        Args:
            value: Value to clean
            choices: List of valid choices
            
        Returns:
            Cleaned choice or None if invalid
        """
        if value is None:
            return None
        
        # Clean string
        cleaned = ImportDataCleaner.clean_string(value)
        if not cleaned:
            return None
        
        # Case-insensitive matching
        cleaned_lower = cleaned.lower()
        valid_choices_lower = [choice.lower() for choice in choices]
        
        if cleaned_lower in valid_choices_lower:
            # Return the original case from choices
            for choice in choices:
                if choice.lower() == cleaned_lower:
                    return choice
        
        return None
    
    @staticmethod
    def clean_row_data(
        row_data: Dict[str, Any],
        field_definitions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Clean an entire row of data based on field definitions.
        
        Args:
            row_data: Row data dictionary
            field_definitions: Field definitions with cleaning rules
            
        Returns:
            Cleaned row data
        """
        cleaned_data = {}
        
        for field_name, field_def in field_definitions.items():
            field_value = row_data.get(field_name)
            field_type = field_def.get('type', 'text')
            choices = field_def.get('choices')
            
            # Clean based on field type
            if field_type == 'text':
                cleaned_value = ImportDataCleaner.clean_string(field_value)
            elif field_type == 'vendor':
                cleaned_value = ImportDataCleaner.clean_vendor_name(field_value)
            elif field_type in ['integer', 'decimal']:
                cleaned_value = ImportDataCleaner.clean_numeric_value(field_value, field_type)
            elif field_type == 'boolean':
                cleaned_value = ImportDataCleaner.clean_boolean_value(field_value)
            elif field_type == 'email':
                cleaned_value = ImportDataCleaner.clean_email(field_value)
            elif field_type == 'url':
                cleaned_value = ImportDataCleaner.clean_url(field_value)
            elif field_type == 'choice' and choices:
                cleaned_value = ImportDataCleaner.clean_choice_value(field_value, choices)
            else:
                cleaned_value = ImportDataCleaner.clean_string(field_value)
            
            # Only include non-empty values unless field is required
            if cleaned_value is not None or field_def.get('required', False):
                cleaned_data[field_name] = cleaned_value
        
        return cleaned_data
    
    @staticmethod
    def detect_and_clean_field(value: Any, field_name: str) -> Any:
        """
        Automatically detect field type and clean value.
        
        Args:
            value: Value to clean
            field_name: Name of the field (used for type detection)
            
        Returns:
            Cleaned value
        """
        if value is None:
            return None
        
        # Detect field type based on field name
        field_name_lower = field_name.lower()
        
        # Email fields
        if any(keyword in field_name_lower for keyword in ['email', 'mail']):
            return ImportDataCleaner.clean_email(value)
        
        # URL fields
        elif any(keyword in field_name_lower for keyword in ['url', 'link', 'website', 'site']):
            return ImportDataCleaner.clean_url(value)
        
        # Vendor fields
        elif 'vendor' in field_name_lower:
            return ImportDataCleaner.clean_vendor_name(value)
        
        # Boolean fields
        elif any(keyword in field_name_lower for keyword in ['enabled', 'active', 'compliant', 'required']):
            return ImportDataCleaner.clean_boolean_value(value)
        
        # Numeric fields
        elif any(keyword in field_name_lower for keyword in ['cost', 'price', 'count', 'size', 'number']):
            return ImportDataCleaner.clean_numeric_value(value)
        
        # Default to string cleaning
        return ImportDataCleaner.clean_string(value)


# Convenience functions for common operations
def clean_import_string(value: Any) -> Optional[str]:
    """Convenience function to clean import string."""
    return ImportDataCleaner.clean_string(value)


def clean_import_vendor(vendor_name: Any) -> Optional[str]:
    """Convenience function to clean import vendor name."""
    return ImportDataCleaner.clean_vendor_name(vendor_name)


def clean_import_row(row_data: Dict[str, Any], field_definitions: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Convenience function to clean import row data."""
    return ImportDataCleaner.clean_row_data(row_data, field_definitions)
