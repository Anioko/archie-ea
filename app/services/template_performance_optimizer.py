"""
Performance Optimization: Template Query & Caching
Implements efficient template retrieval with caching.
"""
import json
import logging
from functools import lru_cache

from flask import current_app

from app import db
from app.models import ElementTemplate
from app.services.core.cache_service import CacheService

logger = logging.getLogger(__name__)


class TemplatePerformanceOptimizer:
    """Optimizes template queries with caching and efficient DB queries."""

    def __init__(self):
        try:
            self.cache = CacheService()
        except Exception as e:
            logger.warning(f"Cache service initialization failed: {e} - continuing without cache")
            self.cache = None
        self.cache_ttl = 300  # 5 minutes

    def get_all_templates_optimized(self, framework=None, layer=None, archimate_type=None):
        """
        Get templates with optimized query and caching.

        Args:
            framework: Filter by framework (PCF, COBIT, TOGAF, etc.)
            layer: Filter by ArchiMate layer
            archimate_type: Filter by element type

        Returns:
            List of template dictionaries
        """
        cache_key = f"templates:fw={framework}:layer={layer}:type={archimate_type}"

        # Try cache first
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        else:
            logger.debug("Cache not available, skipping cache lookup")

        # Build optimized query
        query = ElementTemplate.query

        # CRITICAL FIX: Only filter if values are meaningful
        # Frontend may send empty strings or "null" instead of None
        if framework and framework not in ["null", "None", ""]:
            current_app.logger.debug(f"Filtering by framework: {framework}")
            query = query.filter(ElementTemplate.framework == framework)
        if layer and layer not in ["null", "None", ""]:
            current_app.logger.debug(f"Filtering by layer: {layer}")
            # Case-insensitive comparison using ilike
            query = query.filter(ElementTemplate.layer.ilike(layer))
        if archimate_type and archimate_type not in ["null", "None", "", "All Types"]:
            current_app.logger.debug(f"Filtering by element_type: {archimate_type}")
            # Case-insensitive comparison using ilike
            query = query.filter(ElementTemplate.element_type.ilike(archimate_type))

        # Order by name for consistent UX
        query = query.order_by(ElementTemplate.name)

        # Execute with query timeout
        current_app.logger.debug(
            f"Executing template query with filters - layer={layer}, type={archimate_type}"
        )
        templates = query.limit(1000).all()
        current_app.logger.debug(f"Found {len(templates)} templates")

        # Convert to dict
        result = [
            {
                "id": str(t.id),  # Convert to string to prevent JavaScript precision loss
                "name": t.name,
                "archimate_type": t.element_type,
                "layer": t.layer,
                "description": t.description,
                "properties": json.loads(t.default_properties) if t.default_properties else {},
                "category": t.category,
                "framework": t.framework,
                "code": t.code,
            }
            for t in templates
        ]

        # Cache result
        if self.cache:
            self.cache.set(cache_key, json.dumps(result), ttl=self.cache_ttl)
        else:
            logger.debug("Cache not available, skipping cache storage")

        return result

    def get_template_by_id_cached(self, template_id):
        """
        Get single template with caching.

        Args:
            template_id: Template ID

        Returns:
            Template dictionary or None
        """
        cache_key = f"template:{template_id}"

        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        else:
            logger.debug("Cache not available, skipping cache lookup")

        template = ElementTemplate.query.get(template_id)
        if not template:
            return None

        result = {
            "id": str(template.id),  # Convert to string to prevent JavaScript precision loss
            "name": template.name,
            "archimate_type": template.archimate_type,
            "layer": template.layer,
            "description": template.description,
            "properties": template.properties or {},
            "category": template.category,
            "usage_count": template.usage_count or 0,
            "relationships": template.relationships or [],
        }

        if self.cache:
            self.cache.set(cache_key, json.dumps(result), ttl=self.cache_ttl)
        else:
            logger.debug("Cache not available, skipping cache storage")
        return result

    def increment_usage_count(self, template_id):
        """
        Increment usage count for template (async, non-blocking).

        Args:
            template_id: Template ID
        """
        try:
            db.session.execute(
                db.text(
                    "UPDATE element_templates "
                    "SET usage_count = COALESCE(usage_count, 0) + 1 "
                    "WHERE id = :id"
                ),
                {"id": template_id},
            )
            db.session.commit()

            # Invalidate cache
            self.invalidate_template_cache(template_id)
        except Exception as e:
            current_app.logger.error(f"Failed to increment usage count: {e}")
            db.session.rollback()

    def invalidate_template_cache(self, template_id=None):
        """
        Invalidate template caches.

        Args:
            template_id: Specific template ID, or None for all
        """
        if template_id:
            self.cache.delete(f"template:{template_id}")

        # Invalidate list caches (pattern matching)
        self.cache.delete_pattern("templates:*")

    @lru_cache(maxsize=100)
    def get_layer_counts(self):
        """
        Get count of templates per layer (cached in memory).

        Returns:
            Dict mapping layer -> count
        """
        result = (
            db.session.query(ElementTemplate.layer, db.func.count(ElementTemplate.id))
            .group_by(ElementTemplate.layer)
            .all()
        )

        return {layer: count for layer, count in result}

    @lru_cache(maxsize=100)
    def get_type_counts(self):
        """
        Get count of templates per archimate type (cached in memory).

        Returns:
            Dict mapping type -> count
        """
        result = (
            db.session.query(ElementTemplate.archimate_type, db.func.count(ElementTemplate.id))
            .group_by(ElementTemplate.archimate_type)
            .all()
        )

        return {atype: count for atype, count in result}

    def bulk_get_templates(self, template_ids):
        """
        Efficiently get multiple templates by ID.

        Args:
            template_ids: List of template IDs

        Returns:
            Dict mapping ID -> template dict
        """
        if not template_ids:
            return {}

        # Try cache first
        result = {}
        missing_ids = []

        for tid in template_ids:
            cached = self.get_template_by_id_cached(tid)
            if cached:
                result[tid] = cached
            else:
                missing_ids.append(tid)

        # Fetch missing in bulk
        if missing_ids:
            templates = ElementTemplate.query.filter(ElementTemplate.id.in_(missing_ids)).all()

            for template in templates:
                data = {
                    "id": str(
                        template.id
                    ),  # Convert to string to prevent JavaScript precision loss
                    "name": template.name,
                    "archimate_type": template.archimate_type,
                    "layer": template.layer,
                    "description": template.description,
                    "properties": template.properties or {},
                    "category": template.category,
                    "usage_count": template.usage_count or 0,
                }
                result[str(template.id)] = data  # Use string key too

                # Cache individually
                cache_key = f"template:{template.id}"
                self.cache.set(cache_key, json.dumps(data), timeout=self.cache_ttl)

        return result


# Singleton instance
template_optimizer = TemplatePerformanceOptimizer()
