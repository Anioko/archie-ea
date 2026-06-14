"""Sidebar menu validation and health checking."""

import logging
from typing import Dict, List, Tuple
from flask import current_app
from app.extensions import db
from app.models.sidebar_menu import SidebarMenuItem

logger = logging.getLogger(__name__)


class SidebarMenuValidator:
    """Validates sidebar menu items for consistency and completeness."""
    
    @staticmethod
    def validate_route_exists(route_name: str) -> bool:
        """Check if Flask route/endpoint exists."""
        try:
            if not route_name:
                return True  # null route is OK for parent items
            
            # Get all registered endpoints
            endpoints = current_app.url_map._rules_by_endpoint.keys()
            return route_name in endpoints
        except Exception as e:
            logger.error(f"Error validating route {route_name}: {e}")
            return False
    
    @staticmethod
    def validate_icon_exists(icon_name: str) -> bool:
        """Check if lucide icon exists (basic validation, non-strict)."""
        if not icon_name:
            return True
        
        # Just check it's a reasonable string (alphanumeric, dash, underscore)
        # Don't enforce strict list - UX team knows what icons are available
        # Log warning if icon looks suspicious
        import re
        if not re.match(r'^[a-z0-9\-_]+$', icon_name):
            logger.warning(f"Icon name looks suspicious: {icon_name} (contains invalid chars)")
            return False
        
        return True
    
    @staticmethod
    def validate_all_items() -> Tuple[bool, List[str]]:
        """
        Validate all sidebar items in database.
        
        Returns: (is_valid, error_messages)
        """
        errors = []
        items = SidebarMenuItem.query.all()
        
        for item in items:
            # Validate route exists
            if item.route and not SidebarMenuValidator.validate_route_exists(item.route):
                errors.append(f"Route not found: {item.key} → {item.route}")
            
            # Validate icon exists
            if item.icon and not SidebarMenuValidator.validate_icon_exists(item.icon):
                errors.append(f"Icon not found: {item.key} → {item.icon}")
            
            # Validate required fields
            if not item.key:
                errors.append(f"Missing key for menu item ID {item.id}")
            
            if not item.label:
                errors.append(f"Missing label for key {item.key}")
            
            if not item.section:
                errors.append(f"Missing section for key {item.key}")
            
            # Validate level consistency
            if item.subsection and item.level != 2:
                errors.append(f"Item with subsection should be level 2: {item.key}")
            
            if not item.subsection and item.level == 2:
                errors.append(f"Item with level 2 should have subsection: {item.key}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def get_health_report() -> Dict:
        """Get full health report of sidebar menu system."""
        items = SidebarMenuItem.query.all()
        
        is_valid, errors = SidebarMenuValidator.validate_all_items()
        
        report = {
            'is_healthy': is_valid,
            'total_items': len(items),
            'enabled': sum(1 for i in items if i.is_enabled),
            'disabled': sum(1 for i in items if not i.is_enabled),
            'items_with_roles': sum(1 for i in items if i.required_roles),
            'errors': errors,
            'error_count': len(errors),
        }
        
        if errors:
            logger.warning(f"Sidebar menu health check failed: {len(errors)} error(s)")
            for error in errors:
                logger.warning(f"  - {error}")
        
        return report
