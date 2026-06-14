"""Shared form choice constants for the Applications module."""

DEFAULT_TOKEN_RATE_DIVISOR = 1_000_000  # fabricated-values-ok: standard token rate divisor (per million)

# ArchiMate relationship choices for forms
ARCHIMATE_RELATIONSHIP_CHOICES = [
    ("assignment", "Assignment"),
    ("serving", "Serving"),
    ("access", "Access"),
    ("association", "Association"),
    ("aggregation", "Aggregation"),
    ("composition", "Composition"),
    ("flow", "Flow"),
    ("triggering", "Triggering"),
    ("specialization", "Specialization"),
    ("realization", "Realization"),
]

# Capability mapping form choices
CAPABILITY_SUPPORT_LEVEL_CHOICES = [
    ("primary", "Primary"),
    ("secondary", "Secondary"),
    ("partial", "Partial"),
    ("legacy", "Legacy"),
    ("planned", "Planned"),
    ("linked", "Linked"),
]
CAPABILITY_MATURITY_CHOICES = [(str(level), f"Level {level}") for level in range(1, 6)]

# Vendor footprint form choices
VENDOR_DEPLOYMENT_CHOICES = [
    ("saas", "SaaS"),
    ("on_premise", "On-Premise"),
    ("hybrid", "Hybrid"),
    ("paas", "PaaS"),
    ("iaas", "IaaS"),
]
VENDOR_CRITICALITY_CHOICES = [
    ("critical", "Critical"),
    ("high", "High"),
    ("medium", "Medium"),
    ("low", "Low"),
]
VENDOR_HOSTING_CHOICES = [
    ("cloud", "Cloud"),
    ("on_premise", "On-Premise"),
    ("hybrid", "Hybrid"),
    ("colocation", "Colocation"),
]
