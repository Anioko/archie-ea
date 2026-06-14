"""
AI-Powered Principle Management Service for ArchiMate 3.2 Motivation Layer

This service provides comprehensive Principle modeling and enforcement:
- Principle extraction from policy documents
- Requirement derivation from principles
- Principle-requirement conflict detection
- Principle compliance validation
- Principle hierarchy management

ArchiMate 3.2 Compliance:
- Principle is a Motivation Layer element
- Principle constrains Requirements
- Principle guides architectural decisions
- Principle can be assessed for compliance
"""

import json
import re
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from app import db
from app.models import (
    ArchiMateElement,
    ArchiMateRelationship,
    ArchitectureModel,
    Principle,
    Requirement,
)
from app.services.llm_service import LLMService


class PrincipleService:
    """
    AI-powered service for ArchiMate 3.2 Principle element management.

    Capabilities:
    - Extract principles from policy/governance documents
    - Derive requirements from principles
    - Validate requirements against principles
    - Detect principle conflicts
    - Enforce principle compliance
    """

    def __init__(self):
        self.llm_service = LLMService()

    # ========================================================================
    # Principle Extraction Methods
    # ========================================================================

    def extract_principles_from_policy(
        self, policy_docs: str, architecture_id: int, policy_source: Optional[str] = None
    ) -> List[Principle]:
        """
        Extract architectural principles from policy/governance documents.

        Identifies normative statements (MUST, SHOULD, MAY) that constrain
        architecture and implementation choices.

        Args:
            policy_docs: Policy/governance document text
            architecture_id: ID of the ArchitectureModel
            policy_source: Optional source identifier (e.g., "Enterprise Architecture Policy v2.1")

        Returns:
            List of Principle instances

        Example:
            >>> policy = '''
            ... All customer data MUST be encrypted at rest using AES - 256.
            ... Cloud-first strategy: New applications SHOULD use cloud services.
            ... Open source SHOULD be preferred over proprietary solutions.
            ... '''
            >>> principles = service.extract_principles_from_policy(policy, arch_id=1)
            >>> # Returns 3 principles with enforcement levels
        """
        prompt = self._build_principle_extraction_prompt(policy_docs, policy_source)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            principles_data = json.loads(response)

            if not isinstance(principles_data, dict) or "principles" not in principles_data:
                raise ValueError("Invalid response format from LLM")

            principles = []
            for principle_info in principles_data["principles"]:
                principle = self._create_principle(principle_info, architecture_id, policy_source)
                principles.append(principle)

            db.session.commit()
            return principles

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Principle extraction failed: {str(e)}")

    def extract_principles_by_category(
        self, policy_docs: str, architecture_id: int, categories: Optional[List[str]] = None
    ) -> Dict[str, List[Principle]]:
        """
        Extract principles organized by category.

        Categories: Security, Data, Integration, Technology, Business, Architecture

        Args:
            policy_docs: Policy document text
            architecture_id: ID of the ArchitectureModel
            categories: Optional list of categories to extract

        Returns:
            Dict mapping category to list of Principles
        """
        all_categories = categories or [
            "Security",
            "Data",
            "Integration",
            "Technology",
            "Business",
            "Architecture",
        ]

        prompt = self._build_categorized_extraction_prompt(policy_docs, all_categories)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            categorized_data = json.loads(response)

            results = {}
            for category, principles_list in categorized_data.items():
                if category == "principles":
                    # Flat list format
                    for principle_info in principles_list:
                        cat = principle_info.get("category", "Architecture")
                        if cat not in results:
                            results[cat] = []

                        principle = self._create_principle(principle_info, architecture_id)
                        results[cat].append(principle)
                else:
                    # Categorized format
                    results[category] = []
                    for principle_info in principles_list:
                        principle = self._create_principle(principle_info, architecture_id)
                        results[category].append(principle)

            db.session.commit()
            return results

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Categorized principle extraction failed: {str(e)}")

    # ========================================================================
    # Requirement Derivation Methods
    # ========================================================================

    def derive_requirements_from_principle(
        self, principle_id: int, business_context: Optional[str] = None
    ) -> List[Requirement]:
        """
        Derive specific requirements from a principle.

        A principle is normative (states what SHOULD be), requirements are
        specific implementations of that principle.

        Args:
            principle_id: ID of the Principle
            business_context: Optional context for requirement generation

        Returns:
            List of Requirement instances derived from principle

        Example:
            >>> # Principle: "All data MUST be encrypted at rest"
            >>> reqs = service.derive_requirements_from_principle(principle_id=3)
            >>> # Requirements:
            >>> # - Database encryption using TLS 1.3+ for all databases
            >>> # - File storage using AES - 256 encryption
            >>> # - Key management via HSM or cloud KMS
        """
        principle = db.session.get(Principle, principle_id)
        if not principle:
            raise ValueError(f"Principle {principle_id} not found")

        prompt = self._build_requirement_derivation_prompt(principle, business_context)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            requirements_data = json.loads(response)

            requirements = []
            for req_info in requirements_data.get("requirements", []):
                requirement = self._create_requirement_from_principle(
                    req_info, principle, principle.architecture_id
                )
                requirements.append(requirement)

            db.session.commit()
            return requirements

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Requirement derivation failed: {str(e)}")

    # ========================================================================
    # Principle Compliance Methods
    # ========================================================================

    def validate_requirement_against_principles(
        self, requirement_id: int, principle_ids: Optional[List[int]] = None
    ) -> Dict:
        """
        Validate if a requirement complies with principles.

        Args:
            requirement_id: ID of the Requirement to validate
            principle_ids: Optional specific principles to check (if None, checks all)

        Returns:
            Dict with validation results:
            {
                'compliant': False,
                'violations': [
                    {
                        'principle_id': 5,
                        'principle_name': 'Cloud-first strategy',
                        'severity': 'high',
                        'violation': 'Requirement specifies on-premises deployment',
                        'recommendation': 'Revise to use cloud services'
                    }
                ],
                'warnings': [...],
                'compliance_score': 60  # % of principles satisfied
            }
        """
        requirement = db.session.get(Requirement, requirement_id)
        if not requirement:
            raise ValueError(f"Requirement {requirement_id} not found")

        # Get principles to check
        if principle_ids:
            principles = Principle.query.filter(Principle.id.in_(principle_ids)).all()
        else:
            principles = Principle.query.filter_by(
                architecture_id=requirement.architecture_id, status="approved"
            ).all()

        if not principles:
            return {"compliant": True, "violations": [], "warnings": []}

        prompt = self._build_compliance_validation_prompt(requirement, principles)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            validation_result = json.loads(response)
            return validation_result

        except Exception as e:
            raise Exception(f"Principle compliance validation failed: {str(e)}")

    def detect_principle_conflicts(self, architecture_id: int) -> List[Dict]:
        """
        Detect conflicting principles within an architecture.

        Args:
            architecture_id: ID of the ArchitectureModel

        Returns:
            List of conflicts:
            [
                {
                    'principle1_id': 3,
                    'principle1_name': 'Use proprietary database for performance',
                    'principle2_id': 7,
                    'principle2_name': 'Prefer open source over proprietary',
                    'conflict_type': 'direct_contradiction',
                    'severity': 'high',
                    'description': 'Principle 3 mandates proprietary while Principle 7 prefers open source',
                    'resolution_options': [...]
                }
            ]
        """
        principles = Principle.query.filter_by(
            architecture_id=architecture_id, status="approved"
        ).all()

        if len(principles) < 2:
            return []

        prompt = self._build_conflict_detection_prompt(principles)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            conflicts_data = json.loads(response)
            return conflicts_data.get("conflicts", [])

        except Exception as e:
            raise Exception(f"Conflict detection failed: {str(e)}")

    def enforce_principles(self, architecture_id: int) -> Dict:
        """
        Enforce all principles across requirements in architecture.

        Validates all requirements against all approved principles.

        Args:
            architecture_id: ID of the ArchitectureModel

        Returns:
            Dict with enforcement summary:
            {
                'total_requirements': 50,
                'compliant_requirements': 42,
                'non_compliant_requirements': 8,
                'compliance_rate': 84,
                'violations_by_severity': {
                    'critical': 2,
                    'high': 3,
                    'medium': 3
                },
                'top_violated_principles': [...]
            }
        """
        requirements = Requirement.query.filter_by(architecture_id=architecture_id).all()

        principles = Principle.query.filter_by(
            architecture_id=architecture_id, status="approved"
        ).all()

        if not requirements or not principles:
            return {"total_requirements": 0}

        total_reqs = len(requirements)
        compliant_count = 0
        violations_by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        principle_violation_counts = {}

        for req in requirements:
            validation = self.validate_requirement_against_principles(
                req.id, [p.id for p in principles]
            )

            if validation.get("compliant", False):
                compliant_count += 1
            else:
                for violation in validation.get("violations", []):
                    severity = violation.get("severity", "medium")
                    violations_by_severity[severity] = violations_by_severity.get(severity, 0) + 1

                    principle_id = violation.get("principle_id")
                    if principle_id:
                        principle_violation_counts[principle_id] = (
                            principle_violation_counts.get(principle_id, 0) + 1
                        )

        # Identify most violated principles
        top_violated = sorted(principle_violation_counts.items(), key=lambda x: x[1], reverse=True)[
            :5
        ]

        top_violated_principles = []
        for principle_id, count in top_violated:
            principle = db.session.get(Principle, principle_id)
            if principle:
                top_violated_principles.append(
                    {
                        "principle_id": principle_id,
                        "principle_name": principle.name,
                        "violation_count": count,
                    }
                )

        return {
            "total_requirements": total_reqs,
            "compliant_requirements": compliant_count,
            "non_compliant_requirements": total_reqs - compliant_count,
            "compliance_rate": round((compliant_count / total_reqs) * 100, 1),
            "violations_by_severity": violations_by_severity,
            "top_violated_principles": top_violated_principles,
        }

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _create_principle(
        self, principle_info: Dict, architecture_id: int, policy_source: Optional[str] = None
    ) -> Principle:
        """Create Principle instance with ArchiMate element."""
        # Create ArchiMate Principle element
        principle_element = ArchiMateElement(
            name=principle_info["name"],
            type="Principle",
            layer="motivation",
            description=principle_info.get("statement", ""),
            documentation=principle_info.get("details", ""),
            architecture_id=architecture_id,
        )
        db.session.add(principle_element)
        db.session.flush()

        # Create Principle instance
        principle = Principle(
            name=principle_info["name"],
            statement=principle_info.get("statement", ""),
            rationale=principle_info.get("rationale", ""),
            implications=principle_info.get("implications", ""),
            archimate_element_id=principle_element.id,
            category=principle_info.get("category", "Architecture"),
            enforcement_level=principle_info.get("enforcement_level", "SHOULD"),
            status="draft",
            architecture_id=architecture_id,
        )

        if policy_source:
            props = {"source": policy_source, "extracted_at": datetime.utcnow().isoformat()}
            principle_element.properties = json.dumps(props)

        db.session.add(principle)
        return principle

    def _create_requirement_from_principle(
        self, req_info: Dict, principle: Principle, architecture_id: int
    ) -> Requirement:
        """Create Requirement derived from Principle."""
        # Create ArchiMate Requirement element
        req_element = ArchiMateElement(
            name=req_info["title"],
            type="Requirement",
            layer="motivation",
            description=req_info.get("description", ""),
            architecture_id=architecture_id,
        )
        db.session.add(req_element)
        db.session.flush()

        # Create Requirement instance
        requirement = Requirement(
            title=req_info["title"],
            description=req_info.get("description", ""),
            type=req_info.get("type", "non-functional"),
            category=req_info.get("category", principle.category),
            priority=req_info.get("priority", "medium"),
            rationale=f"Derived from principle: {principle.name}",
            archimate_element_id=req_element.id,
            architecture_id=architecture_id,
        )
        db.session.add(requirement)

        # Create influence relationship (Principle influences Requirement)
        relationship = ArchiMateRelationship(
            type="influence",
            source_id=principle.archimate_element_id,
            target_id=req_element.id,
            architecture_id=architecture_id,
        )
        db.session.add(relationship)

        return requirement

    # ========================================================================
    # Prompt Building Methods
    # ========================================================================

    def _build_principle_extraction_prompt(
        self, policy_docs: str, policy_source: Optional[str]
    ) -> str:
        """Build principle extraction prompt."""
        source_info = f"Source: {policy_source}" if policy_source else ""

        return f"""You are an enterprise architect extracting architectural principles from policy documents.

{source_info}

Policy Documents:
{policy_docs}

Extract all architectural PRINCIPLES (normative statements that constrain design/implementation).

A principle:
- States HOW things should be done (not WHAT to build)
- Uses normative keywords: MUST, SHALL, SHOULD, MAY (RFC 2119)
- Provides rationale (WHY it exists)
- Describes implications (WHAT it means for implementation)

For each principle:
- name: Concise principle name (5 - 10 words)
- statement: Full principle statement with normative keyword
- rationale: Why this principle exists
- implications: What this means for architects/developers
- category: Security | Data | Integration | Technology | Business | Architecture
- enforcement_level: MUST | SHALL | SHOULD | MAY

Return JSON:
{{
  "principles": [
    {{
      "name": "Data Encryption at Rest",
      "statement": "All customer and sensitive business data MUST be encrypted at rest using industry-standard encryption (AES - 256 or equivalent)",
      "rationale": "Protects data from unauthorized access in case of physical theft or backup exposure. Required for GDPR, PCI-DSS compliance.",
      "implications": "All databases must enable transparent data encryption. File storage must use encrypted volumes. Encryption keys must be managed via HSM or cloud KMS.",
      "category": "Security",
      "enforcement_level": "MUST"
    }},
    {{
      "name": "Cloud-First Strategy",
      "statement": "New applications SHOULD be deployed on cloud platforms unless specific constraints require on-premises deployment",
      "rationale": "Cloud provides scalability, resilience, and reduced operational overhead. Aligns with digital transformation strategy.",
      "implications": "Default architecture designs target AWS/Azure/GCP. On-premises deployments require architecture review board approval with justification.",
      "category": "Technology",
      "enforcement_level": "SHOULD"
    }}
  ]
}}

Extract only principles explicitly stated or strongly implied in the documents.
"""

    def _build_categorized_extraction_prompt(self, policy_docs: str, categories: List[str]) -> str:
        """Build categorized principle extraction prompt."""
        categories_str = ", ".join(categories)

        return f"""Extract architectural principles from policy documents, organized by category.

Policy Documents:
{policy_docs}

Categories: {categories_str}

For each category, extract relevant principles.

Return JSON organized by category:
{{
  "Security": [
    {{"name": "Data Encryption", "statement": "...", "rationale": "...", "implications": "...", "enforcement_level": "MUST"}}
  ],
  "Data": [...],
  "Integration": [...],
  "Technology": [...],
  "Business": [...],
  "Architecture": [...]
}}

If no principles found for a category, return empty array.
"""

    def _build_requirement_derivation_prompt(
        self, principle: Principle, business_context: Optional[str]
    ) -> str:
        """Build requirement derivation prompt."""
        context_section = f"\n\nBusiness Context:\n{business_context}" if business_context else ""

        return f"""You are an enterprise architect deriving specific requirements from an architectural principle.

Principle:
Name: {principle.name}
Statement: {principle.statement}
Rationale: {principle.rationale}
Implications: {principle.implications}
Enforcement Level: {principle.enforcement_level}
Category: {principle.category}
{context_section}

Derive 3 - 5 specific REQUIREMENTS that implement this principle.

Each requirement should:
- Be specific and testable
- Directly implement the principle
- Include acceptance criteria
- Specify technology/approach when relevant

Return JSON:
{{
  "requirements": [
    {{
      "title": "Database Encryption Implementation",
      "description": "All PostgreSQL and MySQL databases MUST enable Transparent Data Encryption (TDE) using AES - 256",
      "type": "non-functional",
      "category": "Security",
      "priority": "critical",
      "acceptance_criteria": [
        "TDE enabled on all production databases",
        "Encryption verified via database configuration audit",
        "Key rotation policy documented and implemented"
      ]
    }},
    {{
      "title": "Key Management Service Integration",
      "description": "Encryption keys MUST be managed via AWS KMS or Azure Key Vault, not stored in application code",
      "type": "non-functional",
      "category": "Security",
      "priority": "critical",
      "acceptance_criteria": [
        "All keys stored in KMS/Key Vault",
        "Key access logged and monitored",
        "Automated key rotation enabled"
      ]
    }}
  ]
}}
"""

    def _build_compliance_validation_prompt(
        self, requirement: Requirement, principles: List[Principle]
    ) -> str:
        """Build compliance validation prompt."""
        principles_list = "\n".join(
            [
                f"ID: {p.id}, Name: {p.name}, Enforcement: {p.enforcement_level}, Statement: {p.statement}"
                for p in principles
            ]
        )

        return f"""You are an enterprise architect validating requirement compliance with principles.

Requirement:
Title: {requirement.title}
Description: {requirement.description}
Type: {requirement.type}
Category: {requirement.category}

Principles to Check:
{principles_list}

Validate if the requirement complies with each principle.

For violations:
- Identify which principle is violated
- Explain how it's violated
- Assess severity: critical (MUST violated), high (SHALL violated), medium (SHOULD violated), low (MAY violated)
- Recommend how to fix

Return JSON:
{{
  "compliant": false,
  "violations": [
    {{
      "principle_id": 5,
      "principle_name": "Cloud-First Strategy",
      "enforcement_level": "SHOULD",
      "severity": "medium",
      "violation": "Requirement specifies on-premises deployment without justification",
      "recommendation": "Revise to use cloud services or provide ARB-approved exception for on-premises deployment"
    }}
  ],
  "warnings": [
    {{
      "principle_id": 8,
      "principle_name": "Open Source Preferred",
      "message": "Requirement uses proprietary database. Consider PostgreSQL (open source alternative)."
    }}
  ],
  "compliance_score": 75
}}
"""

    def _build_conflict_detection_prompt(self, principles: List[Principle]) -> str:
        """Build conflict detection prompt."""
        principles_list = "\n".join(
            [
                f"ID: {p.id}, Name: {p.name}, Statement: {p.statement}, Enforcement: {p.enforcement_level}"
                for p in principles
            ]
        )

        return f"""You are an enterprise architect analyzing architectural principles for conflicts.

Principles:
{principles_list}

Identify any conflicting principles where:
- Direct contradiction: Principle A mandates X, Principle B mandates NOT X
- Practical conflict: Following both principles simultaneously is impractical
- Priority conflict: Unclear which principle takes precedence

Return JSON:
{{
  "conflicts": [
    {{
      "principle1_id": 3,
      "principle1_name": "Use Oracle for performance-critical systems",
      "principle2_id": 7,
      "principle2_name": "Prefer open source over proprietary solutions",
      "conflict_type": "practical_conflict",
      "severity": "high",
      "description": "Principle 3 mandates Oracle (proprietary) for performance, while Principle 7 prefers open source. This creates ambiguity for performance-critical systems.",
      "resolution_options": [
        "Add exception clause to Principle 7 for performance-critical systems",
        "Revise Principle 3 to allow PostgreSQL with performance benchmarking",
        "Establish precedence: Performance requirements override open source preference"
      ]
    }}
  ]
}}

Return empty conflicts array if no conflicts found.
"""
