"""
Technology Roadmap Service

Plans and manages technology evolution and modernization:
- Technology gap analysis
- Modernization roadmap planning
- Technology lifecycle management
- Innovation opportunity assessment
- Technology investment planning
"""

from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_

from app import db
from .decorators import transactional


class TechnologyRoadmapService:
    """
    Service for technology roadmap planning and management.

    Provides comprehensive technology planning:
    - Technology gap analysis and assessment
    - Modernization roadmap development
    - Technology lifecycle management
    - Innovation opportunity identification
    - Technology investment optimization
    """

    def __init__(self):
        pass

    @transactional
    def analyze_technology_portfolio(self, include_innovation: bool = True) -> Dict:
        """
        Comprehensive technology portfolio analysis.

        Args:
            include_innovation: Include innovation opportunity analysis

        Returns:
            Dict with technology roadmap analysis results
        """
        # Get all technology components
        technology_components = self._get_technology_components()

        # Analyze each technology component
        tech_analyses = []
        for component in technology_components:
            analysis = self._analyze_technology_component(component, include_innovation)
            tech_analyses.append(analysis)

        # Sort by modernization priority (highest first)
        tech_analyses.sort(key=lambda x: x["modernization_priority_score"], reverse=True)

        # Categorize by priority levels
        critical_tech = [t for t in tech_analyses if t["modernization_level"] == "CRITICAL"]
        high_tech = [t for t in tech_analyses if t["modernization_level"] == "HIGH"]
        medium_tech = [t for t in tech_analyses if t["modernization_level"] == "MEDIUM"]
        low_tech = [t for t in tech_analyses if t["modernization_level"] == "LOW"]

        # Calculate portfolio metrics
        portfolio_metrics = self._calculate_portfolio_metrics(tech_analyses)

        # Generate roadmap phases
        roadmap_phases = self._generate_roadmap_phases(tech_analyses)

        # Generate technology recommendations
        recommendations = self._generate_technology_recommendations(tech_analyses)

        return {
            "total_components": len(technology_components),
            "technology_analyses": tech_analyses,
            "critical_technology": critical_tech,
            "high_technology": high_tech,
            "medium_technology": medium_tech,
            "low_technology": low_tech,
            "portfolio_metrics": portfolio_metrics,
            "roadmap_phases": roadmap_phases,
            "recommendations": recommendations,
            "analysis_date": datetime.utcnow().isoformat(),
        }

    def _get_technology_components(self) -> List[Dict]:
        """Get all technology components from the database."""
        try:
            components = []

            # Get from application components
            from app.models.application_layer import ApplicationComponent

            applications = ApplicationComponent.query.filter(
                ApplicationComponent.deployment_status.in_(
                    ["production", "Production", "Implementing"]
                )
            ).all()

            for app in applications:
                # Extract technology stack information
                tech_stack = app.technology_stack or []
                for tech in tech_stack:
                    components.append(
                        {
                            "id": f"app_{app.id}_{tech}",
                            "name": tech,
                            "type": "ApplicationTechnology",
                            "application_id": app.id,
                            "application_name": app.name,
                            "deployment_status": app.deployment_status,
                            "age_years": getattr(app, "age_years", 0),
                            "platform_status": getattr(app, "platform_status", "supported"),
                            "technology_category": self._categorize_technology(tech),
                            "strategic_importance": self._assess_tech_importance(tech, app),
                            "modernization_need": self._assess_modernization_need(tech, app),
                        }
                    )

            # Get from infrastructure components if available
            try:
                from app.models.platform_models import PlatformConfiguration

                platforms = PlatformConfiguration.query.all()
                for platform in platforms:
                    components.append(
                        {
                            "id": f"platform_{platform.id}",
                            "name": platform.name,
                            "type": "PlatformTechnology",
                            "platform_id": platform.id,
                            "technology_category": "Infrastructure",
                            "strategic_importance": getattr(
                                platform, "strategic_importance", "medium"
                            ),
                            "modernization_need": getattr(platform, "modernization_need", "low"),
                        }
                    )
            except Exception as e:
                print(f"Error getting platforms: {e}")

            return components
        except Exception as e:
            print(f"Error getting technology components: {e}")
            return []

    def _categorize_technology(self, technology: str) -> str:
        """Categorize technology based on its name/type."""

        tech_lower = technology.lower()

        # Programming languages
        if any(
            lang in tech_lower
            for lang in ["java", "python", "javascript", "c#", "php", "ruby", "go"]
        ):
            return "Programming Language"

        # Databases
        if any(
            db in tech_lower
            for db in ["mysql", "postgresql", "oracle", "sql server", "mongodb", "redis"]
        ):
            return "Database"

        # Web frameworks
        if any(
            framework in tech_lower
            for framework in ["react", "angular", "vue", "django", "flask", "spring"]
        ):
            return "Web Framework"

        # Cloud platforms
        if any(cloud in tech_lower for cloud in ["aws", "azure", "gcp", "heroku"]):
            return "Cloud Platform"

        # Container technologies
        if any(container in tech_lower for container in ["docker", "kubernetes", "openshift"]):
            return "Container Technology"

        # Message queues
        if any(queue in tech_lower for queue in ["rabbitmq", "kafka", "activemq"]):
            return "Message Queue"

        # Default
        return "Other"

    def _assess_tech_importance(self, technology: str, application) -> str:
        """Assess strategic importance of technology."""

        # Check if application is critical
        app_importance = getattr(application, "strategic_importance", "medium")
        if app_importance == "critical":
            return "critical"
        elif app_importance == "high":
            return "high"

        # Check if technology is core infrastructure
        core_tech = ["database", "application server", "web server", "message queue"]
        if any(core in technology.lower() for core in core_tech):
            return "high"

        return "medium"

    def _assess_modernization_need(self, technology: str, application) -> str:
        """Assess modernization need for technology."""

        # Check application age
        age = getattr(application, "age_years", 0)
        if age > 15:
            return "critical"
        elif age > 10:
            return "high"
        elif age > 5:
            return "medium"

        # Check platform status
        platform_status = getattr(application, "platform_status", "supported")
        if platform_status == "unsupported":
            return "critical"
        elif platform_status == "deprecated":
            return "high"

        # Check technology obsolescence
        obsolete_tech = ["flash", "silverlight", "ie6", "old framework"]
        if any(old in technology.lower() for old in obsolete_tech):
            return "critical"

        return "low"

    def _analyze_technology_component(self, component: Dict, include_innovation: bool) -> Dict:
        """Analyze modernization opportunities for a technology component."""

        # Calculate different modernization factors
        age_score = self._calculate_age_score(component)
        obsolescence_score = self._calculate_obsolescence_score(component)
        support_score = self._calculate_support_score(component)
        performance_score = self._calculate_performance_score(component)
        innovation_score = self._calculate_innovation_score(component) if include_innovation else 0

        # Calculate overall modernization priority score (0 - 100)
        total_score = (
            age_score + obsolescence_score + support_score + performance_score + innovation_score
        )

        # Determine modernization level
        if total_score >= 80:
            modernization_level = "CRITICAL"
        elif total_score >= 60:
            modernization_level = "HIGH"
        elif total_score >= 40:
            modernization_level = "MEDIUM"
        else:
            modernization_level = "LOW"

        # Identify specific modernization factors
        modernization_factors = []
        if age_score >= 20:
            modernization_factors.append("AGING_TECHNOLOGY")
        if obsolescence_score >= 15:
            modernization_factors.append("OBSOLETE_TECHNOLOGY")
        if support_score >= 15:
            modernization_factors.append("UNSUPPORTED_PLATFORM")
        if performance_score >= 15:
            modernization_factors.append("PERFORMANCE_ISSUES")
        if innovation_score >= 10 and include_innovation:
            modernization_factors.append("INNOVATION_OPPORTUNITY")

        # Estimate modernization needs
        modernization_needs = self._estimate_modernization_needs(component, total_score)

        return {
            "component_id": component["id"],
            "component_name": component["name"],
            "component_type": component["type"],
            "technology_category": component["technology_category"],
            "application_name": component.get("application_name", ""),
            "strategic_importance": component["strategic_importance"],
            "age_score": age_score,
            "obsolescence_score": obsolescence_score,
            "support_score": support_score,
            "performance_score": performance_score,
            "innovation_score": innovation_score,
            "modernization_priority_score": total_score,
            "modernization_level": modernization_level,
            "modernization_factors": modernization_factors,
            "modernization_needs": modernization_needs,
            "modernization_assessment": self._generate_modernization_assessment(
                component, modernization_factors, total_score
            ),
        }

    def _calculate_age_score(self, component: Dict) -> int:
        """Calculate age-based modernization score (0 - 25 points)."""

        age = component.get("age_years", 0)

        if age >= 15:
            return 25  # Very old - critical modernization needed
        elif age >= 10:
            return 20  # Old - high modernization needed
        elif age >= 5:
            return 15  # Moderate age - medium modernization
        elif age >= 2:
            return 10  # Recent - low modernization
        else:
            return 5  # New - minimal modernization

    def _calculate_obsolescence_score(self, component: Dict) -> int:
        """Calculate obsolescence score (0 - 20 points)."""

        tech_name = component["name"].lower()

        # Check for known obsolete technologies
        obsolete_tech = ["flash", "silverlight", "ie6", "activex", "vb6", "classic asp"]
        if any(old in tech_name for old in obsolete_tech):
            return 20  # Obsolete technology

        # Check for deprecated frameworks
        deprecated_tech = ["angularjs", "jquery 1.x", "bootstrap 3"]
        if any(deprecated in tech_name for deprecated in deprecated_tech):
            return 15  # Deprecated technology

        # Check for older versions
        if any(version in tech_name for version in ["1.x", "2.x", "3.x"]):
            return 10  # Older version

        return 0  # Current technology

    def _calculate_support_score(self, component: Dict) -> int:
        """Calculate support-based modernization score (0 - 20 points)."""

        platform_status = component.get("platform_status", "supported")

        if platform_status == "unsupported":
            return 20  # No support - critical modernization
        elif platform_status == "deprecated":
            return 15  # Deprecated - high modernization
        elif platform_status == "limited":
            return 10  # Limited support - medium modernization
        else:
            return 5  # Full support - minimal modernization

    def _calculate_performance_score(self, component: Dict) -> int:
        """Calculate performance-based modernization score (0 - 20 points)."""

        # This would be based on actual performance metrics
        # For now, use heuristics based on technology type

        tech_category = component["technology_category"]
        tech_name = component["name"].lower()

        # Known performance issues
        performance_issues = ["old database", "legacy framework", "monolithic architecture"]
        if any(issue in tech_name for issue in performance_issues):
            return 15  # Performance issues identified

        # Database performance concerns
        if tech_category == "Database" and "mysql" in tech_name:
            return 10  # Potential performance concerns

        return 0  # No known performance issues

    def _calculate_innovation_score(self, component: Dict) -> int:
        """Calculate innovation opportunity score (0 - 15 points)."""

        tech_name = component["name"].lower()
        tech_category = component["technology_category"]

        # Check for modern, innovative technologies
        innovative_tech = ["kubernetes", "microservices", "serverless", "ai/ml", "blockchain"]
        if any(innovative in tech_name for innovative in innovative_tech):
            return 15  # High innovation opportunity

        # Check for emerging categories
        emerging_categories = ["AI/ML", "Blockchain", "IoT", "Edge Computing"]
        if tech_category in emerging_categories:
            return 10  # Emerging technology

        # Check for cloud-native technologies
        cloud_native = ["docker", "kubernetes", "serverless", "lambda"]
        if any(cloud in tech_name for cloud in cloud_native):
            return 10  # Cloud-native opportunity

        return 0  # No specific innovation opportunity

    def _estimate_modernization_needs(self, component: Dict, score: int) -> Dict:
        """Estimate modernization needs for the component."""

        # Base modernization estimation
        if score >= 80:
            base_cost = 500000  # $500k for critical modernization
            complexity_multiplier = 1.5
        elif score >= 60:
            base_cost = 250000  # $250k for high modernization
            complexity_multiplier = 1.2
        elif score >= 40:
            base_cost = 100000  # $100k for medium modernization
            complexity_multiplier = 1.0
        else:
            base_cost = 50000  # $50k for low modernization
            complexity_multiplier = 0.8

        # Adjust for strategic importance
        if component["strategic_importance"] == "critical":
            complexity_multiplier *= 1.3
        elif component["strategic_importance"] == "low":
            complexity_multiplier *= 0.8

        estimated_cost = base_cost * complexity_multiplier

        # Timeframe estimation
        if score >= 80:
            timeframe = "12 - 18 months"
        elif score >= 60:
            timeframe = "6 - 12 months"
        elif score >= 40:
            timeframe = "3 - 6 months"
        else:
            timeframe = "1 - 3 months"

        return {
            "estimated_cost": estimated_cost,
            "currency": "USD",
            "timeframe": timeframe,
            "modernization_type": "REPLACE"
            if score >= 70
            else "UPGRADE"
            if score >= 50
            else "OPTIMIZE",
            "complexity": "HIGH"
            if complexity_multiplier > 1.2
            else "MEDIUM"
            if complexity_multiplier > 1.0
            else "LOW",
        }

    def _generate_modernization_assessment(self, component: Dict, factors: List, score: int) -> str:
        """Generate modernization assessment for the component."""

        if score >= 80:
            return f"CRITICAL: {component['name']} requires immediate modernization - multiple critical issues identified"
        elif score >= 60:
            return (
                f"HIGH: {component['name']} has significant modernization needs requiring attention"
            )
        elif score >= 40:
            return f"MEDIUM: {component['name']} has moderate modernization opportunities that should be considered"
        else:
            return f"LOW: {component['name']} is current with minimal modernization needs"

    def _calculate_portfolio_metrics(self, tech_analyses: List[Dict]) -> Dict:
        """Calculate portfolio-level technology metrics."""

        total_components = len(tech_analyses)
        critical_count = len([t for t in tech_analyses if t["modernization_level"] == "CRITICAL"])
        high_count = len([t for t in tech_analyses if t["modernization_level"] == "HIGH"])

        # Technology category distribution
        category_counts = {}
        for tech in tech_analyses:
            category = tech["technology_category"]
            category_counts[category] = category_counts.get(category, 0) + 1

        # Modernization factor distribution
        aging_count = len(
            [t for t in tech_analyses if "AGING_TECHNOLOGY" in t["modernization_factors"]]
        )
        obsolete_count = len(
            [t for t in tech_analyses if "OBSOLETE_TECHNOLOGY" in t["modernization_factors"]]
        )
        unsupported_count = len(
            [t for t in tech_analyses if "UNSUPPORTED_PLATFORM" in t["modernization_factors"]]
        )

        # Average scores
        avg_age_score = (
            sum(t["age_score"] for t in tech_analyses) / total_components
            if total_components > 0
            else 0
        )
        avg_obsolescence_score = (
            sum(t["obsolescence_score"] for t in tech_analyses) / total_components
            if total_components > 0
            else 0
        )
        avg_support_score = (
            sum(t["support_score"] for t in tech_analyses) / total_components
            if total_components > 0
            else 0
        )

        return {
            "total_components": total_components,
            "critical_modernizations": critical_count,
            "high_modernizations": high_count,
            "technology_categories": category_counts,
            "aging_technologies": aging_count,
            "obsolete_technologies": obsolete_count,
            "unsupported_platforms": unsupported_count,
            "average_age_score": round(avg_age_score, 1),
            "average_obsolescence_score": round(avg_obsolescence_score, 1),
            "average_support_score": round(avg_support_score, 1),
            "portfolio_modernization_level": "HIGH"
            if critical_count > 5
            else "MEDIUM"
            if high_count > 10
            else "LOW",
        }

    def _generate_roadmap_phases(self, tech_analyses: List[Dict]) -> List[Dict]:
        """Generate technology roadmap phases."""

        phases = []

        # Phase 1: Critical modernizations (0 - 6 months)
        critical_tech = [t for t in tech_analyses if t["modernization_level"] == "CRITICAL"]
        if critical_tech:
            phases.append(
                {
                    "phase": "Phase 1",
                    "name": "Critical Modernizations",
                    "timeframe": "0 - 6 months",
                    "components": critical_tech,
                    "total_cost": sum(
                        t["modernization_needs"]["estimated_cost"] for t in critical_tech
                    ),
                    "priority": "CRITICAL",
                    "description": "Immediate modernization of critical and obsolete technologies",
                }
            )

        # Phase 2: High priority modernizations (6 - 12 months)
        high_tech = [t for t in tech_analyses if t["modernization_level"] == "HIGH"]
        if high_tech:
            phases.append(
                {
                    "phase": "Phase 2",
                    "name": "High Priority Modernizations",
                    "timeframe": "6 - 12 months",
                    "components": high_tech,
                    "total_cost": sum(
                        t["modernization_needs"]["estimated_cost"] for t in high_tech
                    ),
                    "priority": "HIGH",
                    "description": "Modernization of aging and deprecated technologies",
                }
            )

        # Phase 3: Medium priority improvements (12 - 18 months)
        medium_tech = [t for t in tech_analyses if t["modernization_level"] == "MEDIUM"]
        if medium_tech:
            phases.append(
                {
                    "phase": "Phase 3",
                    "name": "Technology Improvements",
                    "timeframe": "12 - 18 months",
                    "components": medium_tech,
                    "total_cost": sum(
                        t["modernization_needs"]["estimated_cost"] for t in medium_tech
                    ),
                    "priority": "MEDIUM",
                    "description": "Performance improvements and technology optimizations",
                }
            )

        # Phase 4: Innovation opportunities (18 - 24 months)
        innovation_tech = [
            t for t in tech_analyses if "INNOVATION_OPPORTUNITY" in t["modernization_factors"]
        ]
        if innovation_tech:
            phases.append(
                {
                    "phase": "Phase 4",
                    "name": "Innovation Initiatives",
                    "timeframe": "18 - 24 months",
                    "components": innovation_tech,
                    "total_cost": sum(
                        t["modernization_needs"]["estimated_cost"] for t in innovation_tech
                    ),
                    "priority": "LOW",
                    "description": "Adoption of innovative and emerging technologies",
                }
            )

        return phases

    def _generate_technology_recommendations(self, tech_analyses: List[Dict]) -> List[Dict]:
        """Generate technology modernization recommendations."""

        recommendations = []

        # Critical modernizations
        critical_tech = [t for t in tech_analyses if t["modernization_level"] == "CRITICAL"][:5]
        for tech in critical_tech:
            recommendations.append(
                {
                    "type": "IMMEDIATE_MODERNIZATION",
                    "priority": "CRITICAL",
                    "technology": tech["component_name"],
                    "modernization_level": tech["modernization_level"],
                    "modernization_factors": tech["modernization_factors"],
                    "recommendation": self._get_modernization_recommendation(tech),
                    "timeframe": tech["modernization_needs"]["timeframe"],
                    "estimated_cost": tech["modernization_needs"]["estimated_cost"],
                    "business_impact": "HIGH"
                    if tech["strategic_importance"] == "critical"
                    else "MEDIUM",
                }
            )

        # Technology consolidation opportunities
        category_counts = {}
        for tech in tech_analyses:
            category = tech["technology_category"]
            category_counts[category] = category_counts.get(category, 0) + 1

        consolidation_opps = [(cat, count) for cat, count in category_counts.items() if count > 3]
        if consolidation_opps:
            recommendations.append(
                {
                    "type": "TECHNOLOGY_CONSOLIDATION",
                    "priority": "MEDIUM",
                    "technology": f"{len(consolidation_opps)} technology categories",
                    "modernization_level": "MEDIUM",
                    "modernization_factors": ["CONSOLIDATION_OPPORTUNITY"],
                    "recommendation": "Consolidate redundant technologies to reduce complexity and maintenance overhead",
                    "timeframe": "6 - 12 months",
                    "estimated_cost": "SAVINGS",
                    "business_impact": "HIGH",
                }
            )

        # Innovation opportunities
        innovation_tech = [
            t for t in tech_analyses if "INNOVATION_OPPORTUNITY" in t["modernization_factors"]
        ]
        if innovation_tech:
            recommendations.append(
                {
                    "type": "INNOVATION_ADOPTION",
                    "priority": "LOW",
                    "technology": f"{len(innovation_tech)} technologies",
                    "modernization_level": "LOW",
                    "modernization_factors": ["INNOVATION_OPPORTUNITY"],
                    "recommendation": "Adopt innovative technologies to gain competitive advantage",
                    "timeframe": "12 - 24 months",
                    "estimated_cost": sum(
                        t["modernization_needs"]["estimated_cost"] for t in innovation_tech
                    ),
                    "business_impact": "HIGH",
                }
            )

        return recommendations

    def _get_modernization_recommendation(self, tech: Dict) -> str:
        """Get specific modernization recommendation for a technology."""

        factors = tech["modernization_factors"]

        if "AGING_TECHNOLOGY" in factors:
            return f"Replace {tech['component_name']} - aging technology requiring modernization"
        elif "OBSOLETE_TECHNOLOGY" in factors:
            return f"Replace {tech['component_name']} - obsolete technology with no vendor support"
        elif "UNSUPPORTED_PLATFORM" in factors:
            return (
                f"Migrate {tech['component_name']} - unsupported platform creating security risks"
            )
        elif "PERFORMANCE_ISSUES" in factors:
            return f"Upgrade {tech['component_name']} - performance issues affecting business operations"
        elif "INNOVATION_OPPORTUNITY" in factors:
            return (
                f"Adopt {tech['component_name']} - innovation opportunity for competitive advantage"
            )
        else:
            return f"Monitor {tech['component_name']} - continuous technology improvement needed"
