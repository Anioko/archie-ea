"""
AI-Powered Risk Analysis Service for ArchiMate 3.2 Motivation Layer

This service provides comprehensive Risk identification and mitigation:
- AI-powered risk identification (technical, organizational, schedule, budget, regulatory)
- Risk scoring using probability × impact matrix
- Mitigation strategy generation
- Risk-to-driver linkage
- Residual risk calculation
- Risk portfolio analysis

ArchiMate 3.2 Compliance:
- Risk is modeled as Assessment element (risk-specific)
- Assessment is a Motivation Layer element
- Assessment can be associated with Drivers, Goals, Capabilities
- Risk mitigation influences Requirements
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from app import db
from app.models import (
    ArchiMateElement,
    ArchiMateRelationship,
    ArchitectureModel,
    BusinessCapability,
    Requirement,
    RiskAssessment,
)
from app.services.llm_service import LLMService


class RiskService:
    """
    AI-powered service for Risk Assessment and mitigation planning.

    Capabilities:
    - Identify technical, organizational, schedule, budget, regulatory risks
    - Score risks using probability × impact matrix (1 - 25 scale)
    - Generate mitigation strategies
    - Calculate residual risk after mitigation
    - Perform risk portfolio analysis
    - Link risks to drivers, goals, capabilities
    """

    def __init__(self):
        self.llm_service = LLMService()

    # ========================================================================
    # Risk Identification Methods
    # ========================================================================

    def identify_technical_risks(
        self, architecture_id: int, technical_context: Optional[str] = None
    ) -> List[RiskAssessment]:
        """
        Identify technical risks using AI.

        Technical Risks:
        - Unproven technology
        - Integration complexity
        - Performance/scalability concerns
        - Technical debt
        - Vendor lock-in
        - Technology obsolescence

        Args:
            architecture_id: ID of the ArchitectureModel
            technical_context: Optional technical architecture description

        Returns:
            List of RiskAssessment instances (risk_type='technical')
        """
        # Get architecture context
        if not technical_context:
            technical_context = self._get_architecture_context(architecture_id)

        prompt = self._build_technical_risk_prompt(technical_context)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            risks_data = json.loads(response)

            risks = []
            for risk_info in risks_data.get("technical_risks", []):
                risk = self._create_risk_assessment(
                    risk_info, architecture_id, risk_type="technical"
                )
                risks.append(risk)

            db.session.commit()
            return risks

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Technical risk identification failed: {str(e)}")

    def identify_organizational_risks(
        self, architecture_id: int, organizational_context: Optional[str] = None
    ) -> List[RiskAssessment]:
        """
        Identify organizational risks using AI.

        Organizational Risks:
        - Skills gap (team lacks required expertise)
        - Resource constraints (insufficient people)
        - Change resistance
        - Organizational silos
        - Leadership support
        - Competing priorities

        Args:
            architecture_id: ID of the ArchitectureModel
            organizational_context: Optional organizational context

        Returns:
            List of RiskAssessment instances (risk_type='organizational')
        """
        prompt = self._build_organizational_risk_prompt(
            organizational_context or "Organization context not provided"
        )

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            risks_data = json.loads(response)

            risks = []
            for risk_info in risks_data.get("organizational_risks", []):
                risk = self._create_risk_assessment(
                    risk_info, architecture_id, risk_type="organizational"
                )
                risks.append(risk)

            db.session.commit()
            return risks

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Organizational risk identification failed: {str(e)}")

    def identify_schedule_risks(
        self, architecture_id: int, project_plan: Optional[str] = None
    ) -> List[RiskAssessment]:
        """
        Identify schedule/timeline risks using AI.

        Schedule Risks:
        - Dependency on external vendors
        - Resource availability conflicts
        - Procurement lead times
        - Integration dependencies
        - Parallel work constraints
        - Regulatory approval delays

        Args:
            architecture_id: ID of the ArchitectureModel
            project_plan: Optional project plan/timeline description

        Returns:
            List of RiskAssessment instances (risk_type='schedule')
        """
        prompt = self._build_schedule_risk_prompt(project_plan or "Project plan not provided")

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            risks_data = json.loads(response)

            risks = []
            for risk_info in risks_data.get("schedule_risks", []):
                risk = self._create_risk_assessment(
                    risk_info, architecture_id, risk_type="schedule"
                )
                risks.append(risk)

            db.session.commit()
            return risks

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Schedule risk identification failed: {str(e)}")

    def identify_all_risks(
        self,
        architecture_id: int,
        business_context: str,
        technical_context: Optional[str] = None,
        organizational_context: Optional[str] = None,
    ) -> List[RiskAssessment]:
        """
        Comprehensive risk identification across all categories.

        Args:
            architecture_id: ID of the ArchitectureModel
            business_context: Overall business/project context
            technical_context: Optional technical details
            organizational_context: Optional organizational details

        Returns:
            List of all RiskAssessment instances across all categories
        """
        prompt = self._build_comprehensive_risk_prompt(
            business_context, technical_context, organizational_context
        )

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            risks_data = json.loads(response)

            all_risks = []
            for risk_info in risks_data.get("risks", []):
                risk = self._create_risk_assessment(
                    risk_info, architecture_id, risk_type=risk_info.get("risk_type", "strategic")
                )
                all_risks.append(risk)

            db.session.commit()
            return all_risks

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Comprehensive risk identification failed: {str(e)}")

    # ========================================================================
    # Mitigation Strategy Methods
    # ========================================================================

    def generate_mitigation_strategy(
        self, risk_id: int, business_context: Optional[str] = None
    ) -> Dict:
        """
        AI-powered mitigation strategy generation.

        Generates:
        - Response strategy (avoid, mitigate, transfer, accept)
        - Specific mitigation actions
        - Contingency plan (Plan B)
        - Cost and effort estimates
        - Residual risk assessment

        Args:
            risk_id: ID of the RiskAssessment
            business_context: Optional additional context

        Returns:
            Dict with mitigation strategy:
            {
                'response_strategy': 'mitigate',
                'mitigation_actions': [...],
                'contingency_plan': '...',
                'estimated_cost': 50000,
                'estimated_effort': 'medium',
                'residual_probability': 2,
                'residual_impact': 3,
                'residual_risk_score': 6,
                'risk_reduction': 68  # %
            }
        """
        risk = db.session.get(RiskAssessment, risk_id)
        if not risk:
            raise ValueError(f"RiskAssessment {risk_id} not found")

        prompt = self._build_mitigation_strategy_prompt(risk, business_context)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            mitigation_data = json.loads(response)

            # Update risk with mitigation strategy
            risk.response_strategy = mitigation_data.get("response_strategy", "mitigate")
            risk.mitigation_strategy = mitigation_data.get("mitigation_strategy")
            risk.contingency_plan = mitigation_data.get("contingency_plan")

            if mitigation_data.get("estimated_cost"):
                risk.mitigation_cost = Decimal(str(mitigation_data["estimated_cost"]))
            risk.mitigation_effort = mitigation_data.get("estimated_effort", "medium")

            # Update residual risk
            risk.residual_probability = mitigation_data.get("residual_probability")
            risk.residual_impact = mitigation_data.get("residual_impact")
            risk.calculate_residual_risk_score()

            risk.status = "analyzed"

            db.session.commit()

            # Add risk reduction percentage
            mitigation_data["risk_reduction"] = risk.risk_reduction_percentage

            return mitigation_data

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Mitigation strategy generation failed: {str(e)}")

    # ========================================================================
    # Risk Linkage Methods
    # ========================================================================

    def link_risk_to_driver(self, risk_id: int, driver_id: int) -> ArchiMateRelationship:
        """
        Link risk to the driver it threatens/relates to.

        Args:
            risk_id: ID of the RiskAssessment
            driver_id: ID of the Driver ArchiMateElement

        Returns:
            Created ArchiMateRelationship
        """
        risk = db.session.get(RiskAssessment, risk_id)
        driver = db.session.get(ArchiMateElement, driver_id)

        if not risk or not driver or driver.type != "Driver":
            raise ValueError("Invalid risk or driver")

        risk.driver_id = driver_id

        # Create association relationship
        relationship = ArchiMateRelationship(
            type="association",
            source_id=risk.archimate_element_id,
            target_id=driver_id,
            architecture_id=risk.architecture_id,
        )
        db.session.add(relationship)
        db.session.commit()

        return relationship

    def link_risk_to_capability(self, risk_id: int, capability_id: int) -> None:
        """
        Link risk to the capability it threatens.

        Args:
            risk_id: ID of the RiskAssessment
            capability_id: ID of the BusinessCapability
        """
        risk = db.session.get(RiskAssessment, risk_id)
        capability = db.session.get(BusinessCapability, capability_id)

        if not risk or not capability:
            raise ValueError("Invalid risk or capability")

        risk.capability_id = capability_id
        db.session.commit()

    # ========================================================================
    # Risk Analysis Methods
    # ========================================================================

    def analyze_risk_portfolio(self, architecture_id: int) -> Dict:
        """
        Analyze entire risk portfolio for an architecture.

        Args:
            architecture_id: ID of the ArchitectureModel

        Returns:
            Dict with portfolio analysis:
            {
                'total_risks': 25,
                'by_risk_level': {'critical': 3, 'high': 8, 'medium': 10, 'low': 4},
                'by_risk_type': {'technical': 9, 'organizational': 7, ...},
                'by_status': {'identified': 5, 'analyzed': 15, 'mitigated': 5},
                'average_risk_score': 12.4,
                'risks_requiring_action': 11,
                'top_risks': [...]
            }
        """
        risks = RiskAssessment.query.filter_by(architecture_id=architecture_id).all()

        if not risks:
            return {"total_risks": 0}

        # Categorize risks
        by_level = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_type = {}
        by_status = {}

        total_score = 0

        for risk in risks:
            # By level
            level = risk.risk_level or "medium"
            by_level[level] = by_level.get(level, 0) + 1

            # By type
            rtype = risk.risk_type or "strategic"
            by_type[rtype] = by_type.get(rtype, 0) + 1

            # By status
            status = risk.status or "identified"
            by_status[status] = by_status.get(status, 0) + 1

            # Score
            if risk.risk_score:
                total_score += risk.risk_score

        avg_score = total_score / len(risks) if risks else 0

        # Risks requiring action (high or critical, not yet mitigated)
        requiring_action = (
            RiskAssessment.query.filter_by(architecture_id=architecture_id)
            .filter(
                RiskAssessment.risk_level.in_(["high", "critical"]),
                RiskAssessment.status.in_(["identified", "analyzed"]),
            )
            .count()
        )

        # Top risks
        top_risks = (
            RiskAssessment.query.filter_by(architecture_id=architecture_id)
            .order_by(RiskAssessment.risk_score.desc())
            .limit(10)
            .all()
        )

        top_risks_data = [
            {
                "risk_id": r.id,
                "name": r.name,
                "risk_type": r.risk_type,
                "risk_level": r.risk_level,
                "risk_score": r.risk_score,
                "status": r.status,
            }
            for r in top_risks
        ]

        return {
            "total_risks": len(risks),
            "by_risk_level": by_level,
            "by_risk_type": by_type,
            "by_status": by_status,
            "average_risk_score": round(avg_score, 1),
            "risks_requiring_action": requiring_action,
            "top_risks": top_risks_data,
        }

    def get_critical_risks(self, architecture_id: int) -> List[RiskAssessment]:
        """
        Get all critical risks requiring immediate attention.

        Args:
            architecture_id: ID of the ArchitectureModel

        Returns:
            List of critical RiskAssessments
        """
        return (
            RiskAssessment.query.filter_by(architecture_id=architecture_id, risk_level="critical")
            .order_by(RiskAssessment.risk_score.desc())
            .all()
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _create_risk_assessment(
        self, risk_info: Dict, architecture_id: int, risk_type: str
    ) -> RiskAssessment:
        """Create RiskAssessment with ArchiMate element."""
        # Create ArchiMate Assessment element
        assessment_element = ArchiMateElement(
            name=risk_info["name"],
            type="Assessment",
            layer="motivation",
            description=risk_info.get("description", ""),
            architecture_id=architecture_id,
        )
        db.session.add(assessment_element)
        db.session.flush()

        # Create RiskAssessment instance
        risk = RiskAssessment(
            name=risk_info["name"],
            description=risk_info.get("description", ""),
            archimate_element_id=assessment_element.id,
            risk_type=risk_type,
            risk_category=risk_info.get("category", "threat"),
            probability=risk_info.get("probability", "medium"),
            probability_score=risk_info.get("probability_score", 3),
            impact=risk_info.get("impact", "medium"),
            impact_score=risk_info.get("impact_score", 3),
            triggers=risk_info.get("triggers"),
            indicators=risk_info.get("indicators"),
            risk_owner=risk_info.get("owner"),
            status="identified",
            identified_date=date.today(),
            architecture_id=architecture_id,
        )

        # Calculate risk score
        risk.calculate_risk_score()

        db.session.add(risk)
        return risk

    def _get_architecture_context(self, architecture_id: int) -> str:
        """Get architecture context from requirements and capabilities."""
        arch = db.session.get(ArchitectureModel, architecture_id)
        if not arch:
            return "No architecture context available"

        requirements = Requirement.query.filter_by(architecture_id=architecture_id).limit(20).all()

        capabilities = (
            BusinessCapability.query.filter_by(architecture_id=architecture_id).limit(10).all()
        )

        context = f"Architecture: {arch.name}\n"
        if arch.description:
            context += f"Description: {arch.description}\n\n"

        if requirements:
            context += "Requirements:\n"
            for req in requirements[:10]:
                context += f"- {req.title}: {req.description[:100]}\n"

        if capabilities:
            context += "\nCapabilities:\n"
            for cap in capabilities[:5]:
                context += f"- {cap.name}: {cap.description[:100]}\n"

        return context

    # ========================================================================
    # Prompt Building Methods
    # ========================================================================

    def _build_technical_risk_prompt(self, technical_context: str) -> str:
        """Build technical risk identification prompt."""
        return f"""You are a technical risk analyst and enterprise architect.

Analyze this technical architecture and identify TECHNICAL RISKS.

Technical Context:
{technical_context}

Identify risks in these categories:

1. **Unproven Technology**: New/immature tech with limited production track record
2. **Integration Complexity**: Complex integrations, API dependencies, data synchronization
3. **Performance/Scalability**: Performance bottlenecks, scalability limits, concurrency issues
4. **Technical Debt**: Legacy code, outdated frameworks, maintenance burden
5. **Vendor Lock-in**: Proprietary solutions limiting future flexibility
6. **Technology Obsolescence**: Technologies approaching end-of-life

For each risk:
- name: Concise risk name
- description: What could go wrong
- category: 'threat' (negative risk)
- probability: very_low | low | medium | high | very_high
- probability_score: 1 - 5
- impact: negligible | low | medium | high | critical
- impact_score: 1 - 5
- triggers: What events would cause this risk to materialize
- indicators: Early warning signs
- owner: Who should own this risk (e.g., "CTO", "Lead Architect")

Return JSON:
{{
  "technical_risks": [
    {{
      "name": "Python Microservices Skills Gap",
      "description": "Team lacks Python expertise but architecture requires 10 Python microservices",
      "category": "threat",
      "probability": "high",
      "probability_score": 4,
      "impact": "high",
      "impact_score": 4,
      "triggers": "Project starts implementation without training or hiring",
      "indicators": "Slow development velocity, code quality issues, high defect rates",
      "owner": "CTO"
    }},
    {{
      "name": "Third-Party API Dependency Risk",
      "description": "Critical dependency on external vendor API with no SLA",
      "category": "threat",
      "probability": "medium",
      "probability_score": 3,
      "impact": "critical",
      "impact_score": 5,
      "triggers": "API downtime, breaking changes, rate limiting",
      "indicators": "API response time degradation, error rate increases",
      "owner": "Lead Architect"
    }}
  ]
}}

Focus on realistic, evidence-based risks from the technical context.
"""

    def _build_organizational_risk_prompt(self, organizational_context: str) -> str:
        """Build organizational risk prompt."""
        return f"""You are an organizational change and risk analyst.

Identify ORGANIZATIONAL RISKS that could impact project success.

Organizational Context:
{organizational_context}

Risk Categories:

1. **Skills Gap**: Team lacks required expertise
2. **Resource Constraints**: Insufficient people, competing priorities
3. **Change Resistance**: Stakeholders resistant to change
4. **Organizational Silos**: Lack of collaboration between departments
5. **Leadership Support**: Insufficient executive sponsorship
6. **Competing Priorities**: Other initiatives draining resources

For each risk, provide:
- name, description, category='threat'
- probability, probability_score (1 - 5)
- impact, impact_score (1 - 5)
- triggers, indicators
- owner

Return JSON with organizational_risks array.

Example:
{{
  "organizational_risks": [
    {{
      "name": "Insufficient Java Developer Resources",
      "description": "Only 2 Java developers available, need 5 for project timeline",
      "category": "threat",
      "probability": "high",
      "probability_score": 4,
      "impact": "high",
      "impact_score": 4,
      "triggers": "Project kickoff without additional hiring",
      "indicators": "Sprint velocity below target, overtime hours increasing",
      "owner": "Engineering Manager"
    }}
  ]
}}
"""

    def _build_schedule_risk_prompt(self, project_plan: str) -> str:
        """Build schedule risk prompt."""
        return f"""Identify SCHEDULE/TIMELINE RISKS.

Project Plan:
{project_plan}

Risk Categories:

1. **External Vendor Dependencies**: Delays from third parties
2. **Resource Availability**: Key people unavailable when needed
3. **Procurement Lead Times**: Long procurement cycles (RFP, security review)
4. **Integration Dependencies**: Can't start until dependencies complete
5. **Regulatory Approvals**: Government/regulatory approval delays
6. **Parallel Work Constraints**: Limited parallelization opportunities

For each risk:
- name, description, category='threat'
- probability, probability_score (1 - 5)
- impact, impact_score (1 - 5)
- triggers, indicators
- owner

Return JSON with schedule_risks array.
"""

    def _build_comprehensive_risk_prompt(
        self,
        business_context: str,
        technical_context: Optional[str],
        organizational_context: Optional[str],
    ) -> str:
        """Build comprehensive risk identification prompt."""
        tech_section = f"\n\nTechnical Context:\n{technical_context}" if technical_context else ""
        org_section = (
            f"\n\nOrganizational Context:\n{organizational_context}"
            if organizational_context
            else ""
        )

        return f"""You are a comprehensive risk analyst. Identify ALL significant risks across all categories.

Business Context:
{business_context}
{tech_section}
{org_section}

Risk Categories:
- technical: Technology, architecture, integration risks
- organizational: People, skills, change management
- schedule: Timeline, dependencies, procurement
- budget: Cost overruns, unexpected expenses
- regulatory: Compliance failures, legal challenges
- operational: Operations, support, maintenance
- strategic: Market changes, competitive threats

For each risk:
- name, description, risk_type (from categories above), category='threat'
- probability, probability_score (1 - 5)
- impact, impact_score (1 - 5)
- triggers, indicators
- owner

Return JSON:
{{
  "risks": [
    {{
      "name": "GDPR Compliance Failure",
      "description": "Fail to implement GDPR requirements by deadline",
      "risk_type": "regulatory",
      "category": "threat",
      "probability": "medium",
      "probability_score": 3,
      "impact": "critical",
      "impact_score": 5,
      "triggers": "Incomplete data mapping, missing consent mechanisms",
      "indicators": "Data protection assessment not complete, legal review delayed",
      "owner": "Chief Compliance Officer"
    }}
  ]
}}

Identify 8 - 12 most significant risks.
"""

    def _build_mitigation_strategy_prompt(
        self, risk: RiskAssessment, business_context: Optional[str]
    ) -> str:
        """Build mitigation strategy prompt."""
        context_section = f"\n\nBusiness Context:\n{business_context}" if business_context else ""

        return f"""You are a risk management expert. Generate mitigation strategy for this risk.

Risk:
Name: {risk.name}
Description: {risk.description}
Type: {risk.risk_type}
Probability: {risk.probability} (Score: {risk.probability_score}/5)
Impact: {risk.impact} (Score: {risk.impact_score}/5)
Risk Score: {risk.risk_score}/25
Risk Level: {risk.risk_level}
{context_section}

Generate comprehensive mitigation strategy:

1. **Response Strategy**: Choose one:
   - avoid: Eliminate the risk entirely
   - mitigate: Reduce probability or impact
   - transfer: Shift risk to third party (insurance, outsourcing)
   - accept: Acknowledge and monitor

2. **Mitigation Actions**: 3 - 5 specific actions to reduce risk

3. **Contingency Plan**: Plan B if risk materializes

4. **Cost & Effort**:
   - estimated_cost: Numeric value (€/$ amount)
   - estimated_effort: low | medium | high

5. **Residual Risk** (after mitigation):
   - residual_probability: 1 - 5
   - residual_impact: 1 - 5

Return JSON:
{{
  "response_strategy": "mitigate",
  "mitigation_strategy": "Hire 2 experienced Python developers immediately. Provide intensive Python training to existing Java team. Start with pilot microservice to build expertise before scaling.",
  "mitigation_actions": [
    "Post job openings for senior Python developers (2 weeks)",
    "Enroll 4 Java developers in Python bootcamp (1 month)",
    "Implement pilot microservice as learning project (2 months)",
    "Pair programming: new Python devs mentor Java team",
    "Code review process with Python best practices checklist"
  ],
  "contingency_plan": "If Python expertise not acquired in 3 months, pivot architecture to Java microservices which team knows well. Accept 2 - month schedule delay for re-architecture.",
  "estimated_cost": 150000,
  "estimated_effort": "high",
  "residual_probability": 2,
  "residual_impact": 3
}}

Provide realistic, actionable mitigation strategies.
"""
