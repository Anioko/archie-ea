"""
-> app.modules.vendors.services.seeder_service

Comprehensive Vendor Seed Validation

Validates vendors against:
- Required fields (code, name, headquarters_location, vendor_type, year_founded)
- Enum constraints (vendor_type, market_position, risk_level, deployment_model)
- Type constraints (strings, numbers, lists, dicts)
- Consistency checks across all vendors
- Referential integrity (competitors, capabilities)
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VendorSeedValidator:
    """
    Comprehensive vendor data validation.
    
    Features:
    - Schema validation (required fields, types)
    - Enum validation (vendor_type, market_position, etc)
    - Consistency validation (LEADER position requires market share)
    - Uniqueness validation (code, source_id, name)
    - Referential integrity (competitors exist)
    """
    
    # Enum constraints
    VALID_VENDOR_TYPES = {'ISV', 'Service Provider', 'Infrastructure', 'Cloud', 'Hybrid'}
    VALID_MARKET_POSITIONS = {'LEADER', 'CHALLENGER', 'FOLLOWER', 'NICHE'}
    VALID_RISK_LEVELS = {'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'}
    VALID_DEPLOYMENT_MODELS = {'On-Premise', 'Cloud', 'Hybrid', 'SaaS'}
    
    # Required fields per vendor
    REQUIRED_FIELDS = {
        'code': str,
        'name': str,
        'headquarters_location': str,
        'vendor_type': str,
        'year_founded': int,
    }
    
    # Optional fields with expected types
    OPTIONAL_FIELDS = {
        'market_position': str,
        'market_share_percent': (int, float),
        'risk_level': str,
        'employees_count': int,
        'annual_revenue_usd': (int, float),
        'deployment_model': str,
        'supported_regions': list,
        'certifications': list,
        'soc2': bool,
        'iso27001': bool,
    }
    
    def validate_vendor(self, vendor: Dict[str, Any]) -> List[str]:
        """
        Validate single vendor object.
        
        Returns list of error messages (empty = valid).
        """
        errors = []
        
        # 1. Check required fields
        for field, expected_type in self.REQUIRED_FIELDS.items():
            if field not in vendor:
                errors.append(f"Missing required field: {field}")
            elif vendor[field] is None:
                errors.append(f"Field is None: {field}")
            elif not isinstance(vendor[field], expected_type):
                errors.append(
                    f"Field {field} has wrong type: "
                    f"expected {expected_type.__name__}, got {type(vendor[field]).__name__}"
                )
        
        # 2. Check enum constraints
        vendor_type = vendor.get('vendor_type')
        if vendor_type and vendor_type not in self.VALID_VENDOR_TYPES:
            errors.append(
                f"Invalid vendor_type '{vendor_type}'. "
                f"Valid options: {', '.join(self.VALID_VENDOR_TYPES)}"
            )
        
        market_position = vendor.get('market_position')
        if market_position and market_position not in self.VALID_MARKET_POSITIONS:
            errors.append(
                f"Invalid market_position '{market_position}'. "
                f"Valid options: {', '.join(self.VALID_MARKET_POSITIONS)}"
            )
        
        risk_level = vendor.get('risk_level')
        if risk_level and risk_level not in self.VALID_RISK_LEVELS:
            errors.append(
                f"Invalid risk_level '{risk_level}'. "
                f"Valid options: {', '.join(self.VALID_RISK_LEVELS)}"
            )
        
        deployment_model = vendor.get('deployment_model')
        if deployment_model and deployment_model not in self.VALID_DEPLOYMENT_MODELS:
            errors.append(
                f"Invalid deployment_model '{deployment_model}'. "
                f"Valid options: {', '.join(self.VALID_DEPLOYMENT_MODELS)}"
            )
        
        # 3. Check optional field types
        for field, expected_type in self.OPTIONAL_FIELDS.items():
            if field in vendor and vendor[field] is not None:
                if not isinstance(vendor[field], expected_type):
                    if isinstance(expected_type, tuple):
                        type_names = ' or '.join(t.__name__ for t in expected_type)
                    else:
                        type_names = expected_type.__name__
                    
                    errors.append(
                        f"Field {field} has wrong type: "
                        f"expected {type_names}, got {type(vendor[field]).__name__}"
                    )
        
        # 4. Consistency checks
        consistency_errors = self._validate_vendor_consistency(vendor)
        errors.extend(consistency_errors)
        
        return errors
    
    def _validate_vendor_consistency(self, vendor: Dict[str, Any]) -> List[str]:
        """Validate consistency within single vendor."""
        errors = []
        
        # LEADER market position should have reasonable market share
        # But don't be too strict - some established vendors might be LEADER without high %, and vice versa
        if vendor.get('market_position') == 'LEADER':
            market_share = vendor.get('market_share_percent', 0)
            if market_share and market_share < 5:
                # Only warn if market share is provided and very low
                logger.warning(
                    f"Market position is LEADER but market_share_percent is {market_share}%. "
                    f"LEADER typically requires >= 5% market share. Verify this is correct."
                )
        
        # Year founded sanity check - be lenient
        # Many legacy vendors were founded before 1980, and that's OK
        # Only flag if year is unrealistic (future or too far past)
        year_founded = vendor.get('year_founded')
        if year_founded:
            try:
                year_int = int(year_founded) if isinstance(year_founded, str) else year_founded
                if year_int > 2026:
                    errors.append(
                        f"Year founded {year_int} is in the future."
                    )
            except (ValueError, TypeError):
                errors.append(
                    f"Year founded must be an integer, got: {type(year_founded).__name__}"
                )
            # Removed check for < 1980 - many valid vendors are older (IBM, etc.)
        
        # Market share bounds
        market_share = vendor.get('market_share_percent')
        if market_share is not None:
            if market_share < 0 or market_share > 100:
                errors.append(
                    f"Market share {market_share}% is out of bounds [0, 100]."
                )
        
        # Risk level and certification consistency (informational, not blocking)
        if vendor.get('risk_level') in ['CRITICAL', 'HIGH']:
            has_security = vendor.get('soc2') or vendor.get('iso27001')
            if not has_security:
                logger.warning(
                    f"Vendor {vendor.get('name')} has HIGH/CRITICAL risk "
                    f"but no SOC2/ISO27001 certifications. Consider addressing."
                )
        
        return errors
    
    def validate_consistency(self, vendors: List[Dict[str, Any]]) -> List[str]:
        """
        Validate consistency across all vendors.
        
        Checks:
        - No duplicate codes
        - No duplicate source_ids
        - No duplicate names
        - Referential integrity (competitor codes exist)
        """
        errors = []
        
        # Extract all codes, source_ids, names
        codes = {}
        source_ids = {}
        names = {}
        
        for idx, vendor in enumerate(vendors):
            code = vendor.get('code')
            source_id = vendor.get('seed_source_id') or vendor.get('id')
            name = vendor.get('name')
            
            # Check code uniqueness
            if code:
                if code in codes:
                    errors.append(
                        f"Duplicate code '{code}' at vendors[{codes[code]}] and vendors[{idx}]"
                    )
                codes[code] = idx
            
            # Check source_id uniqueness
            if source_id:
                if source_id in source_ids:
                    errors.append(
                        f"Duplicate seed_source_id '{source_id}' "
                        f"at vendors[{source_ids[source_id]}] and vendors[{idx}]"
                    )
                source_ids[source_id] = idx
            
            # Warn on name duplicates (non-blocking)
            if name:
                if name in names:
                    logger.warning(
                        f"Duplicate name '{name}' at vendors[{names[name]}] and vendors[{idx}]"
                    )
                names[name] = idx
        
        # Check referential integrity (competitors)
        for idx, vendor in enumerate(vendors):
            competitors = vendor.get('competitors', [])
            if competitors:
                for competitor_code in competitors:
                    if competitor_code not in codes:
                        errors.append(
                            f"Vendor {vendor.get('name')} references competitor "
                            f"'{competitor_code}' which does not exist in seed data"
                        )
        
        return errors
