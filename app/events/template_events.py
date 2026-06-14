"""Domain events for template instantiation.

Implements Domain Events pattern from Domain-Driven Design.
Allows decoupled event handling for audit, analytics, notifications.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class EventType(Enum):
    """Types of domain events."""

    # Template Events
    TEMPLATE_INSTANTIATED = "template.instantiated"
    TEMPLATE_USAGE_REMOVED = "template.usage.removed"
    BULK_INSTANTIATION_COMPLETED = "template.bulk.completed"
    INSTANTIATION_FAILED = "template.instantiation.failed"

    # FR - 002: Workflow Events
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_STEP_COMPLETED = "workflow.step.completed"

    # FR - 001: AI Orchestration Events
    AGENT_EXECUTION_STARTED = "agent.execution.started"
    AGENT_EXECUTION_COMPLETED = "agent.execution.completed"
    AGENT_CONTEXT_SHARED = "agent.context.shared"
    AI_DECISION_MADE = "ai.decision.made"

    # FR - 003: Data Mesh Events
    DATA_CONTRACT_VALIDATED = "data.contract.validated"
    DATA_LINEAGE_UPDATED = "data.lineage.updated"
    DATA_QUALITY_CHANGED = "data.quality.changed"

    # FR - 004: Service Mesh Events
    SERVICE_HEALTH_CHANGED = "service.health.changed"
    CIRCUIT_BREAKER_STATE_CHANGED = "circuit.breaker.state.changed"
    SERVICE_DISCOVERED = "service.discovered"

    # FR - 005: Workflow Intelligence Events
    DEPENDENCY_RESOLVED = "workflow.dependency.resolved"
    PARALLEL_EXECUTION_STARTED = "workflow.parallel.started"
    DECISION_POINT_REACHED = "workflow.decision.reached"


@dataclass
class DomainEvent:
    """Base domain event."""

    event_type: EventType
    timestamp: datetime
    user_id: Optional[int]
    data: Dict[str, Any]

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class TemplateInstantiatedEvent(DomainEvent):
    """Event fired when template is instantiated."""

    def __init__(
        self,
        template_id: int,
        template_name: str,
        template_code: str,
        application_id: int,
        application_name: str,
        archimate_element_id: int,
        element_type: str,
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.TEMPLATE_INSTANTIATED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "template_id": template_id,
                "template_name": template_name,
                "template_code": template_code,
                "application_id": application_id,
                "application_name": application_name,
                "archimate_element_id": archimate_element_id,
                "element_type": element_type,
            },
        )


@dataclass
class TemplateUsageRemovedEvent(DomainEvent):
    """Event fired when template usage is removed."""

    def __init__(
        self,
        template_id: int,
        application_id: int,
        archimate_element_id: int,
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.TEMPLATE_USAGE_REMOVED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "template_id": template_id,
                "application_id": application_id,
                "archimate_element_id": archimate_element_id,
            },
        )


@dataclass
class BulkInstantiationCompletedEvent(DomainEvent):
    """Event fired when bulk instantiation completes."""

    def __init__(
        self,
        application_id: int,
        template_ids: List[int],
        success_count: int,
        failure_count: int,
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.BULK_INSTANTIATION_COMPLETED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "application_id": application_id,
                "template_ids": template_ids,
                "success_count": success_count,
                "failure_count": failure_count,
            },
        )


# =============================================================================
# FR - 002: Workflow Events
# =============================================================================


@dataclass
class WorkflowStartedEvent(DomainEvent):
    """Event fired when a workflow starts execution."""

    def __init__(
        self,
        workflow_id: int,
        workflow_code: str,
        workflow_name: str,
        context: Dict[str, Any],
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.WORKFLOW_STARTED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "workflow_id": workflow_id,
                "workflow_code": workflow_code,
                "workflow_name": workflow_name,
                "context": context,
            },
        )


@dataclass
class WorkflowCompletedEvent(DomainEvent):
    """Event fired when a workflow completes successfully."""

    def __init__(
        self,
        workflow_id: int,
        workflow_code: str,
        duration_seconds: float,
        result: Dict[str, Any],
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.WORKFLOW_COMPLETED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "workflow_id": workflow_id,
                "workflow_code": workflow_code,
                "duration_seconds": duration_seconds,
                "result": result,
            },
        )


@dataclass
class WorkflowFailedEvent(DomainEvent):
    """Event fired when a workflow fails."""

    def __init__(
        self,
        workflow_id: int,
        workflow_code: str,
        error: str,
        failed_step: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.WORKFLOW_FAILED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "workflow_id": workflow_id,
                "workflow_code": workflow_code,
                "error": error,
                "failed_step": failed_step,
            },
        )


@dataclass
class WorkflowStepCompletedEvent(DomainEvent):
    """Event fired when a workflow step completes."""

    def __init__(
        self,
        workflow_id: int,
        step_id: str,
        step_name: str,
        duration_seconds: float,
        output: Dict[str, Any],
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.WORKFLOW_STEP_COMPLETED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "workflow_id": workflow_id,
                "step_id": step_id,
                "step_name": step_name,
                "duration_seconds": duration_seconds,
                "output": output,
            },
        )


# =============================================================================
# FR - 001: AI Orchestration Events
# =============================================================================


@dataclass
class AgentExecutionStartedEvent(DomainEvent):
    """Event fired when an AI agent starts execution."""

    def __init__(
        self,
        agent_name: str,
        execution_id: int,
        context: Dict[str, Any],
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.AGENT_EXECUTION_STARTED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={"agent_name": agent_name, "execution_id": execution_id, "context": context},
        )


@dataclass
class AgentExecutionCompletedEvent(DomainEvent):
    """Event fired when an AI agent completes execution."""

    def __init__(
        self,
        agent_name: str,
        execution_id: int,
        success: bool,
        duration_seconds: float,
        result: Dict[str, Any],
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.AGENT_EXECUTION_COMPLETED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "agent_name": agent_name,
                "execution_id": execution_id,
                "success": success,
                "duration_seconds": duration_seconds,
                "result": result,
            },
        )


@dataclass
class AgentContextSharedEvent(DomainEvent):
    """Event fired when context is shared between agents."""

    def __init__(
        self,
        source_agent: str,
        target_agents: List[str],
        context_key: str,
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.AGENT_CONTEXT_SHARED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "source_agent": source_agent,
                "target_agents": target_agents,
                "context_key": context_key,
            },
        )


@dataclass
class AIDecisionMadeEvent(DomainEvent):
    """Event fired when an AI makes a decision."""

    def __init__(
        self,
        decision_type: str,
        agent_name: str,
        decision: Dict[str, Any],
        confidence_score: float,
        rationale: str,
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.AI_DECISION_MADE,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "decision_type": decision_type,
                "agent_name": agent_name,
                "decision": decision,
                "confidence_score": confidence_score,
                "rationale": rationale,
            },
        )


# =============================================================================
# FR - 003: Data Mesh Events
# =============================================================================


@dataclass
class DataContractValidatedEvent(DomainEvent):
    """Event fired when a data contract is validated."""

    def __init__(
        self,
        contract_id: str,
        contract_name: str,
        valid: bool,
        validation_errors: List[str],
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.DATA_CONTRACT_VALIDATED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "contract_id": contract_id,
                "contract_name": contract_name,
                "valid": valid,
                "validation_errors": validation_errors,
            },
        )


@dataclass
class DataLineageUpdatedEvent(DomainEvent):
    """Event fired when data lineage is updated."""

    def __init__(
        self,
        source_entity: str,
        target_entity: str,
        transformation: str,
        lineage_id: int,
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.DATA_LINEAGE_UPDATED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "source_entity": source_entity,
                "target_entity": target_entity,
                "transformation": transformation,
                "lineage_id": lineage_id,
            },
        )


@dataclass
class DataQualityChangedEvent(DomainEvent):
    """Event fired when data quality metrics change."""

    def __init__(
        self,
        entity_id: str,
        entity_type: str,
        quality_score: float,
        previous_score: float,
        quality_dimensions: Dict[str, float],
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.DATA_QUALITY_CHANGED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "entity_id": entity_id,
                "entity_type": entity_type,
                "quality_score": quality_score,
                "previous_score": previous_score,
                "quality_dimensions": quality_dimensions,
            },
        )


# =============================================================================
# FR - 004: Service Mesh Events
# =============================================================================


@dataclass
class ServiceHealthChangedEvent(DomainEvent):
    """Event fired when service health status changes."""

    def __init__(
        self,
        service_name: str,
        health_status: str,
        previous_status: str,
        health_details: Dict[str, Any],
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.SERVICE_HEALTH_CHANGED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "service_name": service_name,
                "health_status": health_status,
                "previous_status": previous_status,
                "health_details": health_details,
            },
        )


@dataclass
class CircuitBreakerStateChangedEvent(DomainEvent):
    """Event fired when circuit breaker state changes."""

    def __init__(
        self,
        service_name: str,
        new_state: str,
        previous_state: str,
        failure_count: int,
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.CIRCUIT_BREAKER_STATE_CHANGED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "service_name": service_name,
                "new_state": new_state,
                "previous_state": previous_state,
                "failure_count": failure_count,
            },
        )


@dataclass
class ServiceDiscoveredEvent(DomainEvent):
    """Event fired when a new service is discovered."""

    def __init__(
        self,
        service_name: str,
        service_type: str,
        endpoints: List[str],
        capabilities: List[str],
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.SERVICE_DISCOVERED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "service_name": service_name,
                "service_type": service_type,
                "endpoints": endpoints,
                "capabilities": capabilities,
            },
        )


# =============================================================================
# FR - 005: Workflow Intelligence Events
# =============================================================================


@dataclass
class DependencyResolvedEvent(DomainEvent):
    """Event fired when workflow dependencies are resolved."""

    def __init__(
        self,
        workflow_id: int,
        resolved_steps: List[str],
        execution_order: List[str],
        parallel_groups: List[List[str]],
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.DEPENDENCY_RESOLVED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "workflow_id": workflow_id,
                "resolved_steps": resolved_steps,
                "execution_order": execution_order,
                "parallel_groups": parallel_groups,
            },
        )


@dataclass
class ParallelExecutionStartedEvent(DomainEvent):
    """Event fired when parallel execution of steps begins."""

    def __init__(
        self,
        workflow_id: int,
        parallel_steps: List[str],
        max_workers: int,
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.PARALLEL_EXECUTION_STARTED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "workflow_id": workflow_id,
                "parallel_steps": parallel_steps,
                "max_workers": max_workers,
            },
        )


@dataclass
class DecisionPointReachedEvent(DomainEvent):
    """Event fired when a decision point is reached in workflow."""

    def __init__(
        self,
        workflow_id: int,
        decision_id: str,
        decision_type: str,
        options: List[Dict[str, Any]],
        context: Dict[str, Any],
        user_id: Optional[int] = None,
    ):
        super().__init__(
            event_type=EventType.DECISION_POINT_REACHED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            data={
                "workflow_id": workflow_id,
                "decision_id": decision_id,
                "decision_type": decision_type,
                "options": options,
                "context": context,
            },
        )


class DomainEventDispatcher:
    """
    Event dispatcher for domain events.
    Implements Observer pattern for decoupled event handling.
    """

    _handlers: Dict[EventType, List[Callable[[DomainEvent], None]]] = {}

    @classmethod
    def subscribe(cls, event_type: EventType, handler: Callable[[DomainEvent], None]) -> None:
        """Subscribe handler to event type."""
        if event_type not in cls._handlers:
            cls._handlers[event_type] = []
        cls._handlers[event_type].append(handler)

    @classmethod
    def publish(cls, event: DomainEvent) -> None:
        """Publish event to all subscribed handlers."""
        handlers = cls._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                # Log error but don't break other handlers
                from flask import current_app

                if current_app:
                    current_app.logger.error(
                        f"Error in event handler for {event.event_type}: {str(e)}"
                    )

    @classmethod
    def clear_handlers(cls) -> None:
        """Clear all handlers (useful for testing)."""
        cls._handlers.clear()


# Default event handlers


def log_template_instantiated(event: TemplateInstantiatedEvent) -> None:
    """Log template instantiation."""
    from flask import current_app

    if current_app:
        current_app.logger.info(
            f"Template instantiated: {event.data['template_code']} - "
            f"{event.data['template_name']} for app {event.data['application_id']}"
        )


def log_bulk_instantiation_completed(event: BulkInstantiationCompletedEvent) -> None:
    """Log bulk instantiation completion."""
    from flask import current_app

    if current_app:
        current_app.logger.info(
            f"Bulk instantiation completed: {event.data['success_count']} succeeded, "
            f"{event.data['failure_count']} failed for app {event.data['application_id']}"
        )


# Intelligent Integration event handlers


def log_workflow_started(event: WorkflowStartedEvent) -> None:
    """Log workflow start."""
    from flask import current_app

    if current_app:
        current_app.logger.info(
            f"Workflow started: {event.data['workflow_code']} " f"(ID: {event.data['workflow_id']})"
        )


def log_workflow_completed(event: WorkflowCompletedEvent) -> None:
    """Log workflow completion."""
    from flask import current_app

    if current_app:
        current_app.logger.info(
            f"Workflow completed: {event.data['workflow_code']} "
            f"in {event.data['duration_seconds']:.2f}s"
        )


def log_workflow_failed(event: WorkflowFailedEvent) -> None:
    """Log workflow failure."""
    from flask import current_app

    if current_app:
        current_app.logger.error(
            f"Workflow failed: {event.data['workflow_code']} "
            f"at step {event.data['failed_step']}: {event.data['error']}"
        )


def log_agent_execution_started(event: AgentExecutionStartedEvent) -> None:
    """Log agent execution start."""
    from flask import current_app

    if current_app:
        current_app.logger.info(
            f"Agent started: {event.data['agent_name']} "
            f"(Execution ID: {event.data['execution_id']})"
        )


def log_agent_execution_completed(event: AgentExecutionCompletedEvent) -> None:
    """Log agent execution completion."""
    from flask import current_app

    if current_app:
        status = "succeeded" if event.data["success"] else "failed"
        current_app.logger.info(
            f"Agent {status}: {event.data['agent_name']} "
            f"in {event.data['duration_seconds']:.2f}s"
        )


def log_ai_decision_made(event: AIDecisionMadeEvent) -> None:
    """Log AI decision for audit."""
    from flask import current_app

    if current_app:
        current_app.logger.info(
            f"AI Decision: {event.data['decision_type']} by {event.data['agent_name']} "
            f"(confidence: {event.data['confidence_score']:.2f})"
        )


def log_circuit_breaker_state_changed(event: CircuitBreakerStateChangedEvent) -> None:
    """Log circuit breaker state change."""
    from flask import current_app

    if current_app:
        current_app.logger.warning(
            f"Circuit breaker state changed: {event.data['service_name']} "
            f"{event.data['previous_state']} -> {event.data['new_state']} "
            f"(failures: {event.data['failure_count']})"
        )


def log_service_health_changed(event: ServiceHealthChangedEvent) -> None:
    """Log service health change."""
    from flask import current_app

    if current_app:
        current_app.logger.warning(
            f"Service health changed: {event.data['service_name']} "
            f"{event.data['previous_status']} -> {event.data['health_status']}"
        )


# Register default handlers
DomainEventDispatcher.subscribe(EventType.TEMPLATE_INSTANTIATED, log_template_instantiated)
DomainEventDispatcher.subscribe(
    EventType.BULK_INSTANTIATION_COMPLETED, log_bulk_instantiation_completed
)

# Register intelligent integration handlers
DomainEventDispatcher.subscribe(EventType.WORKFLOW_STARTED, log_workflow_started)
DomainEventDispatcher.subscribe(EventType.WORKFLOW_COMPLETED, log_workflow_completed)
DomainEventDispatcher.subscribe(EventType.WORKFLOW_FAILED, log_workflow_failed)
DomainEventDispatcher.subscribe(EventType.AGENT_EXECUTION_STARTED, log_agent_execution_started)
DomainEventDispatcher.subscribe(EventType.AGENT_EXECUTION_COMPLETED, log_agent_execution_completed)
DomainEventDispatcher.subscribe(EventType.AI_DECISION_MADE, log_ai_decision_made)
DomainEventDispatcher.subscribe(
    EventType.CIRCUIT_BREAKER_STATE_CHANGED, log_circuit_breaker_state_changed
)
DomainEventDispatcher.subscribe(EventType.SERVICE_HEALTH_CHANGED, log_service_health_changed)
