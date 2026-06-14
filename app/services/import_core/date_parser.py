"""
Shared Date Parser for Import Systems

Flexible date parsing functionality for import operations.
Used by both unified applications import and batch import systems.
"""

import logging
from datetime import datetime
from typing import Optional

_date_logger = logging.getLogger(__name__)


def parse_flexible_date(value: str, date_order: str = 'iso') -> Optional[datetime]:
    """
    Parse date string with flexible format support.
    
    Args:
        value: Date string to parse
        date_order: Date format order ('iso', 'dmy', 'mdy')
        
    Returns:
        Parsed datetime or None if parsing fails
    """
    if not value or not isinstance(value, str):
        return None
    
    value_str = str(value).strip()
    
    # Year-only values are too ambiguous — could be version, ID, or count.
    # Skip silently instead of converting "2009" to 2009-01-01.
    if value_str.isdigit() and len(value_str) == 4:
        _date_logger.debug("Skipping year-only value '%s' (too ambiguous)", value_str)
        return None
    
    # Build format list with locale-preferred order
    formats = []
    
    if date_order == 'iso':
        # ISO 8601 format preferred (unambiguous)
        formats.extend([
            '%Y-%m-%d',  # 2024-01-15
            '%Y/%m/%d',  # 2024/01/15
            '%Y.%m.%d',  # 2024.01.15
        ])
    elif date_order == 'dmy':
        # Day-Month-Year format (European)
        formats.extend([
            '%d-%m-%Y',  # 15-01-2024
            '%d/%m/%Y',  # 15/01/2024
            '%d.%m.%Y',  # 15.01.2024
        ])
    elif date_order == 'mdy':
        # Month-Day-Year format (US)
        formats.extend([
            '%m-%d-%Y',  # 01-15-2024
            '%m/%d/%Y',  # 01/15/2024
            '%m.%d.%Y',  # 01.15.2024
        ])
    
    # Add common formats as fallback
    formats.extend([
        '%d %b %Y',    # 15 Jan 2024
        '%d %B %Y',    # 15 January 2024
        '%b %d %Y',    # Jan 15 2024
        '%B %d %Y',    # January 15 2024
        '%Y-%m-%d %H:%M:%S',  # 2024-01-15 14:30:00
        '%Y-%m-%d %H:%M',     # 2024-01-15 14:30
        '%Y-%m-%d %H',         # 2024-01-15 14
    ])
    
    # Try each format
    for fmt in formats:
        try:
            parsed = datetime.strptime(value_str, fmt)
            
            # Warn when date is ambiguous (day and month both <= 12)
            if fmt in ('%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%m-%d-%Y'):
                if parsed.day <= 12 and parsed.month <= 12 and parsed.day != parsed.month:
                    _date_logger.warning(
                        "Ambiguous date '%s' parsed as %s using format '%s' "
                        "(date_order=%s). Consider ISO 8601 (YYYY-MM-DD).",
                        value_str, parsed.strftime("%Y-%m-%d"), fmt, date_order,
                    )
            
            return parsed
            
        except ValueError:
            continue
    
    # If all formats fail, log and return None
    _date_logger.debug("Could not parse date '%s' with any format", value_str)
    return None


def normalize_date_format(date_str: str) -> str:
    """
    Normalize date string to ISO format if possible.
    
    Args:
        date_str: Date string to normalize
        
    Returns:
        Normalized date string or original if parsing fails
    """
    parsed = parse_flexible_date(date_str)
    if parsed:
        return parsed.strftime('%Y-%m-%d')
    return date_str


def is_valid_date(date_str: str, date_order: str = 'iso') -> bool:
    """
    Check if a date string is valid.
    
    Args:
        date_str: Date string to check
        date_order: Date format order
        
    Returns:
        True if valid, False otherwise
    """
    return parse_flexible_date(date_str, date_order) is not None


def get_date_format_preference() -> str:
    """
    Get user's date format preference.
    
    Returns:
        Date format preference ('iso', 'dmy', 'mdy')
    """
    # This could be extended to read from user preferences
    # For now, default to ISO format
    return 'iso'


# Convenience functions for common operations
def parse_import_date(value: str, date_order: str = 'iso') -> Optional[datetime]:
    """Convenience function to parse import date."""
    return parse_flexible_date(value, date_order)


def is_import_date_valid(date_str: str, date_order: str = 'iso') -> bool:
    """Convenience function to check if import date is valid."""
    return is_valid_date(date_str, date_order)
