# app/config/kanban_jira_field_mapping.py
"""
KanbanCard -> Jira field mapping configuration.

Maps KanbanCard model fields to Jira issue fields using the same
rule-based pattern as jira_field_mapping.py (ApplicationComponent->Jira).

The Jira issue type is 'Task'. ADM phase is encoded as a label
so architects can filter by phase in Jira board views.
"""

# Priority translation: KanbanCard -> Jira
_PRIORITY_MAP = {
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}

# Card type -> Jira label
_CARD_TYPE_LABEL_MAP = {
    "requirement": "type:requirement",
    "design": "type:design",
    "implementation": "type:implementation",
    "review": "type:review",
    "other": "type:other",
}

# Column -> Jira status transition name
# Jira workflow status names must match the project's workflow exactly.
COLUMN_TO_JIRA_STATUS = {
    "proposed": "To Do",
    "under_development": "In Progress",
    "review": "In Review",
    "approved": "Done",
    "implementing": "In Progress",
    "done": "Done",
}

# ArchiMate element type -> Jira issue type (KAN project issue types: Epic, Subtask, Asset, Request, Research Item)
ARCH_ELEMENT_TO_JIRA_TYPE = {
    "WorkPackage": "Request",
    "Plateau": "Epic",
    "Gap": "Research Item",
    "ImplementationEvent": "Request",
    "Deliverable": "Request",
}

# Field rules list -- each dict drives build_jira_fields()
KANBAN_JIRA_FIELD_MAPPINGS = [
    {"card_field": "title",                "jira_field": "summary",     "transform": "plain"},
    {"card_field": "description",          "jira_field": "description", "transform": "adf"},
    {"card_field": "priority",             "jira_field": "priority",    "transform": "priority"},
    {"card_field": "adm_phase_code",       "jira_field": "labels",      "transform": "adm_label"},
    {"card_field": "card_type",            "jira_field": "labels",      "transform": "type_label"},
    {"card_field": "archimate_element_ids","jira_field": "labels",      "transform": "arch_element"},
]


def build_jira_fields(card_data: dict) -> dict:
    """
    Convert KanbanCard field dict into a Jira fields payload.

    Args:
        card_data: dict with keys: title, description, priority,
                   adm_phase_code, card_type, arch_element_type,
                   arch_domain, togaf_deliverable, requires_arb_signoff

    Returns:
        Jira fields dict ready to pass to JiraALMConnector.create_issue()
    """
    fields: dict = {}
    labels: list = []

    for rule in KANBAN_JIRA_FIELD_MAPPINGS:
        value = card_data.get(rule["card_field"]) or ""
        transform = rule["transform"]

        if transform == "plain":
            fields[rule["jira_field"]] = str(value)

        elif transform == "adf":
            text = str(value) if value else "No description provided."
            fields[rule["jira_field"]] = {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": text}],
                    }
                ],
            }

        elif transform == "priority":
            jira_prio = _PRIORITY_MAP.get(str(value).lower(), "Medium")
            fields[rule["jira_field"]] = {"name": jira_prio}

        elif transform == "adm_label":
            if value:
                labels.append(f"adm:phase-{str(value).upper()}")

        elif transform == "type_label":
            label = _CARD_TYPE_LABEL_MAP.get(str(value).lower(), f"type:{value}")
            labels.append(label)

        elif transform == "arch_element":
            # archimate_element_ids is a list of ArchiMateElement IDs
            ids = value if isinstance(value, list) else []
            for elem_id in ids:
                labels.append(f"arch:elem-{elem_id}")

    # ArchiMate/TOGAF semantic labels (ADM-003)
    element_type = card_data.get("arch_element_type") or ""
    if element_type:
        labels.append(f"archimate:{element_type.lower()}")
        if element_type == "ImplementationEvent":
            labels.append("archimate:event")

    arch_domain = card_data.get("arch_domain") or ""
    if arch_domain:
        labels.append(f"adm:domain-{arch_domain.lower()}")

    togaf_deliverable = card_data.get("togaf_deliverable") or ""
    if togaf_deliverable:
        labels.append("togaf:deliverable")
        short_name = togaf_deliverable.split()[0].lower() if togaf_deliverable.split() else ""
        if short_name:
            labels.append(f"togaf:del-{short_name}")

    if card_data.get("requires_arb_signoff"):
        labels.append("governance:arb-required")

    if labels:
        fields["labels"] = labels

    return fields


def get_jira_issue_type(card_data: dict) -> str:
    """Return the Jira issue type for a KanbanCard based on arch_element_type."""
    element_type = card_data.get("arch_element_type") or ""
    return ARCH_ELEMENT_TO_JIRA_TYPE.get(element_type, "Request")
