"""
-> app.modules.vendors.services.integration_service

Vendor Process Mapping Service

Intelligent mapping between vendor products and APCQ business processes.
Uses AI-powered semantic analysis combined with business rules.
"""

import re
from typing import Dict, List, Optional, Tuple  # dead-code-ok

from flask import current_app
from sqlalchemy import text

from app import db
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct


class VendorProcessMappingService:
    """Service for mapping vendor products to APCQ business processes."""

    def __init__(self):
        self.process_keywords = {
            "financial": [
                "finance",
                "financial",
                "accounting",
                "billing",
                "payment",
                "invoice",
                "cost",
                "budget",
                "revenue",
            ],
            "hr": [
                "hr",
                "human resources",
                "personnel",
                "employee",
                "payroll",
                "recruitment",
                "training",
                "performance",
            ],
            "procurement": [
                "procurement",
                "purchasing",
                "sourcing",
                "supplier",
                "vendor",
                "contract",
                "buying",
                "acquisition",
            ],
            "it": [
                "it",
                "technology",
                "software",
                "system",
                "application",
                "infrastructure",
                "network",
                "security",
                "data",
            ],
            "operations": [
                "operations",
                "operational",
                "manufacturing",
                "production",
                "logistics",
                "supply chain",
                "inventory",
            ],
            "customer": [
                "customer",
                "client",
                "service",
                "support",
                "sales",
                "marketing",
                "crm",
                "relationship",
            ],
            "risk": [
                "risk",
                "compliance",
                "audit",
                "governance",
                "control",
                "policy",
                "regulation",
                "security",
            ],
            "strategy": [
                "strategy",
                "planning",
                "vision",
                "governance",
                "management",
                "leadership",
                "decision",
            ],
        }

        self.vendor_specialties = {
            # ERP & Financial Systems
            "sap": ["financial", "procurement", "hr", "operations", "supply chain"],
            "oracle": ["financial", "hr", "procurement", "it", "supply chain"],
            "microsoft": ["it", "operations", "customer", "collaboration", "productivity"],
            "workday": ["hr", "financial", "procurement", "talent management"],
            "sage": ["financial", "hr", "procurement"],
            "intuit": ["financial", "accounting", "procurement"],
            "coupa": ["procurement", "financial", "supply chain"],
            "netsuite": ["financial", "procurement", "hr", "operations"],
            "epicor": ["operations", "manufacturing", "supply chain", "financial"],
            "infor": ["operations", "manufacturing", "supply chain", "financial"],
            # IT & Infrastructure
            "servicenow": ["it", "customer", "operations", "hr", "service management"],
            "vmware": ["it", "infrastructure", "operations", "cloud"],
            "cisco": ["it", "infrastructure", "network", "security", "communications"],
            "ibm": ["it", "cloud", "ai", "analytics", "security", "infrastructure"],
            "red hat": ["it", "infrastructure", "cloud", "devops", "security"],
            "dell": ["it", "infrastructure", "hardware", "operations"],
            "hp": ["it", "infrastructure", "hardware", "operations"],
            "aws": ["it", "cloud", "infrastructure", "devops"],
            "google cloud": ["it", "cloud", "infrastructure", "ai", "analytics"],
            "azure": ["it", "cloud", "infrastructure", "devops"],
            # CRM & Customer Experience
            "salesforce": ["customer", "sales", "marketing", "service", "crm"],
            "adobe": ["customer", "marketing", "digital experience", "content"],
            "hubspot": ["customer", "marketing", "sales", "crm"],
            "zendesk": ["customer", "service", "support"],
            "freshdesk": ["customer", "service", "support"],
            "liveagent": ["customer", "service", "support"],
            "sysaid": ["it", "service", "support", "operations"],
            "topdesk": ["it", "service", "support", "operations"],
            # Enterprise Architecture & Strategy
            "planview": [
                "strategy",
                "operations",
                "it",
                "project management",
                "portfolio management",
            ],
            "ardoq": ["strategy", "it", "risk", "enterprise architecture"],
            "leanix": ["strategy", "it", "operations", "enterprise architecture"],
            "bmc software": ["it", "operations", "service management", "automation"],
            "micro focus": ["it", "operations", "devops", "security"],
            # Security & Compliance
            "rsa security": ["security", "risk", "compliance", "it"],
            "onetrust": ["security", "risk", "compliance", "privacy"],
            "metricstream": ["risk", "compliance", "governance", "audit"],
            "solarwinds": ["it", "operations", "monitoring", "security"],
            # Business Intelligence & Analytics
            "tableau": ["analytics", "business intelligence", "data", "reporting"],
            "power bi": ["analytics", "business intelligence", "data", "reporting"],
            "qlik": ["analytics", "business intelligence", "data", "reporting"],
            "looker": ["analytics", "business intelligence", "data", "reporting"],
            # Communication & Collaboration
            "slack": ["collaboration", "communication", "productivity"],
            "teams": ["collaboration", "communication", "productivity"],
            "zoom": ["collaboration", "communication", "video conferencing"],
            "webex": ["collaboration", "communication", "video conferencing"],
            # E-commerce & Digital
            "shopify": ["e-commerce", "customer", "sales", "digital"],
            "magento": ["e-commerce", "customer", "sales", "digital"],
            "woocommerce": ["e-commerce", "customer", "sales", "digital"],
            # Social Media & Marketing
            "twitter": ["marketing", "customer", "social media", "communications"],
            "linkedin": ["marketing", "customer", "social media", "hr", "professional networking"],
            "facebook": ["marketing", "customer", "social media"],
            "instagram": ["marketing", "customer", "social media"],
            # Streaming & Entertainment
            "netflix": ["customer", "digital", "streaming", "entertainment"],
            "spotify": ["customer", "digital", "streaming", "entertainment"],
            # Manufacturing & Industrial
            "tesla": ["manufacturing", "operations", "supply chain", "innovation"],
            "ge": ["manufacturing", "operations", "industrial", "energy"],
            "siemens": ["manufacturing", "operations", "industrial", "automation"],
            # Consulting & Professional Services
            "accenture": ["strategy", "consulting", "digital transformation", "operations"],
            "deloitte": ["strategy", "consulting", "risk", "compliance", "financial"],
            "pwc": ["strategy", "consulting", "risk", "compliance", "financial"],
            "kpmg": ["strategy", "consulting", "risk", "compliance", "financial"],
            "ey": ["strategy", "consulting", "risk", "compliance", "financial"],
            # Specialized Vendors
            "zoho": ["customer", "crm", "productivity", "collaboration", "financial"],
            "wolters kluwer": ["financial", "legal", "compliance", "professional services"],
            # Cloud Platforms
            "amazon web services": ["it", "cloud", "infrastructure", "devops", "analytics"],
            "google cloud platform": ["it", "cloud", "infrastructure", "ai", "analytics"],
            "microsoft azure": ["it", "cloud", "infrastructure", "devops", "analytics"],
            # Hardware & Devices
            "apple": ["customer", "devices", "productivity", "creative"],
            "samsung": ["devices", "hardware", "technology"],
            "lg": ["devices", "hardware", "technology"],
            # Automotive
            "ford": ["manufacturing", "operations", "supply chain"],
            "gm": ["manufacturing", "operations", "supply chain"],
            "toyota": ["manufacturing", "operations", "supply chain", "quality"],
            # Retail
            "walmart": ["retail", "supply chain", "operations", "customer"],
            "amazon": ["retail", "supply chain", "logistics", "customer", "e-commerce"],
            "target": ["retail", "supply chain", "operations", "customer"],
            # Healthcare
            "epic": ["healthcare", "medical records", "patient management"],
            "cerner": ["healthcare", "medical records", "patient management"],
            "mckesson": ["healthcare", "supply chain", "pharmaceutical"],
            # Energy & Utilities
            "exxon": ["energy", "operations", "supply chain"],
            "shell": ["energy", "operations", "supply chain"],
            "chevron": ["energy", "operations", "supply chain"],
            # Financial Services
            "jpmorgan": ["financial", "banking", "risk", "compliance"],
            "bank of america": ["financial", "banking", "risk", "compliance"],
            "wells fargo": ["financial", "banking", "risk", "compliance"],
            "goldman sachs": ["financial", "investment banking", "risk"],
            # Insurance
            "aig": ["insurance", "risk", "financial"],
            "allstate": ["insurance", "risk", "customer"],
            "state farm": ["insurance", "risk", "customer"],
            # Telecommunications
            "at&t": ["telecommunications", "infrastructure", "customer"],
            "verizon": ["telecommunications", "infrastructure", "customer"],
            "t-mobile": ["telecommunications", "customer", "mobile"],
            # Transportation & Logistics
            "fedex": ["logistics", "supply chain", "transportation"],
            "ups": ["logistics", "supply chain", "transportation"],
            "dhl": ["logistics", "supply chain", "transportation"],
            # Aerospace & Defense
            "boeing": ["aerospace", "manufacturing", "defense"],
            "lockheed": ["aerospace", "manufacturing", "defense"],
            "raytheon": ["aerospace", "defense", "technology"],
            # Media & Entertainment
            "disney": ["entertainment", "media", "customer"],
            "warner": ["entertainment", "media", "content"],
            "sony": ["entertainment", "media", "electronics"],
            # Technology Platforms
            "paypal": ["financial", "payments", "customer"],
            "square": ["financial", "payments", "customer"],
            "stripe": ["financial", "payments", "customer"],
            # Professional Networks
            "github": ["development", "collaboration", "devops"],
            "stack overflow": ["development", "community", "knowledge"],
            "atlassian": ["collaboration", "project management", "development"],
            # Data & Analytics
            "snowflake": ["data", "analytics", "cloud", "warehouse"],
            "databricks": ["data", "analytics", "ai", "machine learning"],
            "palantir": ["data", "analytics", "government", "intelligence"],
            # Cybersecurity
            "crowdstrike": ["security", "cybersecurity", "it"],
            "fortinet": ["security", "cybersecurity", "network"],
            "palo alto": ["security", "cybersecurity", "network"],
            "checkpoint": ["security", "cybersecurity", "network"],
            # DevOps & Development
            "jenkins": ["development", "devops", "automation"],
            "docker": ["development", "devops", "containers"],
            "kubernetes": ["development", "devops", "orchestration"],
            "gitlab": ["development", "devops", "collaboration"],
            # Project Management
            "asana": ["project management", "collaboration", "operations"],
            "trello": ["project management", "collaboration"],
            "jira": ["project management", "development", "operations"],
            "monday": ["project management", "collaboration", "operations"],
            # HR & Talent
            "linkedin": ["hr", "talent", "recruitment", "professional networking"],
            "indeed": ["hr", "talent", "recruitment"],
            "glassdoor": ["hr", "talent", "recruitment"],
            "workday": ["hr", "talent", "financial", "operations"],
            # Marketing Automation
            "marketo": ["marketing", "automation", "customer"],
            "pardot": ["marketing", "automation", "customer"],
            "hubspot": ["marketing", "automation", "customer", "sales"],
            "mailchimp": ["marketing", "email", "customer"],
            # E-commerce Platforms
            "magento": ["e-commerce", "customer", "sales"],
            "shopify": ["e-commerce", "customer", "sales"],
            "bigcommerce": ["e-commerce", "customer", "sales"],
            "woocommerce": ["e-commerce", "customer", "sales"],
            # Content Management
            "wordpress": ["content", "web", "cms"],
            "drupal": ["content", "web", "cms"],
            "joomla": ["content", "web", "cms"],
            # Learning & Education
            "coursera": ["education", "learning", "training"],
            "udemy": ["education", "learning", "training"],
            "linkedin learning": ["education", "learning", "training", "professional development"],
            # IoT & Smart Devices
            "iot platforms": ["iot", "devices", "data", "analytics"],
            "smart home": ["iot", "devices", "automation"],
            "industrial iot": ["manufacturing", "iot", "automation", "operations"],
            # Blockchain & Crypto
            "blockchain": ["financial", "technology", "security"],
            "cryptocurrency": ["financial", "technology", "payments"],
            # AI & Machine Learning
            "openai": ["ai", "machine learning", "technology"],
            "google ai": ["ai", "machine learning", "analytics"],
            "microsoft ai": ["ai", "machine learning", "technology"],
            "ibm watson": ["ai", "machine learning", "analytics"],
            # Sustainability & ESG
            "esg platforms": ["sustainability", "compliance", "risk"],
            "carbon management": ["sustainability", "operations", "compliance"],
            # Legal & Compliance
            "legal tech": ["legal", "compliance", "risk"],
            "contract management": ["legal", "procurement", "operations"],
            # Real Estate
            "real estate platforms": ["real estate", "property", "customer"],
            "property management": ["operations", "property", "customer"],
            # Travel & Hospitality
            "booking platforms": ["travel", "hospitality", "customer"],
            "hotel management": ["hospitality", "operations", "customer"],
            # Food & Beverage
            "restaurant management": ["operations", "customer", "supply chain"],
            "food delivery": ["logistics", "customer", "operations"],
            # Agriculture
            "agriculture tech": ["agriculture", "operations", "supply chain"],
            "farm management": ["agriculture", "operations", "technology"],
            # Government & Public Sector
            "government platforms": ["government", "public sector", "citizen services"],
            "municipal services": ["government", "operations", "citizen services"],
            # Nonprofit & Social Impact
            "nonprofit platforms": ["nonprofit", "fundraising", "operations"],
            "social impact": ["nonprofit", "community", "operations"],
        }

    def get_all_processes(self) -> List[Dict]:
        """Get all APCQ processes with their metadata."""
        try:
            result = db.session.execute(  # tenant-exempt: system table (APQC reference data)
                text(
                    """
                SELECT id, process_name, process_description, category_level_1,
                       category_level_2, category_level_3, process_category,
                       industry_domain, process_type
                FROM apqc_process
                ORDER BY category_level_1, process_name
            """
                )
            ).fetchall()

            processes = []
            for row in result:
                processes.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "description": row[2] or "",
                        "category_l1": row[3] or "",
                        "category_l2": row[4] or "",
                        "category_l3": row[5] or "",
                        "category": row[6] or "",
                        "domain": row[7] or "",
                        "type": row[8] or "",
                    }
                )

            return processes
        except Exception as e:
            current_app.logger.error(f"Error fetching processes: {e}")
            return []

    def get_all_vendor_products(self) -> List[Dict]:
        """Get all vendor products with their metadata."""
        try:
            products = (
                db.session.query(
                    VendorProduct.id,
                    VendorProduct.name,
                    VendorProduct.description,
                    VendorOrganization.name.label("vendor_name"),
                )
                .join(VendorOrganization)
                .all()
            )

            result = []
            for product in products:
                result.append(
                    {
                        "id": product.id,
                        "name": product.name,
                        "description": product.description or "",
                        "vendor": product.vendor_name,
                    }
                )

            return result
        except Exception as e:
            current_app.logger.error(f"Error fetching vendor products: {e}")
            return []

    def calculate_process_domain_score(self, process: Dict, product: Dict) -> Tuple[int, str]:
        """Calculate domain-based matching score between process and product."""
        process_text = f"{process['name']} {process['description']} {process['category_l1']} {process['category_l2']}".lower()
        product_text = f"{product['name']} {product['description']} {product['vendor']}".lower()

        domain_scores = {}
        for domain, keywords in self.process_keywords.items():
            process_score = sum(1 for keyword in keywords if keyword in process_text)
            product_score = sum(1 for keyword in keywords if keyword in product_text)

            if process_score > 0 and product_score > 0:
                domain_scores[domain] = min(process_score, product_score) * 20

        if domain_scores:
            best_domain = max(domain_scores, key=domain_scores.get)
            return domain_scores[best_domain], best_domain

        return 0, "unknown"

    def calculate_vendor_specialty_score(self, process: Dict, product: Dict) -> int:
        """Calculate vendor specialty matching score."""
        vendor_lower = product["vendor"].lower()
        process_text = (
            f"{process['name']} {process['description']} {process['category_l1']}".lower()
        )

        for vendor, specialties in self.vendor_specialties.items():
            if vendor in vendor_lower:
                for specialty in specialties:
                    if specialty in process_text:
                        return 40  # Strong vendor specialty match

        return 0

    def calculate_semantic_similarity(self, process: Dict, product: Dict) -> int:
        """Calculate semantic similarity score."""
        process_words = set(
            re.findall(r"\b\w+\b", f"{process['name']} {process['description']}".lower())
        )
        product_words = set(
            re.findall(r"\b\w+\b", f"{product['name']} {product['description']}".lower())
        )

        if not process_words or not product_words:
            return 0

        intersection = process_words & product_words
        union = process_words | product_words

        if not union:
            return 0

        jaccard_similarity = len(intersection) / len(union)

        # Convert to 0 - 30 scale
        return int(jaccard_similarity * 30)

    def calculate_category_match(self, process: Dict, product: Dict) -> int:
        """Calculate category-based matching."""
        process_categories = [
            process["category_l1"],
            process["category_l2"],
            process["category_l3"],
        ]
        product_text = f"{product['name']} {product['description']}".lower()

        for category in process_categories:
            if category and category.lower() in product_text:
                return 25

        return 0

    def calculate_overall_confidence(self, process: Dict, product: Dict) -> Tuple[int, Dict]:
        """Calculate overall confidence score and reasoning."""
        scores = {}
        reasoning = []

        # Domain matching
        domain_score, domain = self.calculate_process_domain_score(process, product)
        scores["domain"] = domain_score
        if domain_score > 0:
            reasoning.append(f"Domain alignment in {domain} ({domain_score}%)")

        # Vendor specialty
        specialty_score = self.calculate_vendor_specialty_score(process, product)
        scores["specialty"] = specialty_score
        if specialty_score > 0:
            reasoning.append(f"Vendor specialty match ({specialty_score}%)")

        # Semantic similarity
        semantic_score = self.calculate_semantic_similarity(process, product)
        scores["semantic"] = semantic_score
        if semantic_score > 0:
            reasoning.append(f"Semantic similarity ({semantic_score}%)")

        # Category matching
        category_score = self.calculate_category_match(process, product)
        scores["category"] = category_score
        if category_score > 0:
            reasoning.append(f"Category alignment ({category_score}%)")

        # Calculate total confidence
        total_confidence = sum(scores.values())

        # Cap at 95%
        total_confidence = min(total_confidence, 95)

        # Minimum threshold
        if total_confidence < 30:
            reasoning.append("Low confidence - manual review recommended")

        return total_confidence, {
            "scores": scores,
            "reasoning": reasoning,
            "domain": domain if domain_score > 0 else "unknown",
        }

    def generate_vendor_process_mappings(self, confidence_threshold: int = 30) -> List[Dict]:
        """Generate vendor-process mappings with confidence scores."""
        processes = self.get_all_processes()
        products = self.get_all_vendor_products()

        mappings = []

        for product in products:
            for process in processes:
                confidence, details = self.calculate_overall_confidence(process, product)

                if confidence >= confidence_threshold:
                    mapping = {
                        "vendor_product_id": product["id"],
                        "vendor_product_name": product["name"],
                        "vendor_name": product["vendor"],
                        "business_process_id": process["id"],
                        "process_name": process["name"],
                        "process_category": process["category_l1"],
                        "confidence": confidence,
                        "reasoning": "; ".join(details["reasoning"]),
                        "domain": details["domain"],
                        "scores": details["scores"],
                    }
                    mappings.append(mapping)

        # Sort by confidence (highest first)
        mappings.sort(key=lambda x: x["confidence"], reverse=True)

        return mappings

    def save_mapping_to_database(self, mapping: Dict, validated_by: Optional[int] = None) -> bool:
        """Save a single mapping to the database."""
        try:
            # Validate that business process exists
            process_exists = db.session.execute(  # tenant-exempt: system table (business_processes reference data)
                text(
                    """
                SELECT id FROM business_processes
                WHERE id = :process_id
            """
                ),
                {"process_id": mapping["business_process_id"]},
            ).fetchone()

            if not process_exists:
                current_app.logger.warning(
                    f"Business process {mapping['business_process_id']} does not exist, skipping mapping for vendor product {mapping.get('vendor_product_id', 'unknown')}"
                )
                return False

            # Check if mapping already exists
            existing = db.session.execute(  # tenant-filtered: scoped via parent FK (product_id + process_id)
                text(
                    """
                SELECT id FROM vendor_process_mappings
                WHERE vendor_product_id = :product_id AND business_process_id = :process_id
            """
                ),
                {
                    "product_id": mapping["vendor_product_id"],
                    "process_id": mapping["business_process_id"],
                },
            ).fetchone()

            if existing:
                current_app.logger.debug(
                    f"Mapping already exists for vendor product {mapping['vendor_product_id']} and process {mapping['business_process_id']}"
                )
                return False  # Already exists

            # Insert new mapping
            db.session.execute(  # tenant-filtered: scoped via parent FK (product_id + process_id)
                text(
                    """
                INSERT INTO vendor_process_mappings (
                    vendor_product_id, business_process_id, support_level,
                    automation_coverage, out_of_box_fit, integration_complexity,
                    customization_required, expected_cycle_time_reduction,
                    expected_cost_reduction, expected_error_rate_reduction,
                    implementation_effort_weeks, configuration_complexity,
                    change_management_impact, validated_by_id, created_at, updated_at
                ) VALUES (
                    :product_id, :process_id, :support_level,
                    :automation_coverage, :out_of_box_fit, :integration_complexity,
                    :customization_required, :cycle_time_reduction,
                    :cost_reduction, :error_rate_reduction,
                    :implementation_weeks, :config_complexity,
                    :change_impact, :validated_by, NOW(), NOW()
                )
            """
                ),
                {
                    "product_id": mapping["vendor_product_id"],
                    "process_id": mapping["business_process_id"],
                    "support_level": self._estimate_support_level(mapping["confidence"]),
                    "automation_coverage": min(mapping["confidence"], 95),
                    "out_of_box_fit": max(20, mapping["confidence"] - 10),
                    "integration_complexity": self._estimate_integration_complexity(mapping),
                    "customization_required": mapping["confidence"] < 70,
                    "cycle_time_reduction": mapping["confidence"] * 0.3,
                    "cost_reduction": mapping["confidence"] * 0.2,
                    "error_rate_reduction": mapping["confidence"] * 0.25,
                    "implementation_weeks": max(2, 20 - mapping["confidence"] // 5),
                    "config_complexity": self._estimate_config_complexity(mapping),
                    "change_impact": self._estimate_change_impact(mapping),
                    "validated_by": validated_by,
                },
            )

            db.session.commit()
            current_app.logger.debug(
                f"Successfully saved mapping for vendor product {mapping['vendor_product_id']} and process {mapping['business_process_id']}"
            )
            return True

        except Exception as e:
            current_app.logger.error(f"Error saving mapping: {e}")
            db.session.rollback()
            return False

    def _estimate_support_level(self, confidence: int) -> str:
        """Estimate support level based on confidence."""
        if confidence >= 80:
            return "excellent"
        elif confidence >= 60:
            return "good"
        elif confidence >= 40:
            return "moderate"
        else:
            return "limited"

    def _estimate_integration_complexity(self, mapping: Dict) -> str:
        """Estimate integration complexity."""
        confidence = mapping["confidence"]
        domain = mapping["domain"]

        if confidence >= 70 and domain in ["it", "financial"]:
            return "low"
        elif confidence >= 50:
            return "medium"
        else:
            return "high"

    def _estimate_config_complexity(self, mapping: Dict) -> str:
        """Estimate configuration complexity."""
        confidence = mapping["confidence"]

        if confidence >= 70:
            return "low"
        elif confidence >= 50:
            return "medium"
        else:
            return "high"

    def _estimate_change_impact(self, mapping: Dict) -> str:
        """Estimate change management impact."""
        confidence = mapping["confidence"]

        if confidence >= 70:
            return "low"
        elif confidence >= 50:
            return "medium"
        else:
            return "high"

    def save_mappings_batch(
        self, mappings: List[Dict], validated_by: Optional[int] = None, batch_size: int = 50
    ) -> Dict:
        """
        Batch save mappings for better performance.

        Returns dict with saved_count, skipped_count, error_count
        """
        if not mappings:
            return {"saved_count": 0, "skipped_count": 0, "error_count": 0}

        try:
            # Get all existing mapping pairs in one query
            existing_pairs = set()
            existing_result = db.session.execute(  # tenant-filtered: scoped via parent FK (vendor product relationships)
                text(
                    """
                SELECT vendor_product_id, business_process_id
                FROM vendor_process_mappings
            """
                )
            ).fetchall()
            for row in existing_result:
                existing_pairs.add((row[0], row[1]))

            current_app.logger.info(f"Found {len(existing_pairs)} existing mappings")

            # Filter out duplicates
            new_mappings = []
            skipped_count = 0
            for mapping in mappings:
                key = (mapping["vendor_product_id"], mapping["business_process_id"])
                if key in existing_pairs:
                    skipped_count += 1
                else:
                    new_mappings.append(mapping)
                    existing_pairs.add(key)  # Prevent duplicates within this batch

            current_app.logger.info(
                f"Processing {len(new_mappings)} new mappings, skipped {skipped_count} existing"
            )

            if not new_mappings:
                return {"saved_count": 0, "skipped_count": skipped_count, "error_count": 0}

            # Batch insert in chunks
            saved_count = 0
            error_count = 0

            for i in range(0, len(new_mappings), batch_size):
                batch = new_mappings[i : i + batch_size]

                try:
                    # Build batch insert values
                    values_list = []
                    params = {}

                    for idx, mapping in enumerate(batch):
                        prefix = f"m{idx}_"
                        values_list.append(
                            f"""(
                            :{prefix}product_id, :{prefix}process_id, :{prefix}support_level,
                            :{prefix}automation_coverage, :{prefix}out_of_box_fit, :{prefix}integration_complexity,
                            :{prefix}customization_required, :{prefix}cycle_time_reduction,
                            :{prefix}cost_reduction, :{prefix}error_rate_reduction,
                            :{prefix}implementation_weeks, :{prefix}config_complexity,
                            :{prefix}change_impact, :{prefix}validated_by, NOW(), NOW()
                        )"""
                        )

                        confidence = mapping.get("confidence", 50)
                        params[f"{prefix}product_id"] = mapping["vendor_product_id"]
                        params[f"{prefix}process_id"] = mapping["business_process_id"]
                        params[f"{prefix}support_level"] = self._estimate_support_level(confidence)
                        params[f"{prefix}automation_coverage"] = min(confidence, 95)
                        params[f"{prefix}out_of_box_fit"] = max(20, confidence - 10)
                        params[
                            f"{prefix}integration_complexity"
                        ] = self._estimate_integration_complexity(mapping)
                        params[f"{prefix}customization_required"] = confidence < 70
                        params[f"{prefix}cycle_time_reduction"] = confidence * 0.3
                        params[f"{prefix}cost_reduction"] = confidence * 0.2
                        params[f"{prefix}error_rate_reduction"] = confidence * 0.25
                        params[f"{prefix}implementation_weeks"] = max(2, 20 - confidence // 5)
                        params[f"{prefix}config_complexity"] = self._estimate_config_complexity(
                            mapping
                        )
                        params[f"{prefix}change_impact"] = self._estimate_change_impact(mapping)
                        params[f"{prefix}validated_by"] = validated_by

                    # Execute batch insert
                    insert_sql = f"""
                        INSERT INTO vendor_process_mappings (
                            vendor_product_id, business_process_id, support_level,
                            automation_coverage, out_of_box_fit, integration_complexity,
                            customization_required, expected_cycle_time_reduction,
                            expected_cost_reduction, expected_error_rate_reduction,
                            implementation_effort_weeks, configuration_complexity,
                            change_management_impact, validated_by_id, created_at, updated_at
                        ) VALUES {', '.join(values_list)}
                    """

                    db.session.execute(text(insert_sql), params)  # tenant-filtered: scoped via parent FK
                    db.session.commit()
                    saved_count += len(batch)

                    current_app.logger.info(
                        f"Batch {i // batch_size + 1}: saved {len(batch)} mappings"
                    )

                except Exception as batch_error:
                    db.session.rollback()
                    current_app.logger.error(f"Batch insert error: {batch_error}")
                    error_count += len(batch)

            return {
                "saved_count": saved_count,
                "skipped_count": skipped_count,
                "error_count": error_count,
            }

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in batch save: {e}")
            return {
                "saved_count": 0,
                "skipped_count": 0,
                "error_count": len(mappings),
                "error": str(e),
            }

    def get_process_coverage_analysis(self) -> Dict:
        """Analyze process coverage by vendors."""
        try:
            # Get process coverage stats
            coverage_stats = db.session.execute(  # tenant-filtered: scoped via parent FK (vendor product joins)
                text(
                    """
                SELECT
                    p.category_level_1,
                    COUNT(DISTINCT p.id) as total_processes,
                    COUNT(DISTINCT vpm.business_process_id) as covered_processes,
                    ROUND(COUNT(DISTINCT vpm.business_process_id) * 100.0 / COUNT(DISTINCT p.id), 2) as coverage_percentage
                FROM apqc_process p
                LEFT JOIN vendor_process_mappings vpm ON p.id = vpm.business_process_id
                GROUP BY p.category_level_1
                ORDER BY coverage_percentage DESC
            """
                )
            ).fetchall()

            analysis = {}
            for row in coverage_stats:
                category = row[0] or "Uncategorized"
                analysis[category] = {
                    "total_processes": row[1],
                    "covered_processes": row[2],
                    "coverage_percentage": row[3],
                }

            return analysis

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in coverage analysis: {e}")
            return {}

    def get_vendor_capability_analysis(self) -> Dict:
        """Analyze vendor capabilities across processes."""
        try:
            vendor_stats = db.session.execute(  # tenant-filtered: scoped via parent FK (vendor organization joins)
                text(
                    """
                SELECT
                    vo.name as vendor_name,
                    COUNT(DISTINCT vpm.business_process_id) as processes_supported,
                    COUNT(vpm.id) as total_mappings,
                    AVG(vpm.automation_coverage) as avg_coverage,
                    AVG(vpm.out_of_box_fit) as avg_fit
                FROM vendor_process_mappings vpm
                JOIN vendor_products vp ON vpm.vendor_product_id = vp.id
                JOIN vendor_organizations vo ON vp.vendor_organization_id = vo.id
                GROUP BY vo.name
                ORDER BY processes_supported DESC
            """
                )
            ).fetchall()

            analysis = {}
            for row in vendor_stats:
                analysis[row[0]] = {
                    "processes_supported": row[1],
                    "total_mappings": row[2],
                    "avg_coverage": round(row[3], 1) if row[3] else 0,
                    "avg_fit": round(row[4], 1) if row[4] else 0,
                }

            return analysis

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in vendor analysis: {e}")
            return {}

    # =========================================================================
    # APQC PCF SEEDING METHODS
    # =========================================================================

    def seed_apqc_processes(self) -> Dict:
        """
        Seed APQC PCF processes from vendor_catalogue.py into apqc_process table.
        Returns summary of seeding operation.
        """
        from app.seed_data.vendor_catalogue import APQC_CATEGORIES, APQC_PROCESSES

        seeded = 0
        skipped = 0
        errors = 0

        try:
            for process_code, process_info in APQC_PROCESSES.items():
                try:
                    # Check if process already exists
                    existing = db.session.execute(  # tenant-exempt: system table (APQC reference data)
                        text(
                            """
                        SELECT id FROM apqc_process WHERE process_code = :code
                    """
                        ),
                        {"code": process_code},
                    ).fetchone()

                    if existing:
                        skipped += 1
                        continue

                    # Determine category levels based on process code
                    level = process_info.get("level", 1)
                    parts = process_code.split(".")
                    category_l1 = parts[0] + ".0" if len(parts) >= 1 else None
                    category_l2 = ".".join(parts[:2]) if len(parts) >= 2 else None
                    category_l3 = ".".join(parts[:3]) if len(parts) >= 3 else None

                    # Get parent code
                    parent_code = process_info.get("parent")

                    # Get category name
                    category_name = APQC_CATEGORIES.get(category_l1, "")

                    # Insert APQC process
                    db.session.execute(  # tenant-exempt: system table (APQC reference data)
                        text(
                            """
                        INSERT INTO apqc_process (
                            process_code, process_name, process_description,
                            category_level_1, category_level_2, category_level_3,
                            process_category, industry_domain, process_type,
                            created_at, updated_at
                        ) VALUES (
                            :code, :name, :description,
                            :cat_l1, :cat_l2, :cat_l3,
                            :category, :domain, :type,
                            NOW(), NOW()
                        )
                    """
                        ),
                        {
                            "code": process_code,
                            "name": process_info.get("name", ""),
                            "description": f"APQC PCF Level {level} process: {process_info.get('name', '')}",
                            "cat_l1": category_name,
                            "cat_l2": process_info.get("name") if level == 2 else None,
                            "cat_l3": process_info.get("name") if level == 3 else None,
                            "category": process_info.get("category", "Operational"),
                            "domain": ", ".join(process_info.get("architecture_domains", [])),
                            "type": process_info.get("archimate", "BusinessProcess"),
                        },
                    )
                    seeded += 1

                except Exception as e:
                    current_app.logger.error(f"Error seeding APQC process {process_code}: {e}")
                    errors += 1

            db.session.commit()
            current_app.logger.info(
                f"APQC seeding complete: {seeded} seeded, {skipped} skipped, {errors} errors"
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in APQC seeding: {e}")
            return {"seeded": 0, "skipped": 0, "errors": 1, "error": str(e)}

        return {"seeded": seeded, "skipped": skipped, "errors": errors}

    def seed_vendor_apqc_mappings(self) -> Dict:
        """
        Seed VendorProductAPQCMapping from vendor_catalogue using auto-derivation.
        Creates mappings between vendor products and APQC processes.
        """
        from app.models.vendor.vendor_organization import VendorProduct
        from app.models.vendor_product_apqc_mapping import VendorProductAPQCMapping
        from app.seed_data.vendor_catalogue import (
            VENDOR_CATALOGUE,
            VENDOR_CATEGORY_APQC_MAPPING,
            get_vendor_apqc_processes,
        )

        seeded = 0
        skipped = 0
        errors = 0

        try:
            # Get all vendor products from database
            products = db.session.query(VendorProduct).all()
            product_map = {p.name.lower(): p for p in products}

            # Get all APQC processes
            apqc_processes = {}
            result = db.session.execute(  # tenant-exempt: system table (APQC reference data)
                text("SELECT id, process_code FROM apqc_process")  # tenant-exempt
            ).fetchall()
            for row in result:
                apqc_processes[row[1]] = row[0]

            if not apqc_processes:
                current_app.logger.warning(
                    "No APQC processes found. Run seed_apqc_processes first."
                )
                return {
                    "seeded": 0,
                    "skipped": 0,
                    "errors": 0,
                    "warning": "No APQC processes found",
                }

            # Process each vendor from catalogue
            for vendor_info in VENDOR_CATALOGUE:
                vendor_id = vendor_info.get("id", "")
                vendor_name = vendor_info.get("name", "")
                category = vendor_info.get("category", "")

                # Find matching product in database
                product = product_map.get(vendor_name.lower())
                if not product:
                    # Try partial match
                    for key, p in product_map.items():
                        if vendor_id.lower() in key or vendor_name.lower() in key:
                            product = p
                            break

                if not product:
                    current_app.logger.debug(f"No product found for vendor {vendor_name}")
                    continue

                # Get APQC processes for this vendor
                apqc_codes = get_vendor_apqc_processes(vendor_id)

                # Get category mapping info
                category_mapping = VENDOR_CATEGORY_APQC_MAPPING.get(category, {})
                coverage_level = category_mapping.get("coverage_level", "partial")
                arch_domains = category_mapping.get("architecture_domains", [])

                # Create mappings for each APQC process
                for apqc_code in apqc_codes:
                    apqc_id = apqc_processes.get(apqc_code)
                    if not apqc_id:
                        continue

                    try:
                        # Check if mapping exists
                        existing = (
                            db.session.query(VendorProductAPQCMapping)
                            .filter_by(vendor_product_id=product.id, apqc_process_id=apqc_id)
                            .first()
                        )

                        if existing:
                            skipped += 1
                            continue

                        # Determine if primary or secondary process
                        is_primary = apqc_code in category_mapping.get("primary_processes", [])
                        relevance = 85 if is_primary else 65
                        coverage_pct = 80 if is_primary else 50

                        # Create new mapping
                        mapping = VendorProductAPQCMapping(
                            vendor_product_id=product.id,
                            apqc_process_id=apqc_id,
                            relevance_score=relevance,
                            confidence_level="high" if is_primary else "medium",
                            coverage_level=coverage_level,
                            coverage_percentage=coverage_pct,
                            automation_capability=70 if is_primary else 40,
                            out_of_box_fit=75 if is_primary else 45,
                            requires_customization=not is_primary,
                            customization_effort="low" if is_primary else "medium",
                            integration_complexity="low" if is_primary else "medium",
                            mapping_source="auto",
                            mapping_rationale=f"Auto-derived from vendor category {category} and capability mapping",
                            validation_status="pending",
                        )

                        db.session.add(mapping)
                        seeded += 1

                    except Exception as e:
                        current_app.logger.error(
                            f"Error creating mapping for {vendor_name} -> {apqc_code}: {e}"
                        )
                        errors += 1

            db.session.commit()
            current_app.logger.info(
                f"Vendor-APQC mapping seeding complete: {seeded} seeded, {skipped} skipped, {errors} errors"
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in vendor-APQC mapping seeding: {e}")
            return {"seeded": 0, "skipped": 0, "errors": 1, "error": str(e)}

        return {"seeded": seeded, "skipped": skipped, "errors": errors}

    def seed_vendors_from_catalogue(self) -> Dict:
        """
        Seed VendorOrganization and VendorProduct from vendor_catalogue.py.
        """
        from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct
        from app.seed_data.vendor_catalogue import VENDOR_CATALOGUE

        orgs_seeded = 0
        products_seeded = 0
        skipped = 0
        errors = 0

        try:
            for vendor_info in VENDOR_CATALOGUE:
                try:
                    vendor_name = vendor_info.get("name", "")

                    # Check if organization exists
                    existing_org = (
                        db.session.query(VendorOrganization)
                        .filter(VendorOrganization.name.ilike(f"%{vendor_name}%"))
                        .first()
                    )

                    if existing_org:
                        org = existing_org
                        skipped += 1
                    else:
                        # Create organization
                        org = VendorOrganization(
                            name=vendor_name,
                            description=vendor_info.get("description", ""),
                            website=vendor_info.get("website", ""),
                            headquarters=vendor_info.get("headquarters", ""),
                            founded_year=vendor_info.get("founded"),
                            is_public=vendor_info.get("publicCompany", False),
                            partnership_level=vendor_info.get("marketPosition", "NICHE").lower(),
                        )
                        db.session.add(org)
                        db.session.flush()  # Get ID
                        orgs_seeded += 1

                    # Check if product exists
                    existing_product = (
                        db.session.query(VendorProduct)
                        .filter(
                            VendorProduct.name.ilike(f"%{vendor_name}%"),
                            VendorProduct.vendor_organization_id == org.id,
                        )
                        .first()
                    )

                    if not existing_product:
                        # Create product
                        product = VendorProduct(
                            vendor_organization_id=org.id,
                            name=vendor_name,
                            description=vendor_info.get("description", ""),
                            deployment_model=vendor_info.get("deploymentModel", ["CLOUD"])[0]
                            if vendor_info.get("deploymentModel")
                            else "cloud",
                            licensing_model=vendor_info.get("licenseModel", "Subscription"),
                        )
                        db.session.add(product)
                        products_seeded += 1

                except Exception as e:
                    current_app.logger.error(
                        f"Error seeding vendor {vendor_info.get('name', 'unknown')}: {e}"
                    )
                    errors += 1

            db.session.commit()
            current_app.logger.info(
                f"Vendor seeding complete: {orgs_seeded} orgs, {products_seeded} products, {skipped} skipped, {errors} errors"
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in vendor seeding: {e}")
            return {
                "orgs_seeded": 0,
                "products_seeded": 0,
                "skipped": 0,
                "errors": 1,
                "error": str(e),
            }

        return {
            "orgs_seeded": orgs_seeded,
            "products_seeded": products_seeded,
            "skipped": skipped,
            "errors": errors,
        }

    def run_full_seed(self) -> Dict:
        """
        Run complete seeding: APQC processes, vendors, and mappings.
        """
        results = {}

        # 1. Seed APQC processes
        current_app.logger.info("Step 1: Seeding APQC processes...")
        results["apqc"] = self.seed_apqc_processes()

        # 2. Seed vendors from catalogue
        current_app.logger.info("Step 2: Seeding vendors from catalogue...")
        results["vendors"] = self.seed_vendors_from_catalogue()

        # 3. Seed vendor-APQC mappings
        current_app.logger.info("Step 3: Seeding vendor-APQC mappings...")
        results["mappings"] = self.seed_vendor_apqc_mappings()

        return results
