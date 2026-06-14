"""Property Service — templates, visibility, scoring, and save for element properties."""

import logging

logger = logging.getLogger(__name__)


def tiers_up_to(tier):
    """Returns list of required tiers up to and including the given tier."""
    order = ["standard", "important", "differentiating"]
    try:
        return order[:order.index(tier) + 1]
    except ValueError:
        return ["standard"]


def is_visible(template, properties):
    """Returns True if the property should be shown based on conditional logic.

    Handles both raw values and {value, source} dict format.
    """
    if template.conditional_on_key is None:
        return True
    parent_val = properties.get(template.conditional_on_key)
    # Handle {value, source} format
    if isinstance(parent_val, dict):
        parent_val = parent_val.get("value")
    if isinstance(parent_val, bool):
        return str(parent_val).lower() == template.conditional_on_value.lower()
    if parent_val is None:
        return False
    return str(parent_val).lower() == str(template.conditional_on_value).lower()


class PropertyService:
    """Manages element property templates, scoring, and persistence."""

    def get_templates_for_type(self, archimate_type, tier="standard", domain=None, tag_filter=None):
        """Get property templates for an element type, filtered by tier."""
        from app.models.acm_property_template import AcmPropertyTemplate

        query = AcmPropertyTemplate.query.filter_by(
            archimate_type=archimate_type,
        ).filter(
            AcmPropertyTemplate.required_for_tier.in_(tiers_up_to(tier))
        )

        if domain:
            query = query.filter(
                (AcmPropertyTemplate.acm_domain == domain) |
                (AcmPropertyTemplate.acm_domain.is_(None))
            )

        if tag_filter:
            query = query.filter(AcmPropertyTemplate.property_key.like(tag_filter + "%"))

        return [t.to_dict() for t in query.order_by(AcmPropertyTemplate.sort_order).all()]

    def calculate_element_score(self, archimate_type, properties, tier="standard", domain=None, tag_filter=None):
        """Calculate property completeness for a single element. Returns float 0.0-1.0."""
        from app.models.acm_property_template import AcmPropertyTemplate

        query = AcmPropertyTemplate.query.filter_by(
            archimate_type=archimate_type,
        ).filter(
            AcmPropertyTemplate.required_for_tier.in_(tiers_up_to(tier))
        )

        if tag_filter:
            query = query.filter(AcmPropertyTemplate.property_key.like(tag_filter + "%"))

        templates = query.all()
        visible = [t for t in templates if is_visible(t, properties)]

        if not visible:
            return 1.0

        filled = 0
        for t in visible:
            val = properties.get(t.property_key)
            if isinstance(val, dict):
                val = val.get("value")
            if val not in (None, "", "TBD"):
                filled += 1

        return filled / len(visible)

    # Sensible defaults when AcmPropertyTemplate.default_value is NULL
    _FALLBACK_DEFAULTS = {
        "ApplicationComponent": {
            "deployment_model": "cloud-native", "build_or_buy": "build",
            "availability_target": "99.9%", "hosting_target": "Cloud (TBD)",
            "technology_stack": "TBD", "estimated_users": "TBD",
            "scalability_pattern": "horizontal", "api_style": "REST",
            "team_owner": "TBD",
        },
        "ApplicationService": {
            "deployment_model": "cloud-native", "build_or_buy": "build",
            "availability_target": "99.9%", "api_style": "REST",
            "hosting_target": "Cloud (TBD)", "technology_stack": "TBD",
            "estimated_users": "TBD", "scalability_pattern": "horizontal",
            "team_owner": "TBD",
        },
        "ApplicationFunction": {
            "deployment_model": "cloud-native", "build_or_buy": "build",
        },
        "ApplicationInterface": {
            "interface_type": "REST-API", "authentication": "OAuth2",
            "rate_limit": "1000 req/min", "data_format": "JSON",
            "versioning_strategy": "URL-path",
        },
        "DataObject": {
            "data_classification": "internal", "contains_pii": False,
            "retention_period": "7 years", "retention_justification": "regulatory",
            "encryption_at_rest": "AES-256", "encryption_in_transit": "TLS-1.3",
            "backup_strategy": "daily", "refresh_frequency": "daily",
            "estimated_volume_initial": "TBD", "estimated_growth_monthly": "TBD",
            "data_owner": "TBD",
        },
        "BusinessObject": {
            "data_classification": "internal",
        },
        "Node": {
            "network_zone": "private", "managed_service": True,
            "dr_strategy": "active-passive", "compute_spec": "TBD",
            "storage_spec": "TBD", "license_model": "open-source",
            "support_tier": "standard",
        },
        "SystemSoftware": {
            "network_zone": "private", "managed_service": True,
            "license_model": "open-source", "support_tier": "standard",
        },
        "CommunicationNetwork": {
            "network_zone": "private",
        },
        "BusinessProcess": {
            "automation_level": "semi-automated",
            "process_frequency": "On demand", "responsible_team": "TBD",
        },
        "Requirement": {
            "priority": "should-have",
        },
        "Constraint": {
            "priority": "must-have",
        },
        "Principle": {
            "priority": "should-have",
        },
    }

    def get_default_properties(self, archimate_type, tier="standard"):
        """Return default property values for an element type.

        First reads from AcmPropertyTemplate.default_value, then falls back
        to hardcoded sensible defaults. Used to pre-fill baseline/NFR proposals
        so the architect starts with sensible values, not blanks.
        """
        from app.models.acm_property_template import AcmPropertyTemplate

        props = {}

        # Start with hardcoded fallbacks for this type
        fallbacks = self._FALLBACK_DEFAULTS.get(archimate_type, {})
        for key, val in fallbacks.items():
            props[key] = {"value": val, "source": "default"}

        # Override with template defaults where they exist
        try:
            templates = AcmPropertyTemplate.query.filter_by(
                archimate_type=archimate_type,
            ).filter(
                AcmPropertyTemplate.required_for_tier.in_(tiers_up_to(tier))
            ).all()
            for t in templates:
                if t.default_value is not None and t.default_value != "":
                    props[t.property_key] = {"value": t.default_value, "source": "default"}
        except Exception as e:
            logger.debug("Property template query skipped: %s", e)

        return props

    def merge_properties(self, existing, updates):
        """Merge user property updates. Sets source to 'user' on each update."""
        merged = dict(existing) if existing else {}
        for key, value in updates.items():
            merged[key] = {"value": value, "source": "user"}
        return merged

    @staticmethod
    def acm_slot_is_fillable(raw):
        """True if a default/LLM/suggested value may be written (never overwrites user)."""
        if raw is None:
            return True
        if isinstance(raw, dict):
            if raw.get("source") == "user":
                return False
            v = raw.get("value")
            if v is None:
                return True
            if isinstance(v, bool):
                return False
            s = str(v).strip()
            return s in ("", "TBD")
        s = str(raw).strip()
        return s in ("", "TBD")

    def merge_template_defaults_only(self, existing, archimate_type, tier="standard"):
        """Apply get_default_properties only where slots are empty. Preserves user edits."""
        props = dict(existing) if existing else {}
        defaults = self.get_default_properties(archimate_type, tier=tier)
        for key, entry in defaults.items():
            if self.acm_slot_is_fillable(props.get(key)):
                props[key] = entry
        return props
