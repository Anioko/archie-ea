class PhaseViewpointBindingService:
    """
    Maps each TOGAF ADM phase workflow code to its canonical ArchiMate 3.2
    input element types, derived element types, and viewpoint name.
    """
    PHASE_BINDINGS = {
        "ADM_PHASE_A_VISION": {
            "phase_name": "Phase A — Architecture Vision",
            "input_types": ["Driver", "Stakeholder", "Goal", "Outcome"],
            "derived_types": ["Principle", "Requirement"],
            "viewpoint_name": "Stakeholder Viewpoint",
            "primary_layer": "motivation",
            "archimate_concern": "Identify key stakeholders and their concerns"
        },
        "ADM_PHASE_B_BUSINESS": {
            "phase_name": "Phase B — Business Architecture",
            "input_types": ["BusinessActor", "BusinessRole", "BusinessProcess"],
            "derived_types": ["BusinessService", "BusinessFunction"],
            "viewpoint_name": "Business Process Viewpoint",
            "primary_layer": "business",
            "archimate_concern": "Model business processes and services"
        },
        "ADM_PHASE_C_IS": {
            "phase_name": "Phase C — Information Systems Architecture",
            "input_types": ["ApplicationComponent", "DataObject"],
            "derived_types": ["ApplicationService", "ApplicationInterface"],
            "viewpoint_name": "Application Co-operation Viewpoint",
            "primary_layer": "application",
            "archimate_concern": "Define application components and data flows"
        },
        "ADM_PHASE_D_TECH": {
            "phase_name": "Phase D — Technology Architecture",
            "input_types": ["Node", "Device", "SystemSoftware"],
            "derived_types": ["TechnologyService", "Artifact"],
            "viewpoint_name": "Technology Usage Viewpoint",
            "primary_layer": "technology",
            "archimate_concern": "Define technology infrastructure"
        },
        "ADM_PHASE_E_OPPORTUNITIES": {
            "phase_name": "Phase E — Opportunities and Solutions",
            "input_types": ["Gap", "Capability"],
            "derived_types": ["CourseOfAction", "WorkPackage"],
            "viewpoint_name": "Gap Analysis Viewpoint",
            "primary_layer": "implementation_migration",
            "archimate_concern": "Identify gaps and solution options"
        },
        "ADM_PHASE_F_MIGRATION": {
            "phase_name": "Phase F — Migration Planning",
            "input_types": ["WorkPackage", "Plateau"],
            "derived_types": ["Deliverable", "ImplementationEvent"],
            "viewpoint_name": "Migration Viewpoint",
            "primary_layer": "implementation_migration",
            "archimate_concern": "Plan migration waves and plateaus"
        },
        "ADM_PHASE_G_GOVERNANCE": {
            "phase_name": "Phase G — Implementation Governance",
            "input_types": ["Principle", "Requirement", "Constraint"],
            "derived_types": ["Assessment"],
            "viewpoint_name": "Architecture Compliance Viewpoint",
            "primary_layer": "motivation",
            "archimate_concern": "Govern implementation against principles"
        },
        "ADM_PHASE_H_CHANGE": {
            "phase_name": "Phase H — Architecture Change Management",
            "input_types": ["Assessment", "Driver"],
            "derived_types": ["CourseOfAction"],
            "viewpoint_name": "Architecture Change Viewpoint",
            "primary_layer": "motivation",
            "archimate_concern": "Manage architecture change triggers"
        },
    }

    def get_binding(self, phase_code: str) -> dict | None:
        return self.PHASE_BINDINGS.get(phase_code)

    def get_input_element_types(self, phase_code: str) -> list:
        b = self.get_binding(phase_code)
        return b["input_types"] if b else []

    def get_derived_element_types(self, phase_code: str) -> list:
        b = self.get_binding(phase_code)
        return b["derived_types"] if b else []

    def get_all_phases(self) -> list:
        return list(self.PHASE_BINDINGS.keys())

    def get_viewpoint_name(self, phase_code: str) -> str:
        b = self.get_binding(phase_code)
        return b["viewpoint_name"] if b else "Unknown Viewpoint"

    def get_primary_layer(self, phase_code: str) -> str:
        b = self.get_binding(phase_code)
        return b["primary_layer"] if b else "unknown"
