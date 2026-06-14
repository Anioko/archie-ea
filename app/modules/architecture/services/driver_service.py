"""
AI-Powered Driver Analysis Service for ArchiMate 3.2 Motivation Layer

This service provides comprehensive Driver identification, extraction, and analysis:
- External driver detection (regulatory, competitive, market, technology)
- Internal driver extraction (cost reduction, digital transformation, M&A)
- Driver criticality assessment (urgency, impact, deadlines)
- Driver-to-requirement linkage
- Driver hierarchy and relationships

ArchiMate 3.2 Compliance:
- Driver is a Motivation Layer element
- Represents external or internal condition motivating organization
- Can influence/trigger Goals
- Can be associated with Requirements
- Can be assessed via Assessment elements
"""

import json
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from app import db
from app.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel, Requirement
from app.services.llm_service import LLMService


class DriverService:
    """
    AI-powered service for ArchiMate 3.2 Driver element extraction and analysis.

    Capabilities:
    - Extract regulatory/compliance drivers (GDPR, SOX, HIPAA, PCI-DSS)
    - Identify market/competitive drivers
    - Detect internal strategic drivers
    - Assess driver criticality and urgency
    - Link drivers to requirements and goals
    """

    def __init__(self):
        self.llm_service = LLMService()

    # ========================================================================
    # Driver Extraction Methods
    # ========================================================================

    def extract_drivers_from_context(
        self,
        business_context: str,
        architecture_id: int,
        industry: Optional[str] = None,
        region: Optional[str] = None,
    ) -> List[ArchiMateElement]:
        """
        Extract all types of drivers from business context using AI.

        This method uses LLM to identify:
        - External drivers (regulatory, market, competitive, technology)
        - Internal drivers (strategic, operational, financial)

        Args:
            business_context: Text describing business situation/needs
            architecture_id: ID of the ArchitectureModel
            industry: Optional industry context (manufacturing, finance, healthcare, etc.)
            region: Optional geographic region (EU, US, APAC, etc.)

        Returns:
            List of ArchiMateElement instances (type='Driver', layer='motivation')

        Example:
            >>> context = '''
            ... The organization must comply with GDPR by Q2 2026.
            ... Competitors are launching AI-powered features.
            ... Executive mandate to reduce operational costs by 20%.
            ... '''
            >>> drivers = service.extract_drivers_from_context(context, arch_id=1, industry='finance', region='EU')
            >>> # Returns 3 drivers: GDPR compliance, competitive pressure, cost reduction
        """
        prompt = self._build_driver_extraction_prompt(business_context, industry, region)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            drivers_data = json.loads(response)

            if not isinstance(drivers_data, dict) or "drivers" not in drivers_data:
                raise ValueError("Invalid response format from LLM")

            drivers = []
            for driver_info in drivers_data["drivers"]:
                driver_element = self._create_driver_element(driver_info, architecture_id)
                drivers.append(driver_element)

            db.session.commit()
            return drivers

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Driver extraction failed: {str(e)}")

    def extract_regulatory_drivers(
        self, business_context: str, architecture_id: int, regulations: Optional[List[str]] = None
    ) -> List[ArchiMateElement]:
        """
        Extract regulatory and compliance drivers using AI.

        Identifies mentions of:
        - GDPR, CCPA (data privacy)
        - SOX, IFRS (financial reporting)
        - HIPAA, HITECH (healthcare)
        - PCI-DSS (payment security)
        - Industry-specific regulations

        Args:
            business_context: Text to analyze
            architecture_id: ID of the ArchitectureModel
            regulations: Optional list of specific regulations to check for

        Returns:
            List of Driver elements with regulatory focus
        """
        prompt = self._build_regulatory_driver_prompt(business_context, regulations)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            drivers_data = json.loads(response)

            drivers = []
            for driver_info in drivers_data.get("regulatory_drivers", []):
                driver_element = self._create_driver_element(
                    driver_info,
                    architecture_id,
                    driver_source="external",
                    driver_category="regulatory",
                )
                drivers.append(driver_element)

            db.session.commit()
            return drivers

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Regulatory driver extraction failed: {str(e)}")

    def extract_internal_drivers(
        self, strategic_docs: str, architecture_id: int
    ) -> List[ArchiMateElement]:
        """
        Extract internal strategic drivers from organizational documents.

        Identifies:
        - Cost reduction mandates
        - Digital transformation initiatives
        - M&A activity
        - Organizational restructuring
        - Strategic pivots

        Args:
            strategic_docs: Strategic planning documents, executive communications
            architecture_id: ID of the ArchitectureModel

        Returns:
            List of internal Driver elements
        """
        prompt = self._build_internal_driver_prompt(strategic_docs)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            drivers_data = json.loads(response)

            drivers = []
            for driver_info in drivers_data.get("internal_drivers", []):
                driver_element = self._create_driver_element(
                    driver_info,
                    architecture_id,
                    driver_source="internal",
                    driver_category=driver_info.get("category", "strategic"),
                )
                drivers.append(driver_element)

            db.session.commit()
            return drivers

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Internal driver extraction failed: {str(e)}")

    # ========================================================================
    # Driver Assessment Methods
    # ========================================================================

    def assess_driver_criticality(
        self, driver_id: int, business_context: Optional[str] = None
    ) -> Dict:
        """
        AI-powered assessment of driver criticality and urgency.

        Analyzes:
        - Urgency (1 - 10 scale)
        - Impact radius (which capabilities/processes affected)
        - Hard deadline vs aspirational
        - Risk of non-compliance/non-response
        - Priority classification (critical, high, medium, low)

        Args:
            driver_id: ID of the Driver ArchiMateElement
            business_context: Optional additional context

        Returns:
            Dict with assessment results:
            {
                'urgency_score': 8,
                'impact_level': 'high',
                'has_hard_deadline': True,
                'deadline_date': '2026 - 05 - 25',
                'priority': 'critical',
                'affected_capabilities': [...],
                'consequences': 'GDPR fines up to 4% revenue',
                'recommendation': 'Immediate action required'
            }
        """
        driver = db.session.get(ArchiMateElement, driver_id)
        if not driver or driver.type != "Driver":
            raise ValueError(f"Driver {driver_id} not found or not a Driver element")

        prompt = self._build_criticality_assessment_prompt(driver, business_context)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            assessment = json.loads(response)

            # Update driver properties with assessment results
            props = json.loads(driver.properties) if driver.properties else {}
            props["criticality_assessment"] = assessment
            props["urgency_score"] = assessment.get("urgency_score")
            props["assessed_at"] = datetime.utcnow().isoformat()

            driver.properties = json.dumps(props)
            driver.priority = self._map_urgency_to_priority(assessment.get("urgency_score", 5))

            db.session.commit()

            return assessment

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Criticality assessment failed: {str(e)}")

    # ========================================================================
    # Driver Linking Methods
    # ========================================================================

    def link_drivers_to_requirements(
        self, driver_id: int, requirements: Optional[List[int]] = None
    ) -> List[Requirement]:
        """
        Link driver to requirements it influences.

        If requirements not specified, uses AI to find semantically related requirements.
        Creates ArchiMate 'influence' relationships.

        Args:
            driver_id: ID of the Driver ArchiMateElement
            requirements: Optional list of Requirement IDs to link

        Returns:
            List of linked Requirement instances
        """
        driver = db.session.get(ArchiMateElement, driver_id)
        if not driver or driver.type != "Driver":
            raise ValueError(f"Driver {driver_id} not found")

        if requirements:
            # Explicit linking
            linked_reqs = []
            for req_id in requirements:
                req = db.session.get(Requirement, req_id)
                if req:
                    req.driver_id = driver_id
                    linked_reqs.append(req)

                    # Create ArchiMate relationship
                    self._create_relationship(
                        driver_id, req.archimate_element_id, "influence", driver.architecture_id
                    )

            db.session.commit()
            return linked_reqs
        else:
            # AI-powered semantic linking
            return self._auto_link_driver_to_requirements(driver)

    def link_driver_to_goal(
        self, driver_id: int, goal_id: int, relationship_type: str = "influence"
    ) -> ArchiMateRelationship:
        """
        Link a driver to a goal it triggers or influences.

        Args:
            driver_id: ID of the Driver ArchiMateElement
            goal_id: ID of the Goal ArchiMateElement
            relationship_type: 'influence' or 'triggering'

        Returns:
            Created ArchiMateRelationship
        """
        driver = db.session.get(ArchiMateElement, driver_id)
        goal = db.session.get(ArchiMateElement, goal_id)

        if not driver or driver.type != "Driver":
            raise ValueError(f"Invalid driver {driver_id}")
        if not goal or goal.type != "Goal":
            raise ValueError(f"Invalid goal {goal_id}")

        relationship = self._create_relationship(
            driver_id, goal_id, relationship_type, driver.architecture_id
        )

        db.session.commit()
        return relationship

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _create_driver_element(
        self,
        driver_info: Dict,
        architecture_id: int,
        driver_source: Optional[str] = None,
        driver_category: Optional[str] = None,
    ) -> ArchiMateElement:
        """Create ArchiMateElement for a driver."""
        properties = {
            "source": driver_source or driver_info.get("source", "unknown"),
            "category": driver_category or driver_info.get("category"),
            "urgency": driver_info.get("urgency"),
            "deadline": driver_info.get("deadline"),
            "impact": driver_info.get("impact"),
            "consequence": driver_info.get("consequence"),
            "extracted_at": datetime.utcnow().isoformat(),
        }

        driver = ArchiMateElement(
            name=driver_info["name"],
            type="Driver",
            layer="motivation",
            description=driver_info.get("description", ""),
            documentation=driver_info.get("details", ""),
            properties=json.dumps(properties),
            priority=driver_info.get("priority", "medium"),
            status="identified",
            architecture_id=architecture_id,
        )

        db.session.add(driver)
        return driver

    def _create_relationship(
        self, source_id: int, target_id: int, rel_type: str, architecture_id: int
    ) -> ArchiMateRelationship:
        """Create ArchiMate relationship."""
        relationship = ArchiMateRelationship(
            type=rel_type, source_id=source_id, target_id=target_id, architecture_id=architecture_id
        )
        db.session.add(relationship)
        return relationship

    def _auto_link_driver_to_requirements(self, driver: ArchiMateElement) -> List[Requirement]:
        """Use AI to automatically link driver to relevant requirements."""
        # Get all requirements in the same architecture
        requirements = Requirement.query.filter_by(architecture_id=driver.architecture_id).all()

        if not requirements:
            return []

        # Build prompt for AI linking
        prompt = self._build_driver_linking_prompt(driver, requirements)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            linking_data = json.loads(response)

            linked_reqs = []
            for link in linking_data.get("links", []):
                req_id = link["requirement_id"]
                req = db.session.get(Requirement, req_id)
                if req:
                    req.driver_id = driver.id
                    linked_reqs.append(req)

                    if req.archimate_element_id:
                        self._create_relationship(
                            driver.id, req.archimate_element_id, "influence", driver.architecture_id
                        )

            db.session.commit()
            return linked_reqs

        except Exception as e:
            db.session.rollback()
            return []

    def _map_urgency_to_priority(self, urgency_score: int) -> str:
        """Map urgency score (1 - 10) to priority level."""
        if urgency_score >= 9:
            return "critical"
        elif urgency_score >= 7:
            return "high"
        elif urgency_score >= 4:
            return "medium"
        else:
            return "low"

    # ========================================================================
    # Prompt Building Methods
    # ========================================================================

    def _build_driver_extraction_prompt(
        self, business_context: str, industry: Optional[str], region: Optional[str]
    ) -> str:
        """Build comprehensive driver extraction prompt."""
        return f"""You are an expert business analyst and enterprise architect specializing in ArchiMate 3.2 Motivation Layer.

Analyze the following business context and extract ALL business drivers (external and internal conditions motivating the organization).

Business Context:
{business_context}

Industry: {industry or 'Not specified'}
Region: {region or 'Global'}

Extract the following types of drivers:

**External Drivers:**
1. **Regulatory/Compliance**: GDPR, SOX, HIPAA, PCI-DSS, industry-specific regulations
2. **Market/Competitive**: Market disruption, competitor actions, customer demand shifts
3. **Technology**: Emerging technologies, platform shifts, obsolescence
4. **Economic**: Economic downturn/growth, currency fluctuations, inflation

**Internal Drivers:**
5. **Strategic**: Digital transformation, market expansion, new business models
6. **Financial**: Cost reduction mandates, revenue growth targets, profitability goals
7. **Organizational**: M&A activity, restructuring, leadership changes
8. **Operational**: Process improvement, quality enhancement, risk mitigation

For each driver, identify:
- Name (concise, 5 - 10 words)
- Description (1 - 2 sentences)
- Source: 'external' or 'internal'
- Category: regulatory, competitive, market, technology, strategic, financial, organizational, operational
- Urgency: 'critical', 'high', 'medium', 'low'
- Deadline: Specific date if mentioned (YYYY-MM-DD), 'ongoing', or 'not_specified'
- Impact: Which business areas are affected
- Consequence: What happens if driver is not addressed
- Priority: 'critical', 'high', 'medium', 'low'

Return JSON:
{{
  "drivers": [
    {{
      "name": "GDPR Compliance Mandate",
      "description": "Organization must comply with GDPR data privacy regulations",
      "source": "external",
      "category": "regulatory",
      "urgency": "critical",
      "deadline": "2026 - 05 - 25",
      "impact": "All systems processing EU citizen data",
      "consequence": "Fines up to 4% of annual revenue, legal liability, reputational damage",
      "priority": "critical",
      "details": "GDPR requires data protection by design, consent management, right to erasure, data portability"
    }}
  ]
}}

IMPORTANT:
- Only extract drivers explicitly stated or strongly implied in the context
- Do NOT invent drivers not supported by the text
- Classify urgency based on keywords: "must", "mandatory", "deadline" = critical/high
- If deadline is mentioned, extract the date
- If industry/region provided, consider industry-specific regulations (e.g., HIPAA for healthcare)
"""

    def _build_regulatory_driver_prompt(
        self, business_context: str, regulations: Optional[List[str]]
    ) -> str:
        """Build regulatory-specific driver extraction prompt."""
        regs_list = regulations or [
            "GDPR",
            "CCPA",
            "SOX",
            "HIPAA",
            "PCI-DSS",
            "IFRS",
            "Basel III",
            "MiFID II",
            "Dodd-Frank",
        ]

        return f"""You are a regulatory compliance expert and enterprise architect.

Analyze the business context and identify all REGULATORY and COMPLIANCE drivers.

Business Context:
{business_context}

Focus on these regulations:
{', '.join(regs_list)}

For each regulatory driver found:
1. Identify the regulation/standard
2. Determine compliance deadline (if specified)
3. Assess criticality (regulatory deadlines are typically "critical")
4. Identify penalties for non-compliance
5. List affected business areas
6. Specify compliance requirements

Return JSON:
{{
  "regulatory_drivers": [
    {{
      "name": "GDPR Data Privacy Compliance",
      "description": "Comply with EU General Data Protection Regulation",
      "regulation": "GDPR",
      "source": "external",
      "category": "regulatory",
      "urgency": "critical",
      "deadline": "2026 - 05 - 25",
      "penalties": "Fines up to €20M or 4% annual revenue, whichever is higher",
      "affected_areas": ["Customer data systems", "HR systems", "Marketing platforms"],
      "requirements": ["Consent management", "Data protection by design", "Right to erasure", "Data portability", "Breach notification <72hrs"],
      "priority": "critical"
    }}
  ]
}}

Only extract regulatory drivers with clear evidence in the text.
"""

    def _build_internal_driver_prompt(self, strategic_docs: str) -> str:
        """Build internal driver extraction prompt."""
        return f"""You are a strategic business analyst and enterprise architect.

Analyze internal strategic documents and extract INTERNAL DRIVERS (organizational conditions motivating change).

Strategic Documents:
{strategic_docs}

Identify internal drivers in these categories:

1. **Strategic Drivers**: Digital transformation, cloud migration, AI adoption, market expansion
2. **Financial Drivers**: Cost reduction targets, revenue growth goals, margin improvement
3. **Organizational Drivers**: M&A integration, restructuring, culture change
4. **Operational Drivers**: Process automation, quality improvement, efficiency gains
5. **Risk/Compliance Drivers**: Risk reduction, audit findings, internal control improvements

For each driver:
- Name: Clear, actionable statement
- Category: strategic, financial, organizational, operational, risk
- Target: Specific measurable target if mentioned (e.g., "reduce costs 20%")
- Timeline: When this must be achieved
- Sponsor: Executive sponsor if mentioned (CEO, CFO, CTO, etc.)
- Rationale: Why this driver exists
- Impact: Business areas affected

Return JSON:
{{
  "internal_drivers": [
    {{
      "name": "Operational Cost Reduction Initiative",
      "description": "Reduce operational costs by 20% through automation and process optimization",
      "category": "financial",
      "source": "internal",
      "target": "20% cost reduction",
      "timeline": "By end of FY2026",
      "sponsor": "CFO",
      "rationale": "Improve profitability margins to remain competitive",
      "impact": "IT operations, customer service, back-office processes",
      "urgency": "high",
      "priority": "high"
    }}
  ]
}}

Extract only drivers clearly stated in the documents.
"""

    def _build_criticality_assessment_prompt(
        self, driver: ArchiMateElement, business_context: Optional[str]
    ) -> str:
        """Build driver criticality assessment prompt."""
        return f"""You are an enterprise risk and impact analyst.

Assess the criticality and urgency of this business driver:

**Driver:**
Name: {driver.name}
Description: {driver.description}
Current Priority: {driver.priority}

**Additional Context:**
{business_context or 'No additional context provided'}

Assess the following:

1. **Urgency Score** (1 - 10):
   - 10 = Hard regulatory deadline within 6 months, critical consequences
   - 7 - 9 = High urgency, significant business impact
   - 4 - 6 = Medium urgency, moderate impact
   - 1 - 3 = Low urgency, minor impact

2. **Impact Level**: critical, high, medium, low
   - How many business processes/capabilities affected?
   - Revenue/cost impact?
   - Customer/stakeholder impact?

3. **Deadline Type**:
   - hard_deadline: Regulatory/contractual, cannot be moved
   - soft_deadline: Internal target, some flexibility
   - no_deadline: Ongoing/strategic

4. **Consequences** if not addressed

5. **Affected Capabilities**: Which business capabilities must respond?

6. **Recommendation**: immediate_action, plan_within_month, plan_within_quarter, monitor

Return JSON:
{{
  "urgency_score": 8,
  "impact_level": "high",
  "has_hard_deadline": true,
  "deadline_date": "2026 - 05 - 25",
  "deadline_type": "hard_deadline",
  "priority": "critical",
  "affected_capabilities": ["Customer Data Management", "Privacy Management", "Consent Management"],
  "business_impact": "All EU customer-facing systems must be compliant",
  "financial_impact": "Potential fines €20M or 4% revenue",
  "consequences": "GDPR non-compliance: massive fines, legal liability, reputational damage, loss of EU market access",
  "recommendation": "immediate_action",
  "reasoning": "Hard regulatory deadline with severe financial and legal consequences"
}}
"""

    def _build_driver_linking_prompt(
        self, driver: ArchiMateElement, requirements: List[Requirement]
    ) -> str:
        """Build prompt for AI-powered driver-to-requirement linking."""
        req_list = "\n".join(
            [
                f"ID: {req.id}, Title: {req.title or req.category}, Description: {req.description[:100]}"
                for req in requirements[:50]  # Limit to prevent token overflow
            ]
        )

        return f"""You are an enterprise architect specializing in traceability analysis.

Link this business driver to relevant requirements it influences.

**Driver:**
Name: {driver.name}
Description: {driver.description}
Properties: {driver.properties}

**Available Requirements:**
{req_list}

Identify which requirements are influenced by this driver. A driver influences a requirement if:
- The requirement addresses/responds to the driver
- The requirement helps satisfy compliance mandated by the driver
- The requirement mitigates risks from the driver
- The requirement achieves outcomes motivated by the driver

For each link, provide:
- requirement_id
- linkage_strength: 'strong', 'medium', 'weak'
- rationale: Why they're linked

Return JSON:
{{
  "links": [
    {{
      "requirement_id": 42,
      "linkage_strength": "strong",
      "rationale": "This requirement directly implements GDPR data protection controls required by the regulatory driver"
    }}
  ]
}}

Only link requirements with clear semantic relationship to the driver.
"""
