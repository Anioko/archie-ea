"""
Application Consolidation Planner Service

Generates comprehensive consolidation plans for duplicate/similar applications including:
- Dependency analysis
- Cost savings calculations
- Risk assessment
- Migration timeline with phases
- Resource requirements

Production-ready service with proper error handling and logging.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app import db
from app.exceptions import BusinessRuleError, DatabaseError, ValidationError
from app.models.application_portfolio import ApplicationComponent
from app.models.application_rationalization import ApplicationDependency
from app.models.enterprise_intelligence import ApplicationCost

logger = logging.getLogger(__name__)


class ConsolidationPlanner:
    """
    Service for generating comprehensive consolidation plans.

    Analyzes applications and creates detailed roadmaps for consolidation
    including financial analysis, risk assessment, and implementation timeline.
    """

    def __init__(self):
        self.current_year = datetime.utcnow().year

    def generate_plan(self, application_ids: List[int]) -> Dict[str, Any]:
        """
        Generate comprehensive consolidation plan for given applications.

        Args:
            application_ids: List of application IDs to consolidate

        Returns:
            Dict containing plan details, timeline, costs, risks, resources

        Raises:
            ValidationError: If application_ids invalid or empty
            DatabaseError: If database query fails
            BusinessRuleError: If consolidation not feasible
        """
        try:
            # Validate input
            if not application_ids or not isinstance(application_ids, list):
                raise ValidationError(
                    "Invalid application IDs",
                    user_message="Please provide a valid list of applications to consolidate",
                    error_code="INVALID_INPUT",
                )

            if len(application_ids) < 2:
                raise BusinessRuleError(
                    "Need at least 2 applications",
                    user_message="Consolidation requires at least 2 applications",
                    error_code="INSUFFICIENT_APPS",
                )

            logger.info(f"Generating consolidation plan for applications: {application_ids}")

            # Load applications with related data
            applications = self._load_applications(application_ids)

            if not applications:
                raise ValidationError(
                    "No applications found",
                    user_message="The specified applications could not be found",
                    error_code="APPS_NOT_FOUND",
                )

            # Analyze dependencies
            dependency_analysis = self._analyze_dependencies(application_ids)

            # Calculate cost savings
            cost_savings = self._calculate_cost_savings(applications)

            # Assess risks
            risk_assessment = self._assess_risks(applications, dependency_analysis)

            # Generate timeline
            timeline = self._generate_timeline(applications, risk_assessment)

            # Calculate resource requirements
            resources = self._calculate_resources(applications, risk_assessment)

            # Determine target application
            target_app = self._determine_target_application(applications)

            # Build comprehensive plan
            plan = {
                "generated_at": datetime.utcnow().isoformat(),
                "application_count": len(applications),
                "applications": [self._format_application_summary(app) for app in applications],
                "target_application": self._format_application_summary(target_app)
                if target_app
                else None,
                "executive_summary": self._generate_executive_summary(
                    applications, cost_savings, risk_assessment
                ),
                "dependencies": dependency_analysis,
                "cost_savings": cost_savings,
                "risks": risk_assessment,
                "timeline": timeline,
                "resources": resources,
                "recommendations": self._generate_recommendations(
                    applications, dependency_analysis, risk_assessment
                ),
                "success_criteria": self._define_success_criteria(),
                "next_steps": self._define_next_steps(timeline),
            }

            logger.info(
                f"Successfully generated consolidation plan for {len(applications)} applications"
            )
            return plan

        except (ValidationError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Error generating consolidation plan: {e}", exc_info=True)
            raise DatabaseError(
                f"Failed to generate consolidation plan: {str(e)}",
                user_message="An error occurred while generating the consolidation plan",
                error_code="PLAN_GENERATION_ERROR",
            )

    def _load_applications(self, application_ids: List[int]) -> List[ApplicationComponent]:
        """Load applications with related cost and dependency data."""
        try:
            apps = (
                ApplicationComponent.query.filter(ApplicationComponent.id.in_(application_ids))
                .options(joinedload(ApplicationComponent.cost_records))
                .all()
            )
            return apps
        except Exception as e:
            logger.error(f"Error loading applications: {e}", exc_info=True)
            raise DatabaseError(
                f"Failed to load applications: {str(e)}",
                user_message="Could not retrieve application data",
                error_code="DB_LOAD_ERROR",
            )

    def _analyze_dependencies(self, application_ids: List[int]) -> Dict[str, Any]:
        """Analyze application dependencies and their impact."""
        try:
            # Get dependencies where these apps are source or target
            source_deps = ApplicationDependency.query.filter(
                ApplicationDependency.source_app_id.in_(application_ids)
            ).all()

            target_deps = ApplicationDependency.query.filter(
                ApplicationDependency.target_app_id.in_(application_ids)
            ).all()

            # Count external dependencies (dependencies outside the consolidation group)
            external_upstream = [d for d in target_deps if d.source_app_id not in application_ids]

            external_downstream = [d for d in source_deps if d.target_app_id not in application_ids]

            internal_deps = [
                d
                for d in (source_deps + target_deps)
                if d.source_app_id in application_ids and d.target_app_id in application_ids
            ]

            # Identify critical dependencies
            critical_deps = [
                d
                for d in (external_upstream + external_downstream)
                if d.dependency_strength in ["critical", "high"]
                or d.business_criticality in ["mission_critical", "business_critical"]
            ]

            return {
                "total_dependencies": len(source_deps) + len(target_deps),
                "internal_dependencies": len(internal_deps),
                "external_upstream": len(external_upstream),
                "external_downstream": len(external_downstream),
                "critical_dependencies": len(critical_deps),
                "dependency_complexity": self._calculate_dependency_complexity(
                    len(external_upstream), len(external_downstream), len(critical_deps)
                ),
                "integration_changes_required": len(external_upstream) + len(external_downstream),
                "critical_dependency_details": [
                    {
                        "type": d.dependency_type,
                        "strength": d.dependency_strength,
                        "criticality": d.business_criticality,
                        "pattern": d.integration_pattern,
                        "frequency": d.frequency,
                    }
                    for d in critical_deps[:10]  # Limit to top 10
                ],
            }
        except Exception as e:
            logger.error(f"Error analyzing dependencies: {e}", exc_info=True)
            return {
                "total_dependencies": 0,
                "internal_dependencies": 0,
                "external_upstream": 0,
                "external_downstream": 0,
                "critical_dependencies": 0,
                "dependency_complexity": "unknown",
                "integration_changes_required": 0,
                "critical_dependency_details": [],
            }

    def _calculate_dependency_complexity(
        self, upstream: int, downstream: int, critical: int
    ) -> str:
        """Calculate overall dependency complexity rating."""
        total_external = upstream + downstream

        if critical >= 5 or total_external >= 20:
            return "very_high"
        elif critical >= 3 or total_external >= 10:
            return "high"
        elif critical >= 1 or total_external >= 5:
            return "medium"
        else:
            return "low"

    def _calculate_cost_savings(self, applications: List[ApplicationComponent]) -> Dict[str, Any]:
        """Calculate potential cost savings from consolidation."""
        try:
            total_costs = {
                "license": Decimal("0"),
                "subscription": Decimal("0"),
                "maintenance": Decimal("0"),
                "infrastructure": Decimal("0"),
                "support": Decimal("0"),
                "development": Decimal("0"),
                "training": Decimal("0"),
            }

            # Aggregate costs from all applications
            for app in applications:
                recent_costs = (
                    ApplicationCost.query.filter_by(application_id=app.id)
                    .filter(ApplicationCost.fiscal_year >= self.current_year - 1)
                    .all()
                )

                for cost in recent_costs:
                    if cost.license_cost:
                        total_costs["license"] += cost.license_cost
                    if cost.subscription_cost:
                        total_costs["subscription"] += cost.subscription_cost
                    if cost.maintenance_cost:
                        total_costs["maintenance"] += cost.maintenance_cost
                    if cost.infrastructure_cost:
                        total_costs["infrastructure"] += cost.infrastructure_cost
                    if cost.support_cost:
                        total_costs["support"] += cost.support_cost
                    if cost.development_cost:
                        total_costs["development"] += cost.development_cost
                    if cost.training_cost:
                        total_costs["training"] += cost.training_cost

            # Calculate average annual costs
            num_apps = len(applications)
            annual_costs = {k: float(v) / max(num_apps, 1) for k, v in total_costs.items()}

            # Estimate savings (consolidating N apps to 1 saves costs from N - 1 apps)
            # Apply realistic savings percentages
            savings_factors = {
                "license": 0.70,  # 70% reduction (keep 1, eliminate N - 1)
                "subscription": 0.70,  # 70% reduction
                "maintenance": 0.60,  # 60% reduction (still need support for consolidated app)
                "infrastructure": 0.50,  # 50% reduction (can decommission servers)
                "support": 0.40,  # 40% reduction (still need support staff)
                "development": 0.30,  # 30% reduction (still need dev, but less duplication)
                "training": 0.50,  # 50% reduction (single platform to train on)
            }

            estimated_savings = {
                category: annual_costs[category] * factor
                for category, factor in savings_factors.items()
            }

            total_annual_savings = sum(estimated_savings.values())
            total_current_cost = sum(annual_costs.values())

            # Three-year projection
            three_year_savings = total_annual_savings * 3

            # Calculate ROI (need implementation cost estimate)
            implementation_cost = self._estimate_implementation_cost(applications)
            roi_percentage = (
                ((three_year_savings - implementation_cost) / implementation_cost * 100)
                if implementation_cost > 0
                else 0
            )
            payback_months = (
                (implementation_cost / total_annual_savings * 12) if total_annual_savings > 0 else 0
            )

            return {
                "current_annual_cost": round(total_current_cost, 2),
                "estimated_annual_savings": round(total_annual_savings, 2),
                "three_year_savings": round(three_year_savings, 2),
                "savings_by_category": {k: round(v, 2) for k, v in estimated_savings.items()},
                "savings_percentage": round(
                    (total_annual_savings / total_current_cost * 100)
                    if total_current_cost > 0
                    else 0,
                    1,
                ),
                "implementation_cost": round(implementation_cost, 2),
                "roi_percentage": round(roi_percentage, 1),
                "payback_months": round(payback_months, 1),
                "break_even_date": (
                    datetime.utcnow() + timedelta(days=payback_months * 30)
                ).strftime("%Y-%m-%d"),
            }
        except Exception as e:
            logger.error(f"Error calculating cost savings: {e}", exc_info=True)
            return {
                "current_annual_cost": 0,
                "estimated_annual_savings": 0,
                "three_year_savings": 0,
                "savings_by_category": {},
                "savings_percentage": 0,
                "implementation_cost": 0,
                "roi_percentage": 0,
                "payback_months": 0,
                "break_even_date": datetime.utcnow().strftime("%Y-%m-%d"),
            }

    def _estimate_implementation_cost(self, applications: List[ApplicationComponent]) -> float:
        """Estimate cost of implementing consolidation."""
        # Base cost factors
        base_cost_per_app = 50000  # $50k base per app to consolidate
        data_migration_cost_per_app = 30000  # $30k for data migration
        integration_cost_per_app = 20000  # $20k for integration changes
        testing_cost_per_app = 15000  # $15k for testing

        num_apps = len(applications)

        # Calculate total implementation cost
        total_cost = (
            base_cost_per_app * num_apps
            + data_migration_cost_per_app * num_apps
            + integration_cost_per_app * num_apps
            + testing_cost_per_app * num_apps
        )

        # Add complexity multiplier for large user bases
        total_users = sum(app.user_count or 0 for app in applications)
        if total_users > 10000:
            total_cost *= 1.5
        elif total_users > 5000:
            total_cost *= 1.3
        elif total_users > 1000:
            total_cost *= 1.1

        return total_cost

    def _assess_risks(
        self, applications: List[ApplicationComponent], dependency_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess risks associated with consolidation."""
        risks = []

        # Data migration risks
        total_users = sum(app.user_count or 0 for app in applications)
        if total_users > 5000:
            risks.append(
                {
                    "category": "Data Migration",
                    "severity": "high",
                    "description": f"Large user base ({total_users:,} users) requires careful data migration planning",
                    "mitigation": "Phased migration approach with pilot group, extensive data validation, rollback plan",
                }
            )
        elif total_users > 1000:
            risks.append(
                {
                    "category": "Data Migration",
                    "severity": "medium",
                    "description": f"Moderate user base ({total_users:,} users) with data migration complexity",
                    "mitigation": "Staged migration with validation checkpoints, user communication plan",
                }
            )

        # Integration risks
        if dependency_analysis.get("critical_dependencies", 0) > 3:
            risks.append(
                {
                    "category": "Integration",
                    "severity": "high",
                    "description": f"{dependency_analysis['critical_dependencies']} critical dependencies must be maintained",
                    "mitigation": "Detailed integration testing, API compatibility layer, parallel run period",
                }
            )
        elif dependency_analysis.get("external_downstream", 0) > 5:
            risks.append(
                {
                    "category": "Integration",
                    "severity": "medium",
                    "description": f"{dependency_analysis['external_downstream']} downstream systems depend on these applications",
                    "mitigation": "Early stakeholder notification, API versioning, comprehensive integration testing",
                }
            )

        # Business continuity risks
        mission_critical = [
            app
            for app in applications
            if app.criticality == "mission_critical"
            or app.business_criticality in ["Critical", "High"]
        ]
        if mission_critical:
            risks.append(
                {
                    "category": "Business Continuity",
                    "severity": "critical",
                    "description": f"{len(mission_critical)} mission-critical applications in scope",
                    "mitigation": "Zero-downtime migration strategy, comprehensive failback plan, 24/7 support during transition",
                }
            )

        # Change management risks
        if len(applications) > 3:
            risks.append(
                {
                    "category": "Change Management",
                    "severity": "medium",
                    "description": f"Consolidating {len(applications)} applications requires significant user retraining",
                    "mitigation": "Comprehensive training program, user champions, extensive documentation, helpdesk support",
                }
            )

        # Technical risks
        tech_stacks = set()
        for app in applications:
            if hasattr(app, "technology_stack") and app.technology_stack:
                tech_stacks.add(app.technology_stack)

        if len(tech_stacks) > 2:
            risks.append(
                {
                    "category": "Technical Complexity",
                    "severity": "medium",
                    "description": f"Multiple technology stacks ({len(tech_stacks)}) increase migration complexity",
                    "mitigation": "Technical architecture review, proof of concept, phased technical migration",
                }
            )

        # Calculate overall risk score
        severity_scores = {"critical": 10, "high": 7, "medium": 4, "low": 2}
        overall_score = sum(severity_scores.get(r["severity"], 0) for r in risks)

        if overall_score >= 20:
            overall_rating = "critical"
        elif overall_score >= 14:
            overall_rating = "high"
        elif overall_score >= 8:
            overall_rating = "medium"
        else:
            overall_rating = "low"

        return {
            "overall_risk_rating": overall_rating,
            "risk_score": overall_score,
            "total_risks_identified": len(risks),
            "risks_by_severity": {
                "critical": len([r for r in risks if r["severity"] == "critical"]),
                "high": len([r for r in risks if r["severity"] == "high"]),
                "medium": len([r for r in risks if r["severity"] == "medium"]),
                "low": len([r for r in risks if r["severity"] == "low"]),
            },
            "risk_details": risks,
            "recommended_approach": self._recommend_approach(overall_rating),
        }

    def _recommend_approach(self, risk_rating: str) -> str:
        """Recommend consolidation approach based on risk."""
        approaches = {
            "critical": "Phased migration with extensive pilot testing, multiple go-live waves, and comprehensive fallback plans",
            "high": "Staged rollout with pilot group, validation gates, and parallel operation period",
            "medium": "Standard migration approach with testing phase and monitored rollout",
            "low": "Direct migration with standard testing and validation procedures",
        }
        return approaches.get(risk_rating, approaches["medium"])

    def _generate_timeline(
        self, applications: List[ApplicationComponent], risk_assessment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate implementation timeline with phases and milestones."""
        risk_rating = risk_assessment.get("overall_risk_rating", "medium")

        # Base durations (in weeks) adjusted by risk
        duration_multipliers = {"critical": 2.0, "high": 1.5, "medium": 1.0, "low": 0.8}

        multiplier = duration_multipliers.get(risk_rating, 1.0)

        # Define phases with durations
        phases = [
            {
                "name": "Discovery & Planning",
                "duration_weeks": int(6 * multiplier),
                "activities": [
                    "Detailed application analysis",
                    "Dependency mapping",
                    "Data migration strategy",
                    "Risk assessment & mitigation planning",
                    "Stakeholder alignment",
                    "Resource allocation",
                ],
            },
            {
                "name": "Design & Architecture",
                "duration_weeks": int(8 * multiplier),
                "activities": [
                    "Target architecture design",
                    "Integration architecture",
                    "Data migration design",
                    "Security & compliance review",
                    "Technical proof of concept",
                    "Cutover planning",
                ],
            },
            {
                "name": "Development & Configuration",
                "duration_weeks": int(12 * multiplier),
                "activities": [
                    "Target application configuration",
                    "Data migration scripts",
                    "Integration development",
                    "User interface customization",
                    "Automated testing development",
                    "Documentation creation",
                ],
            },
            {
                "name": "Testing & Validation",
                "duration_weeks": int(8 * multiplier),
                "activities": [
                    "Unit testing",
                    "Integration testing",
                    "User acceptance testing",
                    "Performance testing",
                    "Security testing",
                    "Cutover rehearsal",
                ],
            },
            {
                "name": "Migration & Cutover",
                "duration_weeks": int(4 * multiplier),
                "activities": [
                    "Data migration execution",
                    "Application cutover",
                    "Integration activation",
                    "User migration",
                    "Go-live support",
                    "Issue resolution",
                ],
            },
            {
                "name": "Stabilization & Optimization",
                "duration_weeks": int(6 * multiplier),
                "activities": [
                    "Post-go-live support",
                    "Performance optimization",
                    "User feedback incorporation",
                    "Documentation refinement",
                    "Knowledge transfer",
                    "Benefits realization tracking",
                ],
            },
        ]

        # Calculate dates
        start_date = datetime.utcnow() + timedelta(weeks=2)  # Start in 2 weeks
        current_date = start_date

        for phase in phases:
            phase["start_date"] = current_date.strftime("%Y-%m-%d")
            end_date = current_date + timedelta(weeks=phase["duration_weeks"])
            phase["end_date"] = end_date.strftime("%Y-%m-%d")
            phase["status"] = "planned"
            current_date = end_date

        total_duration_weeks = sum(p["duration_weeks"] for p in phases)
        total_duration_months = round(total_duration_weeks / 4.33, 1)

        # Key milestones
        milestones = [
            {
                "name": "Project Kickoff",
                "date": start_date.strftime("%Y-%m-%d"),
                "description": "Formal project initiation with all stakeholders",
            },
            {
                "name": "Architecture Approval",
                "date": (
                    start_date
                    + timedelta(weeks=phases[0]["duration_weeks"] + phases[1]["duration_weeks"])
                ).strftime("%Y-%m-%d"),
                "description": "Target architecture design approved by stakeholders",
            },
            {
                "name": "UAT Sign-off",
                "date": (
                    start_date + timedelta(weeks=sum(p["duration_weeks"] for p in phases[:4]))
                ).strftime("%Y-%m-%d"),
                "description": "User acceptance testing completed and signed off",
            },
            {
                "name": "Go-Live",
                "date": (
                    start_date + timedelta(weeks=sum(p["duration_weeks"] for p in phases[:5]))
                ).strftime("%Y-%m-%d"),
                "description": "Production cutover and go-live",
            },
            {
                "name": "Project Closure",
                "date": (start_date + timedelta(weeks=total_duration_weeks)).strftime("%Y-%m-%d"),
                "description": "Project formally closed with lessons learned documented",
            },
        ]

        return {
            "total_duration_weeks": total_duration_weeks,
            "total_duration_months": total_duration_months,
            "project_start_date": start_date.strftime("%Y-%m-%d"),
            "project_end_date": current_date.strftime("%Y-%m-%d"),
            "phases": phases,
            "milestones": milestones,
            "critical_path": "Discovery → Design → Development → Testing → Migration",
            "contingency_buffer": f"{int(total_duration_weeks * 0.15)} weeks",
        }

    def _calculate_resources(
        self, applications: List[ApplicationComponent], risk_assessment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate resource requirements for consolidation."""
        num_apps = len(applications)
        risk_rating = risk_assessment.get("overall_risk_rating", "medium")

        # Base team size adjustments
        risk_multipliers = {"critical": 1.5, "high": 1.3, "medium": 1.0, "low": 0.8}

        multiplier = risk_multipliers.get(risk_rating, 1.0)

        # Core team roles with FTE requirements
        team_structure = [
            {
                "role": "Program Manager",
                "fte": round(1.0 * multiplier, 1),
                "skills_required": [
                    "Program management",
                    "Stakeholder management",
                    "Risk management",
                ],
                "duration": "Full project duration",
            },
            {
                "role": "Solution Architect",
                "fte": round(1.0 * multiplier, 1),
                "skills_required": [
                    "Enterprise architecture",
                    "Integration design",
                    "Technology strategy",
                ],
                "duration": "Discovery through Testing phases",
            },
            {
                "role": "Business Analyst",
                "fte": round(2.0 * multiplier, 1),
                "skills_required": ["Requirements analysis", "Process mapping", "User stories"],
                "duration": "Discovery through UAT phases",
            },
            {
                "role": "Application Developer",
                "fte": round(3.0 * multiplier * (num_apps / 2), 1),
                "skills_required": [
                    "Application development",
                    "API integration",
                    "Database design",
                ],
                "duration": "Design through Migration phases",
            },
            {
                "role": "Data Migration Specialist",
                "fte": round(2.0 * multiplier, 1),
                "skills_required": ["ETL", "Data quality", "SQL", "Data mapping"],
                "duration": "Design through Stabilization phases",
            },
            {
                "role": "QA Engineer",
                "fte": round(2.0 * multiplier, 1),
                "skills_required": ["Test automation", "UAT coordination", "Quality assurance"],
                "duration": "Development through Migration phases",
            },
            {
                "role": "Change Management Lead",
                "fte": round(1.0 * multiplier, 1),
                "skills_required": ["Change management", "Training", "Communication"],
                "duration": "Planning through Stabilization phases",
            },
            {
                "role": "Technical Lead",
                "fte": round(1.0 * multiplier, 1),
                "skills_required": ["Technical leadership", "DevOps", "Infrastructure"],
                "duration": "Design through Stabilization phases",
            },
        ]

        total_fte = sum(member["fte"] for member in team_structure)

        # Budget estimation
        avg_rate_per_fte_month = 15000  # $15k per FTE per month (blended rate)
        duration_months = 10 * multiplier  # Approximate from timeline

        labor_cost = total_fte * avg_rate_per_fte_month * duration_months
        software_tools_cost = 50000  # Migration tools, testing tools, etc.
        infrastructure_cost = 30000  # Temporary infrastructure for testing
        contingency = (labor_cost + software_tools_cost + infrastructure_cost) * 0.15

        total_budget = labor_cost + software_tools_cost + infrastructure_cost + contingency

        return {
            "team_structure": team_structure,
            "total_fte": round(total_fte, 1),
            "peak_team_size": round(total_fte * 1.2, 1),  # Peak during development/testing
            "estimated_budget": {
                "labor_cost": round(labor_cost, 2),
                "software_tools": round(software_tools_cost, 2),
                "infrastructure": round(infrastructure_cost, 2),
                "contingency": round(contingency, 2),
                "total": round(total_budget, 2),
            },
            "key_skills_required": [
                "Enterprise Architecture",
                "Application Development",
                "Data Migration",
                "Integration Development",
                "Change Management",
                "Program Management",
                "Quality Assurance",
            ],
            "vendor_support_recommended": risk_rating in ["critical", "high"],
        }

    def _determine_target_application(
        self, applications: List[ApplicationComponent]
    ) -> Optional[ApplicationComponent]:
        """Determine which application should be the consolidation target."""
        if not applications:
            return None

        # Score each application
        scores = {}
        for app in applications:
            score = 0

            # Prefer newer applications
            if hasattr(app, "deployment_status") and app.deployment_status == "production":
                score += 10

            # Prefer more modern architectures (cloud/SaaS)
            if hasattr(app, "deployment_model"):
                if app.deployment_model in ["cloud", "saas"]:
                    score += 15
                elif app.deployment_model == "hybrid":
                    score += 10

            # Prefer higher user counts (more established)
            if app.user_count:
                score += min(app.user_count / 100, 20)

            # Prefer higher criticality
            if hasattr(app, "business_criticality"):
                if app.business_criticality == "Critical":
                    score += 15
                elif app.business_criticality == "High":
                    score += 10

            # Prefer higher business value
            if hasattr(app, "business_value"):
                if app.business_value == "high":
                    score += 10
                elif app.business_value == "medium":
                    score += 5

            scores[app.id] = score

        # Return application with highest score
        target_id = max(scores, key=scores.get)
        return next(app for app in applications if app.id == target_id)

    def _format_application_summary(self, app: ApplicationComponent) -> Dict[str, Any]:
        """Format application data for plan output."""
        return {
            "id": app.id,
            "name": app.name,
            "description": app.description or "No description available",
            "type": app.application_type or "Unknown",
            "deployment_model": app.deployment_model or "Unknown",
            "criticality": app.business_criticality or app.criticality or "Unknown",
            "user_count": app.user_count or 0,
            "business_domain": app.business_domain or "Unknown",
        }

    def _generate_executive_summary(
        self,
        applications: List[ApplicationComponent],
        cost_savings: Dict[str, Any],
        risk_assessment: Dict[str, Any],
    ) -> str:
        """Generate executive summary of consolidation plan."""
        num_apps = len(applications)
        savings = cost_savings.get("estimated_annual_savings", 0)
        three_year = cost_savings.get("three_year_savings", 0)
        risk = risk_assessment.get("overall_risk_rating", "medium")

        summary = (
            f"This consolidation plan proposes merging {num_apps} similar applications into a single "
            f"unified solution. The consolidation is projected to deliver annual cost savings of "
            f"${savings:,.0f}, totaling ${three_year:,.0f} over three years. "
            f"The overall risk rating is {risk.upper()}, requiring appropriate mitigation strategies. "
            f"Implementation will require a phased approach with careful attention to dependency management, "
            f"data migration, and user adoption. The expected ROI is {cost_savings.get('roi_percentage', 0):.1f}% "
            f"with a payback period of {cost_savings.get('payback_months', 0):.1f} months."
        )

        return summary

    def _generate_recommendations(
        self,
        applications: List[ApplicationComponent],
        dependency_analysis: Dict[str, Any],
        risk_assessment: Dict[str, Any],
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = [
            "Establish a dedicated program management office (PMO) to oversee the consolidation",
            "Create a detailed data migration strategy with comprehensive data quality assessment",
            "Develop a comprehensive training program for all affected users",
            "Implement a phased rollout approach with pilot groups before full deployment",
        ]

        # Add risk-specific recommendations
        if risk_assessment.get("overall_risk_rating") in ["critical", "high"]:
            recommendations.append(
                "Engage external expertise for risk mitigation and independent validation"
            )
            recommendations.append(
                "Establish a comprehensive rollback plan with clearly defined trigger points"
            )

        # Add dependency-specific recommendations
        if dependency_analysis.get("critical_dependencies", 0) > 3:
            recommendations.append(
                "Conduct detailed integration testing for all critical dependencies"
            )
            recommendations.append(
                "Establish an API compatibility layer to minimize integration disruption"
            )

        # Add cost-specific recommendations
        recommendations.append(
            "Track and report on benefits realization monthly to ensure ROI targets are met"
        )
        recommendations.append(
            "Decommission retired applications promptly to realize full cost savings"
        )

        return recommendations

    def _define_success_criteria(self) -> List[Dict[str, str]]:
        """Define measurable success criteria."""
        return [
            {
                "criterion": "User Adoption",
                "target": "95% of users successfully migrated within planned timeframe",
                "measurement": "User login metrics and support ticket volume",
            },
            {
                "criterion": "System Performance",
                "target": "Response times within 10% of baseline with increased user load",
                "measurement": "Application performance monitoring (APM) metrics",
            },
            {
                "criterion": "Data Integrity",
                "target": "100% data accuracy with zero data loss",
                "measurement": "Data validation reports and reconciliation",
            },
            {
                "criterion": "Integration Stability",
                "target": "All critical integrations functioning with 99.9% uptime",
                "measurement": "Integration monitoring and error rates",
            },
            {
                "criterion": "Cost Savings",
                "target": "Achieve planned cost savings within 3 months of go-live",
                "measurement": "Actual vs. planned cost tracking",
            },
            {
                "criterion": "User Satisfaction",
                "target": "User satisfaction score of 4.0 or higher (out of 5.0)",
                "measurement": "User surveys at 30, 60, and 90 days post go-live",
            },
        ]

    def _define_next_steps(self, timeline: Dict[str, Any]) -> List[Dict[str, str]]:
        """Define immediate next steps."""
        return [
            {
                "step": "1. Secure Executive Sponsorship",
                "action": "Present plan to executive leadership for approval and resource commitment",
                "timeline": "Within 2 weeks",
                "owner": "Program Manager",
            },
            {
                "step": "2. Assemble Project Team",
                "action": "Recruit and onboard core team members per resource plan",
                "timeline": "Weeks 2 - 4",
                "owner": "Program Manager / HR",
            },
            {
                "step": "3. Conduct Detailed Discovery",
                "action": "Deep dive into application details, dependencies, and data structures",
                "timeline": f"Weeks 4-{4 + timeline.get('phases', [{}])[0].get('duration_weeks', 6)}",
                "owner": "Solution Architect / Business Analysts",
            },
            {
                "step": "4. Engage Stakeholders",
                "action": "Identify and engage all affected stakeholders, establish communication plan",
                "timeline": "Weeks 2 - 6",
                "owner": "Change Management Lead",
            },
            {
                "step": "5. Establish Governance",
                "action": "Set up steering committee, define decision-making processes, establish RAID log",
                "timeline": "Week 4",
                "owner": "Program Manager",
            },
        ]
