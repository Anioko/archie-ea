"""
DEPRECATED: Import from app.modules.capabilities.services.capability_service instead.
-> app.modules.capabilities.services.capability_service

Dual Capability Mapping Synchronization Service

Manages the coexistence of BusinessCapability and UnifiedCapability during migration.
Provides utilities for:
1. Mapping technical capabilities to both business types
2. Migrating data from BusinessCapability → UnifiedCapability
3. Deprecating old BusinessCapability records
4. Querying through either path
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import or_

from app.models import BusinessCapability, TechnicalCapability, UnifiedCapability, db


class DualCapabilityMappingService:
    """Manages dual mapping paths for backward compatibility."""

    @staticmethod
    def link_technical_to_both(
        technical_capability_id: int,
        business_capability_id: Optional[int] = None,
        unified_capability_id: Optional[int] = None,
        relationship_type: str = "supports",
    ) -> Dict:
        """
        Link a TechnicalCapability to both old and new capability models.

        Args:
            technical_capability_id: ID of TechnicalCapability
            business_capability_id: ID of BusinessCapability (legacy path)
            unified_capability_id: ID of UnifiedCapability (new path)
            relationship_type: Type of relationship

        Returns:
            Dict with mapping status
        """
        tech_cap = TechnicalCapability.query.get(technical_capability_id)
        if not tech_cap:
            return {"status": "error", "message": "TechnicalCapability not found"}

        result = {"status": "success", "legacy": None, "current": None}

        # Link to BusinessCapability (legacy)
        if business_capability_id:
            bus_cap = BusinessCapability.query.get(business_capability_id)
            if bus_cap:
                tech_cap.business_capabilities.append(bus_cap)
                result["legacy"] = {
                    "business_capability_id": business_capability_id,
                    "linked": True,
                }

        # Link to UnifiedCapability (current)
        if unified_capability_id:
            unified_cap = UnifiedCapability.query.get(unified_capability_id)
            if unified_cap:
                tech_cap.unified_capabilities.append(unified_cap)
                result["current"] = {"unified_capability_id": unified_capability_id, "linked": True}

        db.session.commit()
        return result

    @staticmethod
    def deprecate_business_capability(
        business_capability_id: int, unified_capability_id: int, notes: str = ""
    ) -> Dict:
        """
        Mark a BusinessCapability as deprecated in favor of UnifiedCapability.

        Args:
            business_capability_id: BusinessCapability to deprecate
            unified_capability_id: UnifiedCapability replacement
            notes: Deprecation notes

        Returns:
            Dict with deprecation status
        """
        bus_cap = BusinessCapability.query.get(business_capability_id)
        if not bus_cap:
            return {"status": "error", "message": "BusinessCapability not found"}

        unified_cap = UnifiedCapability.query.get(unified_capability_id)
        if not unified_cap:
            return {"status": "error", "message": "UnifiedCapability not found"}

        bus_cap.is_deprecated = True
        bus_cap.deprecated_as_of = datetime.utcnow()
        bus_cap.deprecated_in_favor_of_id = unified_capability_id
        bus_cap.deprecation_notes = notes

        db.session.commit()
        return {
            "status": "success",
            "deprecated": business_capability_id,
            "in_favor_of": unified_capability_id,
        }

    @staticmethod
    def get_technical_capability_mappings(technical_capability_id: int) -> Dict:
        """
        Get all mappings for a TechnicalCapability (both legacy and current).

        Args:
            technical_capability_id: ID of TechnicalCapability

        Returns:
            Dict with legacy and current mappings
        """
        tech_cap = TechnicalCapability.query.get(technical_capability_id)
        if not tech_cap:
            return {"status": "error", "message": "TechnicalCapability not found"}

        legacy_caps = [
            {
                "id": bc.id,
                "name": bc.name,
                "code": bc.code,
                "is_deprecated": bc.is_deprecated,
                "deprecated_in_favor_of_id": bc.deprecated_in_favor_of_id,
            }
            for bc in tech_cap.business_capabilities
        ]

        current_caps = [
            {
                "id": uc.id,
                "name": uc.name,
                "code": uc.code,
                "specialization_type": uc.specialization_type,
            }
            for uc in tech_cap.unified_capabilities
        ]

        return {
            "status": "success",
            "technical_capability_id": technical_capability_id,
            "legacy_business_capabilities": legacy_caps,
            "current_unified_capabilities": current_caps,
            "total_legacy": len(legacy_caps),
            "total_current": len(current_caps),
        }

    @staticmethod
    def migrate_business_to_unified(business_capability_id: int) -> Dict:
        """
        Migrate a BusinessCapability and its mappings to UnifiedCapability.

        Creates a new UnifiedCapability with same data and updates all
        TechnicalCapability mappings to point to the new capability.

        Args:
            business_capability_id: BusinessCapability to migrate

        Returns:
            Dict with migration status and new UnifiedCapability ID
        """
        bus_cap = BusinessCapability.query.get(business_capability_id)
        if not bus_cap:
            return {"status": "error", "message": "BusinessCapability not found"}

        # Create UnifiedCapability with same data
        unified_cap = UnifiedCapability(
            name=bus_cap.name,
            code=bus_cap.code if bus_cap.code else f"UNIFIED-{bus_cap.id}",
            description=bus_cap.description,
            level=bus_cap.level or 1,
            specialization_type="BUSINESS",
            category=bus_cap.category,
            business_value=bus_cap.business_value,
            strategic_importance=bus_cap.strategic_importance,
            business_owner=bus_cap.business_owner,
            current_maturity_level=bus_cap.current_maturity_level,
            target_maturity_level=bus_cap.target_maturity_level,
            kpis=bus_cap.kpis,
            discovered_by_ai=bus_cap.discovered_by_ai,
            discovery_confidence=bus_cap.discovery_confidence,
        )
        db.session.add(unified_cap)
        db.session.flush()

        # Migrate all technical capability mappings
        for tech_cap in bus_cap.technical_capabilities:
            tech_cap.unified_capabilities.append(unified_cap)

        # Mark original as deprecated
        bus_cap.is_deprecated = True
        bus_cap.deprecated_as_of = datetime.utcnow()
        bus_cap.deprecated_in_favor_of_id = unified_cap.id
        bus_cap.deprecation_notes = "Migrated to UnifiedCapability"

        db.session.commit()
        return {
            "status": "success",
            "original_business_capability_id": business_capability_id,
            "new_unified_capability_id": unified_cap.id,
            "message": f"Migrated {bus_cap.name} to UnifiedCapability",
        }

    @staticmethod
    def get_deprecated_capabilities(include_count: bool = False) -> List[Dict]:
        """
        Get all deprecated BusinessCapabilities.

        Args:
            include_count: Include count of technical mappings

        Returns:
            List of deprecated capabilities
        """
        deprecated = BusinessCapability.query.filter_by(is_deprecated=True).all()

        result = []
        for cap in deprecated:
            item = {
                "id": cap.id,
                "name": cap.name,
                "code": cap.code,
                "deprecated_as_of": cap.deprecated_as_of.isoformat()
                if cap.deprecated_as_of
                else None,
                "deprecated_in_favor_of_id": cap.deprecated_in_favor_of_id,
                "deprecation_notes": cap.deprecation_notes,
            }

            if include_count:
                item["technical_mapping_count"] = len(list(cap.technical_capabilities))

            result.append(item)

        return result

    @staticmethod
    def health_check() -> Dict:
        """
        Check health of dual mapping system.

        Returns:
            Dict with mapping statistics
        """
        total_technical = TechnicalCapability.query.count()
        total_business = BusinessCapability.query.count()
        total_unified = UnifiedCapability.query.count()
        deprecated_count = BusinessCapability.query.filter_by(is_deprecated=True).count()

        # Find orphaned mappings (technical with neither mapping)
        orphaned = (
            db.session.query(TechnicalCapability)
            .filter(
                ~TechnicalCapability.business_capabilities.any(),
                ~TechnicalCapability.unified_capabilities.any(),
            )
            .count()
        )

        return {
            "status": "ok",
            "technical_capabilities": total_technical,
            "business_capabilities": total_business,
            "unified_capabilities": total_unified,
            "deprecated_business_capabilities": deprecated_count,
            "orphaned_technical_capabilities": orphaned,
            "migration_ready": deprecated_count == total_business,
        }
