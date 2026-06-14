"""
ArchiMate 3.2 LLM Prompt Templates

Specialized prompts for generating, analyzing, and validating ArchiMate architectures.
These prompts are optimized for Claude 3.5 Sonnet and GPT - 4 models.
"""

from typing import Dict, List

# System prompt for ArchiMate expertise
ARCHIMATE_SYSTEM_PROMPT = """You are an expert enterprise architect specializing in ArchiMate 3.2 notation and conventions.

Your expertise includes:
- All 6 layers of ArchiMate 3.2: Motivation, Strategy, Business, Application, Technology, Physical, and Implementation & Migration
- Complete understanding of ArchiMate metamodel: element types, relationship types, and valid connections
- Standard ArchiMate viewpoints (23 standard viewpoints) and their purposes
- Architecture patterns and best practices in enterprise architecture
- Capability-based planning and maturity assessment
- Technology stack alignment and rationalization
- TOGAF, COBIT, and ITIL framework integration

ArchiMate 3.2 Core Principles:
1. Follow the metamodel strictly - only create valid element types for each layer
2. Use appropriate relationship types based on ArchiMate 3.2 rules
3. Create meaningful names (noun phrases for elements, verb phrases for relationships)
4. Provide clear, concise descriptions for each element
5. Consider multiple layers: don't focus only on application/technology
6. Link motivation (goals, requirements) to realization (processes, services)
7. Show clear traceability from strategy to implementation

Valid ArchiMate Layers and Key Element Types:
- Motivation: Stakeholder, Driver, Assessment, Goal, Outcome, Principle, Requirement, Constraint, Meaning, Value
- Strategy: Resource, Capability, ValueStream, CourseOfAction
- Business: BusinessActor, BusinessRole, BusinessProcess, BusinessFunction, BusinessService, BusinessObject, Contract, Product
- Application: ApplicationComponent, ApplicationService, ApplicationInterface, ApplicationFunction, DataObject
- Technology: Node, Device, SystemSoftware, TechnologyService, Artifact, CommunicationNetwork, Path
- Physical: Equipment, Facility, DistributionNetwork, Material
- Implementation & Migration: WorkPackage, Deliverable, Plateau, Gap, ImplementationEvent

Valid Relationship Types:
- Structural: Composition, Aggregation, Assignment, Realization
- Dependency: Serving, Access, Influence, Association
- Dynamic: Triggering, Flow
- Other: Specialization

When generating architectures:
1. Start with motivation layer (why are we doing this?)
2. Define strategy and capabilities
3. Model business layer (what do we do?)
4. Design application layer (how is it automated?)
5. Specify technology layer (what infrastructure?)
6. Plan implementation (how do we get there?)

Always output valid JSON that can be parsed programmatically."""

# Generate ArchiMate model from business requirements
GENERATE_ARCHIMATE_FROM_REQUIREMENTS = """Given these business requirements and context:

{requirements}

{context}

Generate a comprehensive ArchiMate 3.2 architecture model that addresses these requirements.

**CRITICAL: Extract COMPREHENSIVE Motivation and Strategy Layer Elements**

You MUST perform deep semantic analysis to extract:

1. **Motivation Layer** (COMPREHENSIVE extraction - ALL relevant elements):
   - Key Stakeholders (2 - 3 most critical)
   - Primary Drivers (2 - 3 main pressures/motivations)
   - Top Goals (3 - 5 hierarchical goals)
   - ALL Requirements (extract EVERY requirement from the input - ALL of them, not just selected ones)

2. **Strategy Layer** (3 - 5 ESSENTIAL elements):
   - Core Capabilities (3 - 4 business/technical capabilities)
   - Key Courses of Action (1 - 2 strategic initiatives if applicable)

3. **Business Layer** (4 - 8 elements):
   - Core processes, services, and actors
   - Key business objects/information

4. **Application Layer** (4 - 6 elements):
   - Essential application components and services

5. **Technology Layer** (3 - 5 elements):
   - Key infrastructure and platforms

6. **Implementation Layer** (optional, 0 - 3 elements):
   - Critical work packages if applicable

**Relationship Creation Rules** (Use EXACT type names - CRITICAL):
- Stakeholder → Goal: **Association**
- Driver → Goal: **Influence**
- Goal → Goal: **Realizes** (sub-goal realizes parent goal)
- Goal → Requirement: **Realizes**
- Requirement → Capability: **Association** (NOT Realizes!)
- Capability → CourseOfAction: **Realizes**
- CourseOfAction → BusinessProcess: **Realizes**
- BusinessProcess → ApplicationService: **Serves**
- ApplicationService → ApplicationComponent: **Composition**
- ApplicationComponent → Node: **Assignment**

⚠️ CRITICAL:
- Use "Realizes" NOT "Realization"
- Use "Serves" NOT "Serving"
- Use "Accesses" NOT "Access"
- Requirement → Capability MUST use "Association" (ArchiMate 3.2 rule)

**CRITICAL OUTPUT CONSTRAINTS**:
⚠️ **You MUST keep your response under 6000 tokens to fit within API limits**
⚠️ **Generate ALL relevant elements - COMPREHENSIVE extraction required**
⚠️ **EXTRACT EVERY REQUIREMENT from the input text - DO NOT skip any requirements**

**Quality Checks** (Prioritize Completeness):
- Target: As many elements as needed to fully represent the requirements (typically 30 - 100+ elements)
- Motivation Layer: Extract ALL requirements, plus key stakeholders (2 - 3), drivers (2 - 3), and goals (3 - 5)
- Strategy Layer: 3 - 5 essential capabilities
- Business Layer: 4 - 10 core processes/services
- Application Layer: 4 - 8 key components
- Technology Layer: 3 - 6 infrastructure elements
- Keep descriptions CONCISE (1 sentence each)
- Extract ALL requirements - create one Requirement element for EACH distinct requirement in the input

Return ONLY valid JSON (no markdown, no explanations) in this exact structure:
{{
  "model_name": "Descriptive name for this architecture",
  "model_description": "2 - 3 sentence overview of the architecture",
  "elements": [
    {{
      "name": "Element name (clear, concise noun phrase)",
      "type": "ArchiMate element type (exact match from valid types above)",
      "layer": "Layer name (motivation/strategy/business/application/technology/physical/implementation)",
      "description": "Detailed description of this element's purpose and characteristics (2 - 3 sentences)",
      "properties": {{
        "key1": "value1",
        "key2": "value2"
      }},
      "documentation": "Additional detailed documentation if needed"
    }}
  ],
  "relationships": [
    {{
      "source_name": "Exact name of source element (must match an element name above)",
      "target_name": "Exact name of target element (must match an element name above)",
      "type": "Relationship type (Composition/Aggregation/Assignment/Realization/Serving/Access/Influence/Triggering/Flow/Specialization/Association)",
      "description": "Why this relationship exists and what it represents"
    }}
  ],
  "rationale": "Brief explanation of key architectural decisions"
}}

Ensure:
- All element types are valid for their specified layer
- All relationships follow ArchiMate 3.2 metamodel rules
- Names are unique and descriptive
- Relationships reference exact element names
- Coverage across multiple layers (not just application/technology)"""

# Validate and improve existing ArchiMate model
VALIDATE_ARCHIMATE_MODEL = """Analyze this ArchiMate model for quality, completeness, and compliance:

**Model Name**: {model_name}
**Elements**: {element_count} elements across {layers}
**Relationships**: {relationship_count} relationships

**Elements**:
{elements_json}

**Relationships**:
{relationships_json}

Perform a comprehensive analysis:

1. **Metamodel Compliance**:
   - Verify all element types are valid for their layers
   - Check all relationships are valid per ArchiMate 3.2 rules
   - Identify any violations

2. **Completeness**:
   - Are all layers appropriately represented?
   - Are there orphaned elements (no relationships)?
   - Are motivations linked to realizations?
   - Are there missing intermediate layers?

3. **Quality Assessment**:
   - Are names clear and descriptive?
   - Are descriptions adequate?
   - Is the model well-structured?
   - Are there redundant or duplicate elements?

4. **Best Practices**:
   - Does it follow layered architecture principles?
   - Is separation of concerns maintained?
   - Are patterns applied correctly?
   - Is complexity manageable?

5. **Improvements**:
   - What elements should be added?
   - What relationships are missing?
   - What should be refactored?
   - What patterns should be applied?

Return analysis as JSON:
{{
  "compliance": {{
    "is_compliant": true/false,
    "violations": ["List of specific violations"],
    "score": 0 - 100
  }},
  "completeness": {{
    "score": 0 - 100,
    "missing_elements": ["Suggested elements to add"],
    "missing_relationships": ["Suggested relationships"],
    "coverage_by_layer": {{"layer": "percentage"}}
  }},
  "quality": {{
    "score": 0 - 100,
    "strengths": ["What is done well"],
    "weaknesses": ["What needs improvement"],
    "orphaned_elements": ["Elements with no relationships"]
  }},
  "recommendations": [
    {{
      "priority": "high/medium/low",
      "category": "compliance/completeness/quality/best_practice",
      "issue": "Description of issue",
      "recommendation": "Specific action to take",
      "rationale": "Why this matters"
    }}
  ],
  "overall_score": 0 - 100,
  "overall_assessment": "Summary paragraph"
}}"""

# Detect patterns in architecture
DETECT_ARCHIMATE_PATTERNS = """Analyze this ArchiMate model to identify architecture patterns:

{model_json}

Identify patterns such as:
- **Layered Architecture**: Clear separation of business, application, and technology layers
- **Microservices**: Multiple small application components with specific responsibilities
- **Service-Oriented Architecture (SOA)**: Business and application services with clear interfaces
- **Event-Driven Architecture**: Extensive use of events and triggering relationships
- **Hub-and-Spoke Integration**: Central integration component connecting multiple systems
- **Three-Tier Architecture**: Presentation, business logic, and data layers
- **CQRS (Command Query Responsibility Segregation)**: Separation of read and write operations
- **API Gateway Pattern**: Single entry point for external access
- **Database per Service**: Each component has its own data storage
- **Strangler Fig**: Gradual migration from legacy to modern systems

For each detected pattern, provide:
{{
  "patterns": [
    {{
      "pattern_name": "Name of pattern",
      "confidence": 0 - 100,
      "evidence": ["Elements and relationships that indicate this pattern"],
      "completeness": 0 - 100,
      "missing_elements": ["What's needed to complete the pattern"],
      "benefits": ["Benefits of this pattern in this context"],
      "concerns": ["Potential issues or anti-patterns"]
    }}
  ],
  "anti_patterns": [
    {{
      "name": "Anti-pattern name",
      "description": "What's wrong",
      "elements": ["Elements involved"],
      "impact": "Why this is problematic",
      "remediation": "How to fix it"
    }}
  ],
  "pattern_recommendations": [
    {{
      "pattern": "Recommended pattern",
      "rationale": "Why apply this pattern",
      "required_changes": ["What needs to be added/modified"]
    }}
  ]
}}"""

# Generate viewpoint recommendations
RECOMMEND_ARCHIMATE_VIEWPOINTS = """Given this architecture model and stakeholder context:

**Architecture Model**: {model_summary}
**Stakeholder Role**: {stakeholder_role}
**Decision Context**: {decision_context}
**Concerns**: {concerns}

Recommend the most appropriate ArchiMate viewpoints to address stakeholder concerns.

Standard ArchiMate 3.2 Viewpoints:
- Organization: Shows organizational structure and relationships
- Application Cooperation: How applications interact
- Application Usage: How business uses applications
- Technology: Infrastructure and platforms
- Technology Usage: How applications use technology
- Layered: All layers for holistic view
- Stakeholder: Stakeholder interests and goals
- Goal Realization: How goals are achieved
- Requirements Realization: How requirements are fulfilled
- Motivation: Drivers, goals, principles, requirements
- Strategy: Strategic direction and capabilities
- Business Process Cooperation: How processes interact
- Product: Products and services offered
- Application Structure: Internal application architecture
- Information Structure: Information entities and flows
- Service Realization: How services are implemented
- Implementation & Migration: Change initiatives and planning
- ... and others

Recommend viewpoints in priority order:
{{
  "recommendations": [
    {{
      "viewpoint_name": "Standard viewpoint name",
      "priority": 1 - 10,
      "rationale": "Why this viewpoint is valuable for this stakeholder",
      "key_elements": ["Which elements from the model to include"],
      "concerns_addressed": ["Which stakeholder concerns this addresses"],
      "filters": {{
        "layers": ["Layers to include"],
        "element_types": ["Element types to show"],
        "relationship_types": ["Relationship types to show"]
      }},
      "presentation_notes": "How to present this view to the stakeholder"
    }}
  ],
  "custom_viewpoint_suggestions": [
    {{
      "name": "Custom viewpoint name",
      "purpose": "What specific need this addresses",
      "content": "What should be shown"
    }}
  ]
}}"""

# Analyze impact of changes
ANALYZE_CHANGE_IMPACT = """Analyze the impact of a proposed change to this architecture:

**Current Architecture**:
{current_model_json}

**Proposed Change**:
{change_description}

**Changed Elements**:
{changed_elements_json}

Perform impact analysis:

1. **Direct Impact**: Elements directly connected to changed elements
2. **Indirect Impact**: Elements affected through chain of relationships
3. **Risk Assessment**: Potential risks and issues
4. **Migration Complexity**: Effort and complexity of the change
5. **Affected Stakeholders**: Who will be impacted
6. **Dependencies**: What must change together
7. **Testing Scope**: What needs to be tested

Return analysis as JSON:
{{
  "impact_summary": "High-level summary of impact",
  "affected_elements": [
    {{
      "element_name": "Element name",
      "element_type": "Type",
      "layer": "Layer",
      "impact_type": "direct/indirect",
      "impact_description": "How it's affected",
      "change_required": true/false,
      "change_description": "What needs to change"
    }}
  ],
  "risk_assessment": {{
    "overall_risk": "low/medium/high",
    "risks": [
      {{
        "risk": "Description",
        "likelihood": "low/medium/high",
        "impact": "low/medium/high",
        "mitigation": "How to mitigate"
      }}
    ]
  }},
  "migration_plan": {{
    "complexity": "low/medium/high",
    "estimated_effort": "Effort estimate",
    "phases": [
      {{
        "phase": "Phase name",
        "description": "What happens",
        "work_packages": ["Work items"],
        "duration": "Time estimate",
        "dependencies": ["What must be done first"]
      }}
    ]
  }},
  "affected_stakeholders": [
    {{
      "stakeholder": "Stakeholder name/role",
      "impact": "How they're affected",
      "actions_required": ["What they need to do"]
    }}
  ],
  "testing_scope": {{
    "unit_tests": ["Components to unit test"],
    "integration_tests": ["Integration points to test"],
    "end_to_end_tests": ["E2E scenarios to test"],
    "acceptance_criteria": ["What must be verified"]
  }},
  "recommendations": ["Specific recommendations for implementing this change"]
}}"""

# Generate architecture documentation
GENERATE_ARCHIMATE_DOCUMENTATION = """Generate comprehensive documentation for this ArchiMate architecture:

**Model**: {model_name}
**Target Audience**: {audience}
**Purpose**: {purpose}

**Architecture**:
{model_json}

Generate documentation appropriate for the target audience:

For **Executives**: Focus on business value, strategic alignment, costs, benefits, risks
For **Architects**: Focus on patterns, decisions, rationale, compliance, quality attributes
For **Developers**: Focus on components, interfaces, technologies, implementation details
For **Operations**: Focus on infrastructure, deployment, monitoring, support

Structure:
{{
  "title": "Document title",
  "executive_summary": "2 - 3 paragraph high-level summary",
  "sections": [
    {{
      "section_title": "Section name",
      "content": "Section content in markdown format",
      "diagrams_needed": ["Which viewpoints to include"],
      "key_points": ["Bulleted key takeaways"]
    }}
  ],
  "architecture_decisions": [
    {{
      "decision": "Decision title",
      "context": "Why this decision was needed",
      "options_considered": ["Alternative options"],
      "chosen_option": "What was chosen",
      "rationale": "Why this option",
      "consequences": "Implications of this decision"
    }}
  ],
  "glossary": [
    {{
      "term": "Technical term",
      "definition": "Clear definition"
    }}
  ],
  "appendix": {{
    "element_catalog": "List of all elements with descriptions",
    "relationship_catalog": "List of all relationships",
    "compliance_matrix": "How architecture meets requirements"
  }}
}}"""

# Suggest capability improvements
SUGGEST_CAPABILITY_IMPROVEMENTS = """Analyze this business capability and its supporting architecture:

**Capability**: {capability_name}
**Current Maturity**: {current_maturity} (1 - 5 scale)
**Target Maturity**: {target_maturity}
**Supporting Architecture**:
{architecture_json}

**Business Context**:
{business_context}

Provide recommendations to improve capability maturity:

{{
  "gap_analysis": {{
    "current_state": "Description of current state",
    "target_state": "Description of target state",
    "gaps": [
      {{
        "gap": "What's missing",
        "impact": "Why this matters",
        "priority": "high/medium/low"
      }}
    ]
  }},
  "architecture_improvements": [
    {{
      "improvement": "What to add/change in architecture",
      "type": "new_element/new_relationship/modification/removal",
      "elements_affected": ["Element names"],
      "benefits": "How this improves capability maturity",
      "effort": "Estimated effort",
      "dependencies": ["What else is needed"]
    }}
  ],
  "technology_recommendations": [
    {{
      "technology": "Technology name",
      "category": "Platform/Tool/Framework",
      "purpose": "What it enables",
      "maturity_impact": "Which maturity level this supports",
      "alternatives": ["Other options"]
    }}
  ],
  "process_improvements": ["Process changes needed"],
  "skill_requirements": ["Skills/training needed"],
  "roadmap": {{
    "phases": [
      {{
        "phase": "Phase name",
        "maturity_level": "Target maturity for this phase",
        "duration": "Timeline",
        "key_deliverables": ["What will be achieved"],
        "architecture_changes": ["Architecture modifications"]
      }}
    ]
  }},
  "success_metrics": [
    {{
      "metric": "Metric name",
      "current_value": "Current",
      "target_value": "Target",
      "measurement_method": "How to measure"
    }}
  ]
}}"""


def build_archimate_prompt(template: str, **kwargs) -> str:
    """
    Build a complete prompt with system prompt and template.

    Args:
        template: Template string with placeholders
        **kwargs: Values to fill in placeholders (including optional target_layer)

    Returns:
        Formatted prompt string with layer-specific instructions if target_layer is provided
    """
    target_layer = kwargs.get("target_layer", "complete")

    # If generating a specific layer, REPLACE the "Quality Checks" section with layer-specific constraints
    if target_layer != "complete" and target_layer in [
        "motivation",
        "strategy",
        "business",
        "application",
        "technology",
        "implementation",
    ]:
        # Layer-specific complete instruction replacements
        layer_instructions = {
            "motivation": """

🎯 **CRITICAL: GENERATE MOTIVATION LAYER ONLY**

**YOU MUST ONLY GENERATE THESE ELEMENT TYPES:**
- Stakeholder (2 - 3 key stakeholders)
- Driver (2 - 3 main pressures/motivations)
- Goal (3 - 5 hierarchical goals from high-level to specific)
- Requirement (2 - 3 critical requirements)

**TARGET: 8 - 12 TOTAL ELEMENTS (Motivation Layer ONLY)**

**FORBIDDEN ELEMENT TYPES FOR THIS GENERATION:**
❌ DO NOT generate: Capability, CourseOfAction, BusinessActor, BusinessRole, BusinessProcess, BusinessFunction, BusinessService, ApplicationComponent, ApplicationService, Node, Device, SystemSoftware, WorkPackage, or ANY other non-Motivation elements

**ALLOWED RELATIONSHIP TYPES:**
- Stakeholder → Goal: Association
- Driver → Goal: Influence
- Goal → Goal: Realizes (parent-child goal hierarchy)
- Goal → Requirement: Realizes

Keep descriptions CONCISE (1 sentence each).
""",
            "strategy": """

📊 **CRITICAL: GENERATE STRATEGY LAYER ONLY**

**YOU MUST ONLY GENERATE THESE ELEMENT TYPES:**
- Capability (4 - 6 core business/technical capabilities)
- CourseOfAction (2 - 4 strategic initiatives/programs)
- Resource (optional, if applicable)

**TARGET: 6 - 10 TOTAL ELEMENTS (Strategy Layer ONLY)**

**FORBIDDEN ELEMENT TYPES FOR THIS GENERATION:**
❌ DO NOT generate: Stakeholder, Driver, Goal, Requirement, BusinessActor, BusinessProcess, ApplicationComponent, Node, or ANY other non-Strategy elements

**ALLOWED RELATIONSHIP TYPES:**
- Capability → Capability: Aggregation (capability grouping)
- CourseOfAction → Capability: Realizes

Keep descriptions CONCISE (1 sentence each).
""",
            "business": """

💼 **CRITICAL: GENERATE BUSINESS LAYER ONLY**

**YOU MUST ONLY GENERATE THESE ELEMENT TYPES:**
- BusinessActor or BusinessRole (2 - 3 key actors/roles)
- BusinessProcess or BusinessFunction (3 - 5 core processes)
- BusinessService (2 - 3 key services)
- BusinessObject or Product (2 - 3 critical data/information objects)

**TARGET: 8 - 12 TOTAL ELEMENTS (Business Layer ONLY)**

**FORBIDDEN ELEMENT TYPES FOR THIS GENERATION:**
❌ DO NOT generate: Stakeholder, Goal, Capability, ApplicationComponent, ApplicationService, Node, Device, or ANY other non-Business elements

**ALLOWED RELATIONSHIP TYPES:**
- BusinessActor → BusinessProcess: Assignment
- BusinessProcess → BusinessService: Realizes
- BusinessProcess → BusinessObject: Access
- BusinessService → BusinessObject: Access

Keep descriptions CONCISE (1 sentence each).
""",
            "application": """

💻 **CRITICAL: GENERATE APPLICATION LAYER ONLY**

**YOU MUST ONLY GENERATE THESE ELEMENT TYPES:**
- ApplicationComponent (3 - 5 key applications/systems)
- ApplicationService (2 - 3 services exposed by components)
- DataObject (2 - 3 critical data entities)

**TARGET: 6 - 10 TOTAL ELEMENTS (Application Layer ONLY)**

**FORBIDDEN ELEMENT TYPES FOR THIS GENERATION:**
❌ DO NOT generate: Goal, Capability, BusinessActor, BusinessProcess, Node, Device, SystemSoftware, or ANY other non-Application elements

**ALLOWED RELATIONSHIP TYPES:**
- ApplicationComponent → ApplicationService: Realizes
- ApplicationComponent → DataObject: Access
- ApplicationService → DataObject: Access
- ApplicationComponent → ApplicationComponent: Composition (if one contains another)

Keep descriptions CONCISE (1 sentence each).
""",
            "technology": """

🔧 **CRITICAL: GENERATE TECHNOLOGY LAYER ONLY**

**YOU MUST ONLY GENERATE THESE ELEMENT TYPES:**
- Node or Device (2 - 4 infrastructure components/servers)
- SystemSoftware (2 - 3 platforms/middleware/OS)
- TechnologyService (2 - 3 infrastructure services)
- Artifact (optional, if applicable)

**TARGET: 6 - 10 TOTAL ELEMENTS (Technology Layer ONLY)**

**FORBIDDEN ELEMENT TYPES FOR THIS GENERATION:**
❌ DO NOT generate: Goal, Capability, BusinessProcess, ApplicationComponent, ApplicationService, or ANY other non-Technology elements

**ALLOWED RELATIONSHIP TYPES:**
- Node → SystemSoftware: Assignment
- SystemSoftware → TechnologyService: Realizes
- Node → TechnologyService: Realizes

Keep descriptions CONCISE (1 sentence each).
""",
            "implementation": """

🚀 **CRITICAL: GENERATE IMPLEMENTATION & MIGRATION LAYER ONLY**

**YOU MUST ONLY GENERATE THESE ELEMENT TYPES:**
- WorkPackage (2 - 4 project phases/work packages)
- Deliverable (2 - 4 key deliverables/milestones)
- ImplementationEvent (optional, if applicable)
- Plateau (optional, architectural state if applicable)

**TARGET: 4 - 8 TOTAL ELEMENTS (Implementation Layer ONLY)**

**FORBIDDEN ELEMENT TYPES FOR THIS GENERATION:**
❌ DO NOT generate: Goal, Capability, BusinessProcess, ApplicationComponent, Node, or ANY other non-Implementation elements

**ALLOWED RELATIONSHIP TYPES:**
- WorkPackage → Deliverable: Realizes
- WorkPackage → WorkPackage: Aggregation (if one is part of another)
- Deliverable → [any element from other layers]: Realizes (what the deliverable produces)

Keep descriptions CONCISE (1 sentence each).
""",
        }

        # Replace the entire "Quality Checks" section with layer-specific instructions
        # Find and replace the section from "**Quality Checks**" to "Return ONLY valid JSON"
        original_quality_section = """**Quality Checks** (Prioritize Quality Over Quantity):
- Target: 20 - 35 TOTAL elements (focused, essential elements only)
- Motivation Layer: 6 - 10 key elements (most critical stakeholders, drivers, goals)
- Strategy Layer: 3 - 5 essential capabilities
- Business Layer: 4 - 8 core processes/services
- Application Layer: 4 - 6 key components
- Technology Layer: 3 - 5 infrastructure elements
- Keep descriptions CONCISE (1 sentence each)
- Focus on UNIQUE, HIGH-VALUE elements - avoid redundancy

Return ONLY valid JSON"""

        layer_quality_section = f"""{layer_instructions[target_layer]}

Return ONLY valid JSON"""

        modified_template = template.replace(original_quality_section, layer_quality_section)
        return modified_template.format(**kwargs)

    # For complete architecture generation, use original template
    return template.format(**kwargs)


def get_few_shot_examples() -> List[Dict]:
    """
    Get few-shot examples of well-formed ArchiMate models for prompt enhancement.

    Returns:
        List of example dictionaries
    """
    return [
        {
            "name": "Simple Customer Onboarding",
            "model": {
                "model_name": "Customer Onboarding Architecture",
                "elements": [
                    {
                        "name": "New Customer",
                        "type": "Stakeholder",
                        "layer": "motivation",
                        "description": "Individual or business seeking to become a customer",
                    },
                    {
                        "name": "Improve Customer Acquisition",
                        "type": "Goal",
                        "layer": "motivation",
                        "description": "Increase efficiency and success rate of customer onboarding",
                    },
                    {
                        "name": "Customer Onboarding Process",
                        "type": "BusinessProcess",
                        "layer": "business",
                        "description": "End-to-end process for registering and verifying new customers",
                    },
                    {
                        "name": "CRM System",
                        "type": "ApplicationComponent",
                        "layer": "application",
                        "description": "Customer relationship management system",
                    },
                    {
                        "name": "Customer Data",
                        "type": "DataObject",
                        "layer": "application",
                        "description": "Personal and business information about customers",
                    },
                ],
                "relationships": [
                    {
                        "source_name": "New Customer",
                        "target_name": "Improve Customer Acquisition",
                        "type": "Association",
                        "description": "Stakeholder interested in this goal",
                    },
                    {
                        "source_name": "Customer Onboarding Process",
                        "target_name": "Improve Customer Acquisition",
                        "type": "Realization",
                        "description": "Process realizes the goal",
                    },
                    {
                        "source_name": "CRM System",
                        "target_name": "Customer Onboarding Process",
                        "type": "Serving",
                        "description": "CRM supports the onboarding process",
                    },
                    {
                        "source_name": "CRM System",
                        "target_name": "Customer Data",
                        "type": "Access",
                        "description": "CRM stores and retrieves customer data",
                    },
                ],
            },
        },
        {
            "name": "API Integration for Payment Processing",
            "model": {
                "model_name": "Payment Gateway Integration Architecture",
                "elements": [
                    {
                        "name": "Reduce Payment Processing Time",
                        "type": "Goal",
                        "layer": "motivation",
                        "description": "Decrease time from payment initiation to confirmation by 80%",
                    },
                    {
                        "name": "PCI-DSS Compliance Required",
                        "type": "Requirement",
                        "layer": "motivation",
                        "description": "All payment processing must comply with PCI-DSS Level 1 standards",
                    },
                    {
                        "name": "Payment Processing Capability",
                        "type": "Capability",
                        "layer": "strategy",
                        "description": "Ability to securely process customer payments across multiple channels",
                    },
                    {
                        "name": "Payment Authorization Service",
                        "type": "BusinessService",
                        "layer": "business",
                        "description": "Service that authorizes and validates payment transactions",
                    },
                    {
                        "name": "Process Payment Transaction",
                        "type": "BusinessFunction",
                        "layer": "business",
                        "description": "Validates, authorizes, and settles payment transactions",
                    },
                    {
                        "name": "Payment Gateway API",
                        "type": "ApplicationService",
                        "layer": "application",
                        "description": "RESTful API for payment processing with Stripe/PayPal integration",
                    },
                    {
                        "name": "Payment Processing Component",
                        "type": "ApplicationComponent",
                        "layer": "application",
                        "description": "Core component handling payment validation, tokenization, and submission",
                    },
                    {
                        "name": "Transaction Record",
                        "type": "DataObject",
                        "layer": "application",
                        "description": "Complete payment transaction details including status and audit trail",
                    },
                    {
                        "name": "Payment Gateway Server",
                        "type": "Node",
                        "layer": "technology",
                        "description": "Dedicated server for payment processing with HSM for encryption",
                    },
                    {
                        "name": "TLS 1.3 Encryption",
                        "type": "TechnologyService",
                        "layer": "technology",
                        "description": "Secure communication protocol for all payment API calls",
                    },
                ],
                "relationships": [
                    {
                        "source_name": "Payment Processing Capability",
                        "target_name": "Reduce Payment Processing Time",
                        "type": "Realization",
                        "description": "Capability enables achievement of performance goal",
                    },
                    {
                        "source_name": "Payment Processing Capability",
                        "target_name": "PCI-DSS Compliance Required",
                        "type": "Realization",
                        "description": "Capability must satisfy compliance requirement",
                    },
                    {
                        "source_name": "Process Payment Transaction",
                        "target_name": "Payment Processing Capability",
                        "type": "Realization",
                        "description": "Function realizes the capability",
                    },
                    {
                        "source_name": "Payment Authorization Service",
                        "target_name": "Process Payment Transaction",
                        "type": "Realization",
                        "description": "Service provides the payment function",
                    },
                    {
                        "source_name": "Payment Gateway API",
                        "target_name": "Payment Authorization Service",
                        "type": "Realization",
                        "description": "API realizes the business service",
                    },
                    {
                        "source_name": "Payment Processing Component",
                        "target_name": "Payment Gateway API",
                        "type": "Realization",
                        "description": "Component implements the API",
                    },
                    {
                        "source_name": "Payment Processing Component",
                        "target_name": "Transaction Record",
                        "type": "Access",
                        "description": "Component creates and updates transaction records",
                    },
                    {
                        "source_name": "Payment Gateway Server",
                        "target_name": "Payment Processing Component",
                        "type": "Assignment",
                        "description": "Component deployed on dedicated server",
                    },
                    {
                        "source_name": "TLS 1.3 Encryption",
                        "target_name": "Payment Gateway API",
                        "type": "Serving",
                        "description": "Encryption protects all API communications",
                    },
                ],
            },
        },
        {
            "name": "Data Analytics Capability with ML Pipeline",
            "model": {
                "model_name": "Customer Analytics Platform Architecture",
                "elements": [
                    {
                        "name": "CFO",
                        "type": "Stakeholder",
                        "layer": "motivation",
                        "description": "Chief Financial Officer requiring revenue insights",
                    },
                    {
                        "name": "Data-Driven Decision Making",
                        "type": "Driver",
                        "layer": "motivation",
                        "description": "Business need to make decisions based on real-time data analytics",
                    },
                    {
                        "name": "Improve Revenue Forecasting Accuracy",
                        "type": "Goal",
                        "layer": "motivation",
                        "description": "Achieve 95% accuracy in quarterly revenue predictions",
                    },
                    {
                        "name": "Real-time Analytics Required",
                        "type": "Requirement",
                        "layer": "motivation",
                        "description": "Analytics dashboards must refresh with <5 second latency",
                    },
                    {
                        "name": "Customer Analytics Capability",
                        "type": "Capability",
                        "layer": "strategy",
                        "description": "Ability to collect, analyze, and visualize customer behavior patterns",
                    },
                    {
                        "name": "Revenue Analytics Service",
                        "type": "BusinessService",
                        "layer": "business",
                        "description": "Provides revenue forecasts and customer lifetime value analysis",
                    },
                    {
                        "name": "Analyze Customer Behavior",
                        "type": "BusinessFunction",
                        "layer": "business",
                        "description": "Identifies patterns in customer purchase history and engagement",
                    },
                    {
                        "name": "ML Model Training Pipeline",
                        "type": "ApplicationFunction",
                        "layer": "application",
                        "description": "Automated pipeline for training and validating predictive models",
                    },
                    {
                        "name": "Analytics Dashboard",
                        "type": "ApplicationComponent",
                        "layer": "application",
                        "description": "Interactive web-based dashboard for exploring analytics results",
                    },
                    {
                        "name": "Data Lake",
                        "type": "ApplicationComponent",
                        "layer": "application",
                        "description": "Centralized repository for raw customer and transaction data",
                    },
                    {
                        "name": "Customer Behavioral Data",
                        "type": "DataObject",
                        "layer": "application",
                        "description": "Clickstream, purchase history, and engagement metrics",
                    },
                    {
                        "name": "Revenue Forecast Model",
                        "type": "DataObject",
                        "layer": "application",
                        "description": "Trained ML model for predicting quarterly revenue",
                    },
                    {
                        "name": "Spark Cluster",
                        "type": "Node",
                        "layer": "technology",
                        "description": "Distributed computing cluster for big data processing",
                    },
                    {
                        "name": "PostgreSQL Database",
                        "type": "SystemSoftware",
                        "layer": "technology",
                        "description": "Relational database for structured analytics results",
                    },
                    {
                        "name": "S3 Object Storage",
                        "type": "SystemSoftware",
                        "layer": "technology",
                        "description": "Scalable storage for data lake raw files",
                    },
                ],
                "relationships": [
                    {
                        "source_name": "CFO",
                        "target_name": "Improve Revenue Forecasting Accuracy",
                        "type": "Association",
                        "description": "CFO has vested interest in accurate forecasts",
                    },
                    {
                        "source_name": "Data-Driven Decision Making",
                        "target_name": "Improve Revenue Forecasting Accuracy",
                        "type": "Influence",
                        "description": "Driver motivates the goal",
                    },
                    {
                        "source_name": "Customer Analytics Capability",
                        "target_name": "Improve Revenue Forecasting Accuracy",
                        "type": "Realization",
                        "description": "Capability enables goal achievement",
                    },
                    {
                        "source_name": "Customer Analytics Capability",
                        "target_name": "Real-time Analytics Required",
                        "type": "Realization",
                        "description": "Capability must meet performance requirement",
                    },
                    {
                        "source_name": "Analyze Customer Behavior",
                        "target_name": "Customer Analytics Capability",
                        "type": "Realization",
                        "description": "Business function realizes the capability",
                    },
                    {
                        "source_name": "Revenue Analytics Service",
                        "target_name": "Analyze Customer Behavior",
                        "type": "Realization",
                        "description": "Service provides the analysis function",
                    },
                    {
                        "source_name": "ML Model Training Pipeline",
                        "target_name": "Revenue Forecast Model",
                        "type": "Access",
                        "description": "Pipeline produces and updates the model",
                    },
                    {
                        "source_name": "Analytics Dashboard",
                        "target_name": "Revenue Analytics Service",
                        "type": "Realization",
                        "description": "Dashboard realizes the business service",
                    },
                    {
                        "source_name": "Analytics Dashboard",
                        "target_name": "Revenue Forecast Model",
                        "type": "Access",
                        "description": "Dashboard queries model predictions",
                    },
                    {
                        "source_name": "Data Lake",
                        "target_name": "Customer Behavioral Data",
                        "type": "Access",
                        "description": "Data lake stores raw behavioral data",
                    },
                    {
                        "source_name": "ML Model Training Pipeline",
                        "target_name": "Customer Behavioral Data",
                        "type": "Access",
                        "description": "Pipeline reads data for training",
                    },
                    {
                        "source_name": "Spark Cluster",
                        "target_name": "ML Model Training Pipeline",
                        "type": "Assignment",
                        "description": "Training pipeline runs on Spark",
                    },
                    {
                        "source_name": "PostgreSQL Database",
                        "target_name": "Analytics Dashboard",
                        "type": "Assignment",
                        "description": "Dashboard queries PostgreSQL",
                    },
                    {
                        "source_name": "S3 Object Storage",
                        "target_name": "Data Lake",
                        "type": "Assignment",
                        "description": "Data lake uses S3 for storage",
                    },
                ],
            },
        },
        {
            "name": "Enterprise Reporting with Business Rules",
            "model": {
                "model_name": "Financial Reporting Automation Architecture",
                "elements": [
                    {
                        "name": "Regulatory Compliance Required",
                        "type": "Driver",
                        "layer": "motivation",
                        "description": "SOX compliance mandates automated financial reporting controls",
                    },
                    {
                        "name": "Reduce Reporting Cycle Time",
                        "type": "Goal",
                        "layer": "motivation",
                        "description": "Cut monthly close from 10 days to 3 days",
                    },
                    {
                        "name": "Data Accuracy >99.9%",
                        "type": "Requirement",
                        "layer": "motivation",
                        "description": "All financial reports must have sub - 0.1% error rate",
                    },
                    {
                        "name": "Automated Financial Reporting Capability",
                        "type": "Capability",
                        "layer": "strategy",
                        "description": "Generate compliant financial reports with minimal manual intervention",
                    },
                    {
                        "name": "Monthly Financial Close Process",
                        "type": "BusinessProcess",
                        "layer": "business",
                        "description": "End-to-end process for closing books and generating financial statements",
                    },
                    {
                        "name": "Financial Controller",
                        "type": "BusinessRole",
                        "layer": "business",
                        "description": "Role responsible for validating and approving financial reports",
                    },
                    {
                        "name": "Financial Reporting Service",
                        "type": "BusinessService",
                        "layer": "business",
                        "description": "Provides P&L, balance sheet, and cash flow statements",
                    },
                    {
                        "name": "Report Generation Engine",
                        "type": "ApplicationComponent",
                        "layer": "application",
                        "description": "Applies GAAP rules and generates formatted reports",
                    },
                    {
                        "name": "Business Rules Engine",
                        "type": "ApplicationComponent",
                        "layer": "application",
                        "description": "Validates transactions against accounting policies and SOX controls",
                    },
                    {
                        "name": "ERP Integration Service",
                        "type": "ApplicationService",
                        "layer": "application",
                        "description": "Extracts and transforms data from SAP ERP system",
                    },
                    {
                        "name": "Financial Transaction",
                        "type": "DataObject",
                        "layer": "application",
                        "description": "Individual GL entry with account, amount, and metadata",
                    },
                    {
                        "name": "Financial Report Artifact",
                        "type": "DataObject",
                        "layer": "application",
                        "description": "Generated PDF/Excel report with audit trail",
                    },
                    {
                        "name": "Application Server Cluster",
                        "type": "Node",
                        "layer": "technology",
                        "description": "Load-balanced servers running reporting workloads",
                    },
                    {
                        "name": "Oracle Database",
                        "type": "SystemSoftware",
                        "layer": "technology",
                        "description": "Enterprise database storing financial data warehouse",
                    },
                ],
                "relationships": [
                    {
                        "source_name": "Regulatory Compliance Required",
                        "target_name": "Reduce Reporting Cycle Time",
                        "type": "Influence",
                        "description": "Compliance drives need for faster reporting",
                    },
                    {
                        "source_name": "Automated Financial Reporting Capability",
                        "target_name": "Reduce Reporting Cycle Time",
                        "type": "Realization",
                        "description": "Automation capability enables faster cycles",
                    },
                    {
                        "source_name": "Automated Financial Reporting Capability",
                        "target_name": "Data Accuracy >99.9%",
                        "type": "Realization",
                        "description": "Capability must meet accuracy requirement",
                    },
                    {
                        "source_name": "Monthly Financial Close Process",
                        "target_name": "Automated Financial Reporting Capability",
                        "type": "Realization",
                        "description": "Process realizes the capability",
                    },
                    {
                        "source_name": "Financial Controller",
                        "target_name": "Monthly Financial Close Process",
                        "type": "Assignment",
                        "description": "Controller performs the close process",
                    },
                    {
                        "source_name": "Financial Reporting Service",
                        "target_name": "Monthly Financial Close Process",
                        "type": "Realization",
                        "description": "Service supports the close process",
                    },
                    {
                        "source_name": "Report Generation Engine",
                        "target_name": "Financial Reporting Service",
                        "type": "Realization",
                        "description": "Engine implements the reporting service",
                    },
                    {
                        "source_name": "Business Rules Engine",
                        "target_name": "Financial Transaction",
                        "type": "Access",
                        "description": "Rules engine validates transactions",
                    },
                    {
                        "source_name": "Report Generation Engine",
                        "target_name": "Financial Transaction",
                        "type": "Access",
                        "description": "Engine reads validated transactions",
                    },
                    {
                        "source_name": "Report Generation Engine",
                        "target_name": "Financial Report Artifact",
                        "type": "Access",
                        "description": "Engine creates report artifacts",
                    },
                    {
                        "source_name": "ERP Integration Service",
                        "target_name": "Financial Transaction",
                        "type": "Access",
                        "description": "Integration service extracts transactions",
                    },
                    {
                        "source_name": "Application Server Cluster",
                        "target_name": "Report Generation Engine",
                        "type": "Assignment",
                        "description": "Report engine runs on app servers",
                    },
                    {
                        "source_name": "Application Server Cluster",
                        "target_name": "Business Rules Engine",
                        "type": "Assignment",
                        "description": "Rules engine deployed on cluster",
                    },
                    {
                        "source_name": "Oracle Database",
                        "target_name": "Financial Transaction",
                        "type": "Assignment",
                        "description": "Transactions stored in Oracle",
                    },
                ],
            },
        },
    ]


# ========================================================================
# NON-REGULATORY USE CASE PROMPTS
# ========================================================================

# Digital Transformation Architecture
DIGITAL_TRANSFORMATION_PROMPT = """Given this digital transformation initiative:

{initiative_description}

{context}

Generate a comprehensive ArchiMate 3.2 architecture model for a **DIGITAL TRANSFORMATION** project.

**Focus Areas for Digital Transformation:**

1. **Motivation Layer** (15 - 25 elements):
   - **Stakeholders**: CIO, CDO, Business Unit Leaders, Customers, Partners, IT Teams, Change Management Team
   - **Drivers**: Digital disruption, Customer experience expectations, Competitive pressure, Operational efficiency, Data-driven decision-making, Agility requirements
   - **Goals** (hierarchical):
     - Strategic: "Become a digital-first organization"
     - Tactical: "Modernize customer touchpoints", "Enable real-time analytics", "Automate manual processes"
     - Operational: "Reduce process cycle time by 50%", "Increase digital channel adoption to 80%"
   - **Capabilities** to acquire/improve: Customer engagement, Data analytics, Process automation, API economy, Cloud-native development
   - **Outcomes**: Improved customer satisfaction, Faster time-to-market, Cost reduction, Revenue growth

2. **Strategy Layer** (8 - 15 elements):
   - **Capabilities**: Digital customer experience, Data & Analytics, Cloud infrastructure, API management, DevOps
   - **Value Streams**: Customer onboarding, Order fulfillment, Product innovation
   - **Resources**: Cloud platforms, Data lakes, API gateways, Agile teams

3. **Business Layer** (15 - 30 elements):
   - **Processes**: Current-state vs. Future-state digital processes
   - **Services**: Omnichannel services, Self-service capabilities, Real-time notifications
   - **Actors**: Digital teams, Process owners, Customers (digital-first)
   - **Objects**: Digital assets, Customer profiles, Real-time data

4. **Application Layer** (20 - 40 elements):
   - **Applications to modernize**: Legacy systems → Cloud-native replacements
   - **New digital capabilities**: Mobile apps, Web portals, API layers, Microservices
   - **Integration patterns**: API-first, Event-driven, Real-time streaming
   - **Data architecture**: Operational data stores, Analytics platforms, Data lakes

5. **Technology Layer** (15 - 30 elements):
   - **Cloud infrastructure**: Containers, Kubernetes, Serverless
   - **Data platforms**: Streaming (Kafka), Analytics (Spark), Storage (S3, Data Lake)
   - **Integration middleware**: API gateways, Service mesh, Message brokers
   - **DevOps tooling**: CI/CD pipelines, Monitoring, Observability

6. **Implementation & Migration Layer** (10 - 20 elements):
   - **Workpackages**: "Migrate CRM to cloud", "Build API layer", "Implement analytics platform"
   - **Plateaus**: Current state, Transitional state, Target state
   - **Gaps**: Technology gaps, Skill gaps, Process gaps
   - **Deliverables**: Migration plans, Training programs, Pilot deployments

**Key Relationships to Model:**
- Driver → Goal → Capability → Process → Application → Technology (full traceability)
- Legacy system decommissioning vs. new system adoption
- Data flow from transactional systems → analytics platforms
- APIs serving multiple channels (web, mobile, partners)

Output comprehensive JSON with 80 - 150 elements covering all 6 layers."""


# Cloud Migration Architecture
CLOUD_MIGRATION_PROMPT = """Given this cloud migration project:

{migration_scope}

{context}

Generate a comprehensive ArchiMate 3.2 architecture model for a **CLOUD MIGRATION** project.

**Focus Areas for Cloud Migration:**

1. **Motivation Layer** (12 - 20 elements):
   - **Drivers**: Cost optimization, Scalability, Agility, Disaster recovery, Innovation enablement
   - **Goals**: "Migrate 80% of workloads to cloud by Q4", "Reduce infrastructure costs by 30%", "Improve system availability to 99.99%"
   - **Stakeholders**: CTO, Infrastructure team, Application teams, Finance, Security/Compliance
   - **Constraints**: Data residency requirements, Regulatory compliance, Budget limits, Migration windows
   - **Principles**: Cloud-first, Security by design, Cost optimization, Lift-and-shift vs. Re-architect

2. **Strategy Layer** (8 - 15 elements):
   - **Capabilities**: Cloud operations, Cost management, Security & compliance, Migration execution
   - **Migration strategies**: Rehost (lift-and-shift), Replatform, Refactor, Retain, Retire
   - **Resources**: Cloud credits, Migration tools, Skills/training

3. **Business Layer** (10 - 20 elements):
   - **Impacted processes**: DevOps, Incident management, Capacity planning, Cost allocation
   - **Services**: Infrastructure-as-a-Service, Platform-as-a-Service
   - **Actors**: Cloud architects, DevOps engineers, Application owners

4. **Application Layer** (20 - 50 elements):
   - **Applications by migration wave**:
     - Wave 1: Low-risk, lift-and-shift candidates
     - Wave 2: Applications requiring minor re-platforming
     - Wave 3: Applications requiring re-architecture
     - Wave 4: Decommission candidates
   - **Cloud-native services**: Managed databases, Serverless functions, Container platforms
   - **Data migration**: Database replication, Data sync services

5. **Technology Layer** (20 - 40 elements):
   - **On-premise infrastructure** (source):
     - Physical servers, Storage arrays, Network equipment
   - **Cloud infrastructure** (target):
     - Virtual machines, Managed Kubernetes, Load balancers, Cloud storage, CDN
   - **Migration tools**: Database migration service, Server migration service, Network connectivity (VPN, Direct Connect)
   - **Hybrid connectivity**: Hybrid cloud networking, VPN gateways

6. **Implementation & Migration Layer** (15 - 30 elements):
   - **Workpackages by wave**: "Wave 1: Migrate 20 VMs", "Wave 2: Migrate database cluster"
   - **Plateaus**: On-premise → Hybrid → Cloud-native
   - **Gaps**: Skills gap in cloud technologies, Network bandwidth constraints
   - **Deliverables**: Migration runbooks, Rollback procedures, Performance benchmarks

**Key Migration Patterns:**
- 6R strategy: Rehost, Replatform, Repurchase, Refactor, Retire, Retain
- Dependency mapping: Which apps must move together
- Data gravity: Where data resides influences app placement
- Cost modeling: On-premise TCO vs. Cloud TCO

Output comprehensive JSON with 80 - 150 elements."""


# Application Modernization Architecture
APPLICATION_MODERNIZATION_PROMPT = """Given this application modernization initiative:

{application_details}

{context}

Generate a comprehensive ArchiMate 3.2 architecture model for an **APPLICATION MODERNIZATION** project.

**Focus Areas for Application Modernization:**

1. **Motivation Layer** (10 - 18 elements):
   - **Drivers**: Technical debt, Maintenance costs, Lack of agility, Security vulnerabilities, Performance issues
   - **Goals**: "Replace monolith with microservices", "Adopt cloud-native architecture", "Enable CI/CD deployment"
   - **Stakeholders**: Application development team, Product owners, Operations, Security
   - **Outcomes**: Faster feature delivery, Improved scalability, Reduced downtime

2. **Strategy Layer** (6 - 12 elements):
   - **Capabilities to acquire**: Containerization, Microservices, API-first development, DevOps automation
   - **Modernization approach**: Strangler fig pattern, Big bang migration, Incremental refactoring
   - **Technology choices**: Container platform, Service mesh, API gateway, CI/CD toolchain

3. **Business Layer** (8 - 15 elements):
   - **Business processes** (unchanged but better served)
   - **Services**: Decomposed into granular business services
   - **Actors**: Developers (new skillsets), SRE teams

4. **Application Layer** (25 - 50 elements):
   - **Legacy monolith** (current state):
     - Monolithic application, Tightly-coupled modules, Embedded database
   - **Target microservices** (future state):
     - Customer service, Order service, Payment service, Notification service, etc.
     - API gateway, Service mesh, Event bus
   - **Data architecture**:
     - Database per service pattern
     - Event sourcing, CQRS
     - Data synchronization mechanisms

5. **Technology Layer** (20 - 40 elements):
   - **Legacy infrastructure**: Application servers, Monolithic database
   - **Modern infrastructure**:
     - Kubernetes cluster, Container registry, Service mesh (Istio/Linkerd)
     - Message broker (Kafka, RabbitMQ), API gateway (Kong, Apigee)
     - Observability: Prometheus, Grafana, Jaeger
   - **CI/CD pipeline**: Jenkins/GitLab CI, ArgoCD, Helm

6. **Implementation & Migration Layer** (12 - 25 elements):
   - **Workpackages**: "Extract payment module as microservice", "Implement API gateway", "Deploy service mesh"
   - **Plateaus**:
     - Current: Monolith running on VMs
     - Transitional: Monolith + some microservices (strangler pattern)
     - Target: Full microservices on Kubernetes
   - **Gaps**: Container skills, Distributed tracing knowledge, Cloud-native patterns
   - **Deliverables**: Service design docs, API specifications, Deployment pipelines

**Modernization Patterns:**
- Strangler fig: Incrementally replace monolith
- Database per service: Each microservice owns its data
- API-first: All interactions via well-defined APIs
- Event-driven: Services communicate via events

Output comprehensive JSON with 70 - 140 elements."""


# Enterprise Integration Architecture
ENTERPRISE_INTEGRATION_PROMPT = """Given this enterprise integration initiative:

{integration_requirements}

{context}

Generate a comprehensive ArchiMate 3.2 architecture model for an **ENTERPRISE INTEGRATION** project.

**Focus Areas for Enterprise Integration:**

1. **Motivation Layer** (10 - 18 elements):
   - **Drivers**: System silos, Data inconsistency, Manual data entry, Real-time data needs, Partner integration
   - **Goals**: "Achieve single source of truth", "Enable real-time data sharing", "Automate cross-system workflows"
   - **Stakeholders**: Enterprise architect, Integration team, Business analysts, System owners
   - **Principles**: Loose coupling, API-first, Event-driven, Standards-based

2. **Strategy Layer** (6 - 12 elements):
   - **Capabilities**: System integration, Data integration, Process orchestration, API management
   - **Integration patterns**: Point-to-point, Hub-and-spoke, Enterprise service bus, Microservices mesh
   - **Resources**: Integration platform, API management platform, Data integration tools

3. **Business Layer** (12 - 20 elements):
   - **Cross-system processes**: Order-to-cash, Procure-to-pay, Lead-to-opportunity
   - **Services**: Exposed as APIs for internal/external consumption
   - **Objects**: Canonical data models, Master data entities

4. **Application Layer** (20 - 40 elements):
   - **Source systems**: ERP, CRM, HCM, SCM, Legacy applications
   - **Integration layer**:
     - API gateway, ESB/Integration platform, Message brokers
     - Data transformation services, Orchestration engine
   - **Data synchronization**: ETL/ELT processes, Change data capture, Event streaming
   - **Master data management**: Customer MDM, Product MDM

5. **Technology Layer** (15 - 30 elements):
   - **Integration middleware**: MuleSoft, Dell Boomi, Apache Camel, WSO2
   - **Message brokers**: Kafka, RabbitMQ, ActiveMQ
   - **API management**: Apigee, Kong, AWS API Gateway
   - **Data integration**: Informatica, Talend, Fivetran
   - **Protocols**: REST, SOAP, GraphQL, gRPC, AMQP, MQTT

6. **Implementation & Migration Layer** (10 - 20 elements):
   - **Workpackages**: "Implement API gateway", "Migrate point-to-point to ESB", "Deploy master data hub"
   - **Plateaus**: Point-to-point → ESB-based → API-driven microservices
   - **Gaps**: API design skills, Event-driven patterns knowledge
   - **Deliverables**: Integration architecture standards, API catalog, Data mapping documents

**Integration Patterns:**
- Canonical data model: Single enterprise data model
- Publish-subscribe: Event-driven integration
- Request-reply: Synchronous API calls
- Orchestration vs. Choreography: Centralized vs. decentralized coordination

Output comprehensive JSON with 70 - 130 elements."""


# Data Analytics Platform Architecture
DATA_ANALYTICS_PLATFORM_PROMPT = """Given this data analytics platform initiative:

{analytics_requirements}

{context}

Generate a comprehensive ArchiMate 3.2 architecture model for a **DATA ANALYTICS PLATFORM** project.

**Focus Areas for Data Analytics Platform:**

1. **Motivation Layer** (12 - 20 elements):
   - **Drivers**: Data-driven decision making, Business intelligence needs, Predictive analytics, Self-service analytics
   - **Goals**: "Enable 360 - degree customer view", "Reduce reporting time by 80%", "Empower business users with self-service BI"
   - **Stakeholders**: CDO, Data analysts, Business users, Data engineers, Data scientists
   - **Outcomes**: Faster insights, Better decisions, Increased revenue, Cost optimization

2. **Strategy Layer** (8 - 15 elements):
   - **Capabilities**: Data ingestion, Data storage, Data processing, Data visualization, ML/AI
   - **Data architecture**: Data lake, Data warehouse, Data mart, Lakehouse
   - **Analytics maturity**: Descriptive → Diagnostic → Predictive → Prescriptive

3. **Business Layer** (10 - 18 elements):
   - **Analytical processes**: Customer segmentation, Churn prediction, Sales forecasting, Operational dashboards
   - **Services**: Reporting service, Analytics service, ML model serving
   - **Actors**: Data analysts, Business analysts, Data scientists, Executives

4. **Application Layer** (20 - 45 elements):
   - **Data sources**: Operational databases, SaaS applications, IoT devices, External data feeds
   - **Ingestion layer**: Batch ETL, Real-time streaming, Change data capture
   - **Storage layer**: Data lake (raw), Data warehouse (curated), Data marts (purpose-specific)
   - **Processing layer**: Data transformation, Feature engineering, Model training
   - **Serving layer**: BI tools, Dashboards, API endpoints, Notebooks
   - **ML platform**: Model registry, Experiment tracking, Model serving

5. **Technology Layer** (25 - 50 elements):
   - **Ingestion**: Apache Kafka, Apache NiFi, Fivetran, Airbyte
   - **Storage**: S3/ADLS (data lake), Snowflake/BigQuery/Redshift (warehouse), PostgreSQL (marts)
   - **Processing**: Apache Spark, Databricks, dbt, Apache Airflow (orchestration)
   - **ML/AI**: Sagemaker, Vertex AI, MLflow, Kubeflow
   - **Visualization**: Tableau, Power BI, Looker, Superset
   - **Governance**: Data catalog (Alation, Collibra), Data quality (Great Expectations)

6. **Implementation & Migration Layer** (12 - 25 elements):
   - **Workpackages**: "Build data lake foundation", "Implement streaming pipeline", "Deploy ML platform"
   - **Plateaus**: Siloed reports → Centralized DW → Modern data platform (lake + warehouse)
   - **Gaps**: Data engineering skills, ML expertise, Data governance processes
   - **Deliverables**: Data models, ETL pipelines, Dashboards, ML models

**Data Architecture Patterns:**
- Lambda architecture: Batch + Stream processing
- Kappa architecture: Stream-only processing
- Medallion architecture: Bronze (raw) → Silver (curated) → Gold (aggregated)
- Data mesh: Decentralized domain-oriented data ownership

Output comprehensive JSON with 80 - 150 elements."""


# Scenario detection helper
SCENARIO_PATTERNS = {
    "digital_transformation": [
        "digital transformation",
        "digitalization",
        "customer experience",
        "omnichannel",
        "modernize",
        "innovation",
        "agile",
        "customer-centric",
        "disrupt",
    ],
    "cloud_migration": [
        "cloud migration",
        "migrate to cloud",
        "aws",
        "azure",
        "gcp",
        "lift and shift",
        "cloud-native",
        "hybrid cloud",
        "infrastructure modernization",
    ],
    "application_modernization": [
        "application modernization",
        "monolith",
        "microservices",
        "legacy system",
        "technical debt",
        "refactor",
        "replatform",
        "containerization",
        "kubernetes",
    ],
    "enterprise_integration": [
        "integration",
        "api",
        "esb",
        "middleware",
        "data sync",
        "master data",
        "interoperability",
        "service bus",
        "orchestration",
    ],
    "data_analytics": [
        "analytics",
        "data warehouse",
        "data lake",
        "business intelligence",
        "bi",
        "reporting",
        "dashboard",
        "machine learning",
        "ml",
        "ai",
        "predictive",
    ],
}


def detect_scenario(text: str) -> str:
    """
    Detect which scenario best matches the input text

    Args:
        text: Input text describing the initiative

    Returns:
        Scenario key ('digital_transformation', 'cloud_migration', etc.) or 'general'
    """
    text_lower = text.lower()

    # Weighted scoring: longer/more specific patterns get higher scores
    matches = {}
    for scenario, patterns in SCENARIO_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if pattern in text_lower:
                # Weight by pattern specificity (longer = more specific)
                weight = len(pattern.split())  # Multi-word patterns worth more
                score += weight

        if score > 0:
            matches[scenario] = score

    # Return scenario with highest score, or 'general' if no matches
    if matches:
        return max(matches.items(), key=lambda x: x[1])[0]
    return "general"


def get_scenario_prompt(scenario: str, **kwargs) -> str:
    """
    Get the appropriate prompt template for a scenario

    Args:
        scenario: Scenario key
        **kwargs: Variables to format into the prompt

    Returns:
        Formatted prompt string
    """
    prompts = {
        "digital_transformation": DIGITAL_TRANSFORMATION_PROMPT,
        "cloud_migration": CLOUD_MIGRATION_PROMPT,
        "application_modernization": APPLICATION_MODERNIZATION_PROMPT,
        "enterprise_integration": ENTERPRISE_INTEGRATION_PROMPT,
        "data_analytics": DATA_ANALYTICS_PLATFORM_PROMPT,
        "general": GENERATE_ARCHIMATE_FROM_REQUIREMENTS,
    }

    prompt_template = prompts.get(scenario, GENERATE_ARCHIMATE_FROM_REQUIREMENTS)
    return prompt_template.format(**kwargs)
