"""Context enums for multi-level architecture (Enterprise, Application, Architecture)"""


class AnalysisContext:
    """
    Defines the three levels of analysis in the multi-level architecture:

    - ENTERPRISE: Portfolio-wide strategic analysis (3 - 5 years)
    - APPLICATION: Application-specific tactical analysis (6 - 18 months)
    - ARCHITECTURE: Technical implementation analysis (3 - 12 months, ArchiMate)
    """

    ENTERPRISE = "enterprise"
    APPLICATION = "application"
    ARCHITECTURE = "architecture"

    @classmethod
    def all(cls):
        """Return all valid context values"""
        return [cls.ENTERPRISE, cls.APPLICATION, cls.ARCHITECTURE]

    @classmethod
    def validate(cls, context):
        """Validate that a context value is valid"""
        return context in cls.all()

    @classmethod
    def get_label(cls, context):
        """Get human-readable label for context"""
        labels = {
            cls.ENTERPRISE: "Enterprise Portfolio",
            cls.APPLICATION: "Application",
            cls.ARCHITECTURE: "Architecture",
        }
        return labels.get(context, context)

    @classmethod
    def get_icon(cls, context):
        """Get icon/emoji for context"""
        icons = {cls.ENTERPRISE: "🏢", cls.APPLICATION: "📱", cls.ARCHITECTURE: "🏛️"}
        return icons.get(context, "📊")

    @classmethod
    def get_color(cls, context):
        """Get color class for context"""
        colors = {cls.ENTERPRISE: "purple", cls.APPLICATION: "blue", cls.ARCHITECTURE: "green"}
        return colors.get(context, "gray")


class RoadmapContext:
    """
    Roadmap context types - similar to AnalysisContext but for roadmaps
    """

    STRATEGIC = "strategic"  # Enterprise strategic roadmap (multi-year)
    APPLICATION = "application"  # Application feature roadmap
    IMPLEMENTATION = "implementation"  # ArchiMate implementation & migration

    @classmethod
    def all(cls):
        return [cls.STRATEGIC, cls.APPLICATION, cls.IMPLEMENTATION]

    @classmethod
    def validate(cls, context):
        return context in cls.all()


class GapType:
    """
    Standard gap types across all contexts
    """

    # Enterprise-level gaps
    MISSING_CAPABILITY = "missing_capability"  # No app provides this capability
    REDUNDANT_CAPABILITY = "redundant_capability"  # Too many apps do same thing
    IMMATURE_CAPABILITY = "immature_capability"  # Capability exists but immature
    OBSOLETE_TECHNOLOGY = "obsolete_technology"  # Technology is outdated

    # Application-level gaps
    MISSING_FEATURE = "missing_feature"  # Feature not implemented
    POOR_PERFORMANCE = "poor_performance"  # Performance issues
    POOR_UX = "poor_ux"  # User experience issues
    INTEGRATION_GAP = "integration_gap"  # Missing integration

    # Architecture-level gaps
    MISSING_COMPONENT = "missing_component"  # Component not implemented
    MISSING_INTERFACE = "missing_interface"  # Interface not defined
    TECHNOLOGY_MISMATCH = "technology_mismatch"  # Tech stack incompatibility

    @classmethod
    def get_types_for_context(cls, context):
        """Get relevant gap types for a specific context"""
        if context == AnalysisContext.ENTERPRISE:
            return [
                cls.MISSING_CAPABILITY,
                cls.REDUNDANT_CAPABILITY,
                cls.IMMATURE_CAPABILITY,
                cls.OBSOLETE_TECHNOLOGY,
            ]
        elif context == AnalysisContext.APPLICATION:
            return [cls.MISSING_FEATURE, cls.POOR_PERFORMANCE, cls.POOR_UX, cls.INTEGRATION_GAP]
        elif context == AnalysisContext.ARCHITECTURE:
            return [cls.MISSING_COMPONENT, cls.MISSING_INTERFACE, cls.TECHNOLOGY_MISMATCH]
        return []
