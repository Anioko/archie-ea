"""
Business Process Knowledge Base
Domain-specific understanding of APQC processes and their relationships
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


@dataclass
class ProcessRelationship:
    """Defines relationships between APQC processes"""

    source_code: str
    target_code: str
    relationship_type: str  # 'parent', 'child', 'related', 'alternative'
    confidence: float
    business_context: str


@dataclass
class BusinessDomain:
    """Business domain with associated processes"""

    domain_name: str
    keywords: Set[str]
    process_codes: Set[str]
    common_patterns: List[str]


class BusinessProcessKnowledge:
    """Domain knowledge for APQC process classification"""

    def __init__(self):
        # APQC Category Mappings
        self.category_mappings = {
            "1": {
                "name": "Develop Vision and Strategy",
                "keywords": {"strategy", "vision", "planning", "governance"},
            },
            "2": {
                "name": "Develop and Manage Products and Services",
                "keywords": {"product", "service", "design", "development", "content"},
            },
            "3": {
                "name": "Market and Sell Products and Services",
                "keywords": {"market", "sell", "sales", "customer", "marketing"},
            },
            "4": {
                "name": "Deliver Physical Products",
                "keywords": {
                    "deliver",
                    "physical",
                    "product",
                    "logistics",
                    "warehouse",
                    "supply chain",
                },
            },
            "5": {
                "name": "Deliver Services",
                "keywords": {"service", "deliver", "customer", "support", "operations"},
            },
            "6": {
                "name": "Manage Customer Service",
                "keywords": {"customer", "service", "support", "call", "help", "complaint"},
            },
            "7": {
                "name": "Develop and Manage Human Capital",
                "keywords": {"hr", "human", "employee", "staff", "personnel", "workforce"},
            },
            "8": {
                "name": "Manage Information Technology",
                "keywords": {"it", "technology", "system", "software", "hardware", "data"},
            },
            "9": {
                "name": "Manage Financial Resources",
                "keywords": {"financial", "finance", "accounting", "budget", "cost", "payroll"},
            },
            "10": {
                "name": "Acquire, Construct, and Manage Assets",
                "keywords": {"asset", "property", "facility", "equipment", "infrastructure"},
            },
            "11": {
                "name": "Manage Environmental Health and Safety",
                "keywords": {"environmental", "health", "safety", "risk", "compliance"},
            },
            "12": {
                "name": "Manage External Relationships",
                "keywords": {"external", "partner", "supplier", "vendor", "relationship"},
            },
            "13": {
                "name": "Develop and Manage Business Capabilities",
                "keywords": {"capability", "process", "improvement", "quality", "framework"},
            },
        }

        # Business Domain Patterns
        self.business_domains = [
            BusinessDomain(
                domain_name="HR/Workforce Management",
                keywords={
                    "hr",
                    "human",
                    "resource",
                    "employee",
                    "staff",
                    "personnel",
                    "workforce",
                    "payroll",
                    "attendance",
                    "onboarding",
                    "mobility",
                    "exit",
                    "recruit",
                    "retire",
                    "reward",
                },
                process_codes={"7.1", "7.2", "7.3", "7.4", "7.5", "7.6"},
                common_patterns=[
                    "time and attendance",
                    "onboarding",
                    "mobility",
                    "exit",
                    "payroll",
                    "hr",
                    "human resources",
                ],
            ),
            BusinessDomain(
                domain_name="Logistics/Warehouse",
                keywords={
                    "warehouse",
                    "logistics",
                    "inventory",
                    "wms",
                    "supply",
                    "chain",
                    "distribution",
                    "delivery",
                    "transport",
                },
                process_codes={"4.1", "4.2", "4.3", "4.4", "4.5", "5.1", "5.2", "5.3", "5.4"},
                common_patterns=[
                    "warehouse",
                    "wms",
                    "logistics",
                    "inventory",
                    "supply chain",
                    "distribution",
                ],
            ),
            BusinessDomain(
                domain_name="IT/Technology",
                keywords={
                    "it",
                    "technology",
                    "software",
                    "hardware",
                    "system",
                    "application",
                    "digital",
                    "data",
                    "network",
                    "infrastructure",
                },
                process_codes={"8.1", "8.2", "8.3", "8.4", "8.5"},
                common_patterns=[
                    "it",
                    "technology",
                    "software",
                    "hardware",
                    "system",
                    "application",
                    "digital",
                    "data",
                ],
            ),
            BusinessDomain(
                domain_name="Finance/Accounting",
                keywords={
                    "financial",
                    "finance",
                    "accounting",
                    "budget",
                    "cost",
                    "payroll",
                    "reporting",
                    "general ledger",
                    "ap",
                    "ar",
                },
                process_codes={"9.1", "9.2", "9.3", "9.4", "9.5"},
                common_patterns=[
                    "finance",
                    "accounting",
                    "budget",
                    "cost",
                    "payroll",
                    "general ledger",
                    "reporting",
                ],
            ),
            BusinessDomain(
                domain_name="Customer Service",
                keywords={
                    "customer",
                    "service",
                    "support",
                    "call",
                    "help",
                    "complaint",
                    "contact",
                    "crm",
                },
                process_codes={"6.1", "6.2", "6.3", "6.4", "6.5", "6.6"},
                common_patterns=["customer", "service", "support", "call", "help", "complaint"],
            ),
        ]

        # Process Relationships
        self.process_relationships = self._build_process_relationships()

        # Synonym Mappings
        self.synonym_mappings = {
            "time and attendance": [
                "workforce management",
                "time tracking",
                "attendance tracking",
                "employee scheduling",
            ],
            "warehouse": [
                "wms",
                "warehouse management",
                "inventory management",
                "distribution center",
            ],
            "onboarding": ["employee onboarding", "new hire", "orientation", "employee induction"],
            "payroll": ["payroll processing", "salary", "compensation", "wage management"],
            "event stream": [
                "event processing",
                "stream processing",
                "real-time processing",
                "event-driven",
            ],
        }

    def _build_process_relationships(self) -> List[ProcessRelationship]:
        """Build known relationships between processes"""
        relationships = [
            # HR domain relationships
            ProcessRelationship("7.1", "7.2", "sequential", 0.9, "Strategy drives recruitment"),
            ProcessRelationship("7.2", "7.3", "sequential", 0.9, "Recruit leads to development"),
            ProcessRelationship("7.3", "7.4", "sequential", 0.8, "Development enables management"),
            ProcessRelationship("7.4", "7.5", "sequential", 0.8, "Management requires rewards"),
            ProcessRelationship("7.5", "7.6", "sequential", 0.7, "Rewards precede retirement"),
            # Logistics domain relationships
            ProcessRelationship("4.1", "4.2", "sequential", 0.9, "Planning enables sourcing"),
            ProcessRelationship("4.2", "4.3", "sequential", 0.9, "Sourcing enables production"),
            ProcessRelationship("4.3", "4.4", "sequential", 0.9, "Production enables delivery"),
            ProcessRelationship("4.4", "4.5", "sequential", 0.8, "Delivery requires logistics"),
            # Cross-domain relationships
            ProcessRelationship(
                "5.3", "4.5", "related", 0.7, "Service delivery relates to logistics"
            ),
            ProcessRelationship(
                "9.5", "7.6", "related", 0.8, "Payroll relates to employee retirement"
            ),
        ]
        return relationships

    def identify_business_domain(self, text: str) -> Tuple[BusinessDomain, float]:
        """Identify the most relevant business domain for text"""
        text_lower = text.lower()
        best_domain = None
        best_score = 0.0

        for domain in self.business_domains:
            score = 0.0
            # Check keyword matches
            for keyword in domain.keywords:
                if keyword in text_lower:
                    score += 1.0

            # Check pattern matches
            for pattern in domain.common_patterns:
                if pattern in text_lower:
                    score += 0.8

            # Normalize score
            score = score / (len(domain.keywords) + len(domain.common_patterns))

            if score > best_score:
                best_score = score
                best_domain = domain

        return best_domain, best_score

    def get_related_processes(
        self, process_code: str, max_depth: int = 2
    ) -> List[Tuple[str, float]]:
        """Get processes related to the given process code"""
        related = []
        visited = set()

        def find_related(code: str, depth: int, accumulated_score: float):
            if depth > max_depth or code in visited:
                return

            visited.add(code)

            for rel in self.process_relationships:
                if rel.source_code == code:
                    related.append((rel.target_code, accumulated_score * rel.confidence))
                    find_related(rel.target_code, depth + 1, accumulated_score * rel.confidence)
                elif rel.target_code == code:
                    related.append((rel.source_code, accumulated_score * rel.confidence))
                    find_related(rel.source_code, depth + 1, accumulated_score * rel.confidence)

        find_related(process_code, 0, 1.0)
        return sorted(related, key=lambda x: x[1], reverse=True)

    def expand_with_synonyms(self, text: str) -> List[str]:
        """Expand text with known synonyms"""
        expanded = [text]
        text_lower = text.lower()

        for concept, synonyms in self.synonym_mappings.items():
            if concept in text_lower:
                expanded.extend(synonyms)

        return expanded

    def calculate_domain_confidence(self, text: str, process_code: str) -> float:
        """Calculate confidence score based on domain alignment"""
        domain, domain_score = self.identify_business_domain(text)

        if not domain:
            return 0.5  # Neutral score if no domain identified

        # Check if process belongs to identified domain
        if process_code.split(".")[0] in [code.split(".")[0] for code in domain.process_codes]:
            return min(0.9, domain_score + 0.3)  # Boost for domain alignment

        # Check for cross-domain relationships
        for domain_code in domain.process_codes:
            related = self.get_related_processes(domain_code, max_depth=1)
            for related_code, score in related:
                if related_code == process_code:
                    return min(0.8, domain_score + score * 0.2)

        return max(0.3, domain_score - 0.2)  # Penalty for domain mismatch
