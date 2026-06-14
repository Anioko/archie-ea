"""
Business Context Service
Captures and analyzes business drivers, strategic objectives, constraints, and success metrics
for architecture planning and capability-based decision making.
"""

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.services.core.cache_service import CacheService


class CapabilityMaturity(Enum):
    """Capability maturity levels"""

    NONE = "none"
    INITIAL = "initial"
    REPEATABLE = "repeatable"
    DEFINED = "defined"
    MANAGED = "managed"
    OPTIMIZING = "optimizing"


class StrategicImportance(Enum):
    """Strategic importance levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BusinessDriver:
    """Business driver model"""

    id: str
    name: str
    description: str
    category: str  # market, regulatory, technology, operational, strategic
    impact_level: str  # high, medium, low
    timeframe: str  # immediate, short_term, medium_term, long_term
    stakeholders: List[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class StrategicObjective:
    """Strategic objective model"""

    id: str
    name: str
    description: str
    kpis: List[Dict[str, Any]]  # metric, target, current, unit
    priority: str  # high, medium, low
    timeframe: str
    owner: str
    dependencies: List[str]  # IDs of dependent objectives
    created_at: datetime
    updated_at: datetime


@dataclass
class BusinessConstraint:
    """Business constraint model"""

    id: str
    name: str
    description: str
    type: str  # regulatory, budgetary, technical, organizational, timeline
    impact: str  # blocker, significant, moderate, minor
    mitigation_strategy: str
    created_at: datetime
    updated_at: datetime


@dataclass
class SuccessMetric:
    """Success metric model"""

    id: str
    name: str
    description: str
    metric_type: str  # kpi, kqi, kci
    current_value: float
    target_value: float
    unit: str
    measurement_frequency: str
    owner: str
    created_at: datetime
    updated_at: datetime


@dataclass
class BusinessCapability:
    """Business capability model"""

    id: str
    name: str
    description: str
    domain: str
    level: int  # 1 - 3 in capability hierarchy
    parent_capability: Optional[str]  # parent capability ID
    maturity: CapabilityMaturity
    strategic_importance: StrategicImportance
    business_value: str
    current_state: str
    target_state: str
    gaps: List[str]
    dependencies: List[str]  # dependent capability IDs
    created_at: datetime
    updated_at: datetime


@dataclass
class BusinessContext:
    """Complete business context model"""

    id: str
    name: str
    description: str
    organization: str
    industry: str
    drivers: List[BusinessDriver]
    objectives: List[StrategicObjective]
    constraints: List[BusinessConstraint]
    metrics: List[SuccessMetric]
    capabilities: List[BusinessCapability]
    capability_heatmap: Dict[str, Any]
    problem_statement: str
    scope_definition: str
    created_at: datetime
    updated_at: datetime


class BusinessContextService:
    """Service for capturing and analyzing business context"""

    def __init__(self):
        self.cache = CacheService()
        self.logger = logging.getLogger(__name__)

    def create_business_context(
        self, name: str, description: str, organization: str, industry: str
    ) -> BusinessContext:
        """Create a new business context"""
        context = BusinessContext(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            organization=organization,
            industry=industry,
            drivers=[],
            objectives=[],
            constraints=[],
            metrics=[],
            capabilities=[],
            capability_heatmap={},
            problem_statement="",
            scope_definition="",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Cache the context
        cache_key = f"business_context:{context.id}"
        self.cache.set(cache_key, asdict(context), ttl=3600)  # 1 hour

        self.logger.info(f"Created business context: {context.name} ({context.id})")
        return context

    def add_business_driver(
        self,
        context_id: str,
        name: str,
        description: str,
        category: str,
        impact_level: str,
        timeframe: str,
        stakeholders: List[str],
    ) -> BusinessDriver:
        """Add a business driver to the context"""
        driver = BusinessDriver(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            category=category,
            impact_level=impact_level,
            timeframe=timeframe,
            stakeholders=stakeholders,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Update context
        context = self._get_context(context_id)
        context.drivers.append(driver)
        context.updated_at = datetime.utcnow()
        self._save_context(context)

        self.logger.info(f"Added business driver: {driver.name} to context {context_id}")
        return driver

    def add_strategic_objective(
        self,
        context_id: str,
        name: str,
        description: str,
        kpis: List[Dict[str, Any]],
        priority: str,
        timeframe: str,
        owner: str,
        dependencies: List[str] = None,
    ) -> StrategicObjective:
        """Add a strategic objective to the context"""
        objective = StrategicObjective(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            kpis=kpis or [],
            priority=priority,
            timeframe=timeframe,
            owner=owner,
            dependencies=dependencies or [],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Update context
        context = self._get_context(context_id)
        context.objectives.append(objective)
        context.updated_at = datetime.utcnow()
        self._save_context(context)

        self.logger.info(f"Added strategic objective: {objective.name} to context {context_id}")
        return objective

    def add_business_constraint(
        self,
        context_id: str,
        name: str,
        description: str,
        constraint_type: str,
        impact: str,
        mitigation_strategy: str,
    ) -> BusinessConstraint:
        """Add a business constraint to the context"""
        constraint = BusinessConstraint(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            type=constraint_type,
            impact=impact,
            mitigation_strategy=mitigation_strategy,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Update context
        context = self._get_context(context_id)
        context.constraints.append(constraint)
        context.updated_at = datetime.utcnow()
        self._save_context(context)

        self.logger.info(f"Added business constraint: {constraint.name} to context {context_id}")
        return constraint

    def add_success_metric(
        self,
        context_id: str,
        name: str,
        description: str,
        metric_type: str,
        current_value: float,
        target_value: float,
        unit: str,
        measurement_frequency: str,
        owner: str,
    ) -> SuccessMetric:
        """Add a success metric to the context"""
        metric = SuccessMetric(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            metric_type=metric_type,
            current_value=current_value,
            target_value=target_value,
            unit=unit,
            measurement_frequency=measurement_frequency,
            owner=owner,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Update context
        context = self._get_context(context_id)
        context.metrics.append(metric)
        context.updated_at = datetime.utcnow()
        self._save_context(context)

        self.logger.info(f"Added success metric: {metric.name} to context {context_id}")
        return metric

    def add_business_capability(
        self,
        context_id: str,
        name: str,
        description: str,
        domain: str,
        level: int,
        parent_capability: Optional[str],
        maturity: str,
        strategic_importance: str,
        business_value: str,
        current_state: str,
        target_state: str,
        gaps: List[str] = None,
        dependencies: List[str] = None,
    ) -> BusinessCapability:
        """Add a business capability to the context"""
        capability = BusinessCapability(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            domain=domain,
            level=level,
            parent_capability=parent_capability,
            maturity=CapabilityMaturity(maturity),
            strategic_importance=StrategicImportance(strategic_importance),
            business_value=business_value,
            current_state=current_state,
            target_state=target_state,
            gaps=gaps or [],
            dependencies=dependencies or [],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Update context
        context = self._get_context(context_id)
        context.capabilities.append(capability)
        context.updated_at = datetime.utcnow()
        self._save_context(context)

        self.logger.info(f"Added business capability: {capability.name} to context {context_id}")
        return capability

    def generate_capability_heatmap(self, context_id: str) -> Dict[str, Any]:
        """Generate a capability heatmap visualization data"""
        context = self._get_context(context_id)

        heatmap = {
            "domains": {},
            "maturity_distribution": {},
            "strategic_importance_distribution": {},
            "gap_analysis": {},
            "recommendations": [],
        }

        # Group capabilities by domain
        for capability in context.capabilities:
            if capability.domain not in heatmap["domains"]:
                heatmap["domains"][capability.domain] = []
            heatmap["domains"][capability.domain].append(asdict(capability))

        # Calculate maturity distribution
        maturity_counts = {}
        for cap in context.capabilities:
            maturity = cap.maturity.value
            maturity_counts[maturity] = maturity_counts.get(maturity, 0) + 1
        heatmap["maturity_distribution"] = maturity_counts

        # Calculate strategic importance distribution
        importance_counts = {}
        for cap in context.capabilities:
            importance = cap.strategic_importance.value
            importance_counts[importance] = importance_counts.get(importance, 0) + 1
        heatmap["strategic_importance_distribution"] = importance_counts

        # Gap analysis
        total_gaps = sum(len(cap.gaps) for cap in context.capabilities)
        heatmap["gap_analysis"] = {
            "total_gaps": total_gaps,
            "capabilities_with_gaps": len([c for c in context.capabilities if c.gaps]),
            "average_gaps_per_capability": total_gaps / len(context.capabilities)
            if context.capabilities
            else 0,
        }

        # Generate recommendations
        heatmap["recommendations"] = self._generate_heatmap_recommendations(context)

        # Update context
        context.capability_heatmap = heatmap
        context.updated_at = datetime.utcnow()
        self._save_context(context)

        return heatmap

    def generate_problem_statement(self, context_id: str) -> str:
        """Generate a problem statement from the business context"""
        context = self._get_context(context_id)

        drivers_text = ", ".join([d.name for d in context.drivers[:3]])
        objectives_text = ", ".join([o.name for o in context.objectives[:3]])
        constraints_text = ", ".join([c.name for c in context.constraints[:2]])

        problem_statement = f"""
        The {context.organization} organization in the {context.industry} industry is facing
        key business drivers including {drivers_text}. Strategic objectives include
        {objectives_text}. However, the organization is constrained by {constraints_text}.

        Current capability analysis shows {len(context.capabilities)} business capabilities
        with an average maturity of {self._calculate_average_maturity(context.capabilities)}.
        Key gaps include {self._identify_top_gaps(context.capabilities)}.

        This architecture initiative aims to address these challenges and achieve the
        strategic objectives while working within the identified constraints.
        """

        # Update context
        context.problem_statement = problem_statement.strip()
        context.updated_at = datetime.utcnow()
        self._save_context(context)

        return context.problem_statement

    def generate_scope_definition(self, context_id: str) -> str:
        """Generate a scope definition from the business context"""
        context = self._get_context(context_id)

        in_scope_caps = [
            c
            for c in context.capabilities
            if c.strategic_importance in [StrategicImportance.HIGH, StrategicImportance.CRITICAL]
        ]
        out_of_scope_caps = [
            c for c in context.capabilities if c.strategic_importance == StrategicImportance.LOW
        ]

        scope_definition = f"""
        SCOPE DEFINITION

        IN SCOPE:
        - Strategic objectives: {', '.join([o.name for o in context.objectives])}
        - Critical business capabilities: {', '.join([c.name for c in in_scope_caps])}
        - Key constraints to address: {', '.join([c.name for c in context.constraints])}

        OUT OF SCOPE:
        - Low-priority capabilities: {', '.join([c.name for c in out_of_scope_caps])}
        - Non-strategic business drivers

        ASSUMPTIONS:
        - Business context remains stable for the duration of the initiative
        - Required resources and budget will be available
        - Stakeholder commitment to the strategic objectives

        CONSTRAINTS:
        {chr(10).join([f"- {c.name}: {c.description}" for c in context.constraints])}
        """

        # Update context
        context.scope_definition = scope_definition.strip()
        context.updated_at = datetime.utcnow()
        self._save_context(context)

        return context.scope_definition

    def _get_context(self, context_id: str) -> BusinessContext:
        """Get business context from cache"""
        cache_key = f"business_context:{context_id}"
        cached_data = self.cache.get(cache_key)

        if cached_data:
            # Reconstruct nested dataclasses from dicts
            drivers = [BusinessDriver(**d) for d in cached_data.get("drivers", [])]
            objectives = [StrategicObjective(**o) for o in cached_data.get("objectives", [])]
            constraints = [BusinessConstraint(**c) for c in cached_data.get("constraints", [])]
            metrics = [SuccessMetric(**m) for m in cached_data.get("metrics", [])]
            capabilities = []
            for cap_data in cached_data.get("capabilities", []):
                cap_data["maturity"] = CapabilityMaturity(cap_data["maturity"])
                cap_data["strategic_importance"] = StrategicImportance(
                    cap_data["strategic_importance"]
                )
                capabilities.append(BusinessCapability(**cap_data))

            # Convert back to BusinessContext
            return BusinessContext(
                id=cached_data["id"],
                name=cached_data["name"],
                description=cached_data["description"],
                organization=cached_data["organization"],
                industry=cached_data["industry"],
                drivers=drivers,
                objectives=objectives,
                constraints=constraints,
                metrics=metrics,
                capabilities=capabilities,
                capability_heatmap=cached_data.get("capability_heatmap", {}),
                problem_statement=cached_data.get("problem_statement", ""),
                scope_definition=cached_data.get("scope_definition", ""),
                created_at=cached_data["created_at"],
                updated_at=cached_data["updated_at"],
            )

        raise ValueError(f"Business context {context_id} not found")

    def _save_context(self, context: BusinessContext):
        """Save business context to cache"""
        cache_key = f"business_context:{context.id}"
        self.cache.set(cache_key, asdict(context), ttl=3600)

    def _generate_heatmap_recommendations(self, context: BusinessContext) -> List[str]:
        """Generate recommendations based on capability analysis"""
        recommendations = []

        # Maturity recommendations
        low_maturity = [
            c
            for c in context.capabilities
            if c.maturity in [CapabilityMaturity.NONE, CapabilityMaturity.INITIAL]
        ]
        if low_maturity:
            recommendations.append(
                f"Focus on maturing {len(low_maturity)} capabilities currently at low maturity levels"
            )

        # Strategic importance recommendations
        critical_caps = [
            c
            for c in context.capabilities
            if c.strategic_importance == StrategicImportance.CRITICAL
        ]
        if critical_caps:
            recommendations.append(
                f"Prioritize architecture work for {len(critical_caps)} critical capabilities"
            )

        # Gap recommendations
        caps_with_gaps = [c for c in context.capabilities if c.gaps]
        if caps_with_gaps:
            recommendations.append(
                f"Address gaps in {len(caps_with_gaps)} capabilities to achieve target state"
            )

        return recommendations

    def _calculate_average_maturity(self, capabilities: List[BusinessCapability]) -> str:
        """Calculate average maturity level"""
        if not capabilities:
            return "unknown"

        maturity_values = {
            CapabilityMaturity.NONE: 0,
            CapabilityMaturity.INITIAL: 1,
            CapabilityMaturity.REPEATABLE: 2,
            CapabilityMaturity.DEFINED: 3,
            CapabilityMaturity.MANAGED: 4,
            CapabilityMaturity.OPTIMIZING: 5,
        }

        total = sum(maturity_values[c.maturity] for c in capabilities)
        average = total / len(capabilities)

        # Convert back to enum
        for maturity, value in maturity_values.items():
            if value >= average:
                return maturity.value

        return CapabilityMaturity.OPTIMIZING.value

    def _identify_top_gaps(self, capabilities: List[BusinessCapability]) -> str:
        """Identify the most common gaps"""
        all_gaps = []
        for cap in capabilities:
            all_gaps.extend(cap.gaps)

        if not all_gaps:
            return "none identified"

        # Count gap frequencies
        gap_counts = {}
        for gap in all_gaps:
            gap_counts[gap] = gap_counts.get(gap, 0) + 1

        # Return top 3 gaps
        top_gaps = sorted(gap_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        return ", ".join([gap for gap, count in top_gaps])
