"""
Workflow Orchestrator Service - Main service for Phase 4 workflow generation.
Converts AI recommendations into detailed implementation roadmaps.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

from app.models.solution_reasoning import SolutionAIReasoningState
from app.models.solution_workflow import SolutionWorkflow, SolutionWorkflowTask
from app.modules.solutions_strategic.v2.services.task_dependency_resolver import (
    TaskDependencyResolver, TaskDependency
)
from app.modules.solutions_strategic.v2.services.critical_path_analyzer import CriticalPathAnalyzer
from app.modules.solutions_strategic.v2.services.gantt_chart_generator import GanttChartGenerator

logger = logging.getLogger(__name__)


class WorkflowStateMachine:
    """Declarative state machine with transition validation for solution workflows."""

    # Valid state transitions: {from_state: [allowed_to_states]}
    TRANSITIONS = {
        "draft": ["in_review", "cancelled"],
        "in_review": ["approved", "rejected", "draft"],
        "approved": ["in_progress", "cancelled"],
        "rejected": ["draft", "cancelled"],
        "in_progress": ["completed", "on_hold", "cancelled"],
        "on_hold": ["in_progress", "cancelled"],
        "completed": ["archived"],
        "cancelled": ["draft"],  # Allow re-opening
        "archived": [],  # Terminal state
    }

    TERMINAL_STATES = {"archived"}

    @classmethod
    def is_valid_transition(cls, from_state, to_state):
        """Check if a state transition is allowed."""
        if from_state not in cls.TRANSITIONS:
            return False
        return to_state in cls.TRANSITIONS[from_state]

    @classmethod
    def get_allowed_transitions(cls, current_state):
        """Return list of states reachable from current_state."""
        return list(cls.TRANSITIONS.get(current_state, []))

    @classmethod
    def is_terminal(cls, state):
        """Check if a state is terminal (no outgoing transitions)."""
        return state in cls.TERMINAL_STATES

    @classmethod
    def validate_transition(cls, from_state, to_state):
        """Validate and return (is_valid, error_message)."""
        if from_state not in cls.TRANSITIONS:
            return False, f"Unknown state: {from_state}"
        if to_state not in cls.TRANSITIONS.get(from_state, []):
            allowed = cls.get_allowed_transitions(from_state)
            return False, f"Cannot transition from '{from_state}' to '{to_state}'. Allowed: {allowed}"
        return True, None


class WorkflowOrchestratorService:
    """
    Orchestrates workflow generation from AI recommendations.
    
    Workflow:
    1. Extract recommendations from reasoning state
    2. Define tasks based on recommendations
    3. Determine task dependencies
    4. Calculate realistic timelines
    5. Generate Gantt chart
    6. Persist to database
    """
    
    # Phase definitions with typical task patterns
    PHASE_TEMPLATES = {
        'assessment': {
            'sequence': 1,
            'tasks': [
                {'task_id': 'ASSESS_CURRENT_STATE', 'title': 'Assess current state', 'duration': 5, 'role': 'Architect'},
                {'task_id': 'DATA_AUDIT', 'title': 'Data audit & quality review', 'duration': 8, 'role': 'Data Engineer'},
                {'task_id': 'STAKEHOLDER_ANALYSIS', 'title': 'Stakeholder & impact analysis', 'duration': 3, 'role': 'Project Manager'},
            ]
        },
        'design': {
            'sequence': 2,
            'tasks': [
                {'task_id': 'DESIGN_SOLUTION', 'title': 'Design target solution', 'duration': 10, 'role': 'Architect', 'risk': 0.4},
                {'task_id': 'DESIGN_REVIEW', 'title': 'Design review & approval', 'duration': 3, 'role': 'Lead Architect', 'risk': 0.2},
                {'task_id': 'RESOURCE_PLAN', 'title': 'Resource & budget planning', 'duration': 5, 'role': 'Project Manager', 'risk': 0.3},
            ]
        },
        'implementation': {
            'sequence': 3,
            'tasks': [
                {'task_id': 'SETUP_INFRASTRUCTURE', 'title': 'Setup infrastructure & environments', 'duration': 7, 'role': 'DevOps', 'risk': 0.5},
                {'task_id': 'IMPLEMENT_CORE', 'title': 'Implement core functionality', 'duration': 20, 'role': 'Development', 'risk': 0.6},
                {'task_id': 'DATA_MIGRATION', 'title': 'Data migration & validation', 'duration': 10, 'role': 'Data Engineer', 'risk': 0.7},
                {'task_id': 'INTEGRATION', 'title': 'Integration with existing systems', 'duration': 8, 'role': 'Integration Engineer', 'risk': 0.5},
            ]
        },
        'testing': {
            'sequence': 4,
            'tasks': [
                {'task_id': 'UNIT_TESTING', 'title': 'Unit & component testing', 'duration': 5, 'role': 'QA', 'risk': 0.3},
                {'task_id': 'INTEGRATION_TESTING', 'title': 'Integration & system testing', 'duration': 8, 'role': 'QA', 'risk': 0.4},
                {'task_id': 'UAT', 'title': 'User acceptance testing', 'duration': 7, 'role': 'Business Analyst', 'risk': 0.5},
            ]
        },
        'training': {
            'sequence': 5,
            'tasks': [
                {'task_id': 'DEVELOP_TRAINING', 'title': 'Develop training materials', 'duration': 6, 'role': 'Business Analyst', 'risk': 0.3},
                {'task_id': 'TRAIN_TRAINERS', 'title': 'Train-the-trainer program', 'duration': 4, 'role': 'Training Lead', 'risk': 0.2},
                {'task_id': 'END_USER_TRAINING', 'title': 'End-user training', 'duration': 8, 'role': 'Trainers', 'risk': 0.4},
            ]
        },
        'cutover': {
            'sequence': 6,
            'tasks': [
                {'task_id': 'CUTOVER_PREP', 'title': 'Cutover preparation & rehearsal', 'duration': 3, 'role': 'Project Manager', 'risk': 0.6},
                {'task_id': 'GO_LIVE', 'title': 'Go-live execution', 'duration': 2, 'role': 'Operations', 'risk': 0.8},
                {'task_id': 'STABILIZATION', 'title': 'Stabilization & monitoring', 'duration': 5, 'role': 'Support', 'risk': 0.5},
            ]
        }
    }
    
    def __init__(self):
        self.dependency_resolver = TaskDependencyResolver()
        self.critical_path_analyzer = CriticalPathAnalyzer()
        self.gantt_generator = GanttChartGenerator()
    
    def generate_workflow(self, solution_id: int, 
                         solution_description: str = None,
                         reasoning_state: SolutionAIReasoningState = None) -> Optional[SolutionWorkflow]:
        """
        Generate complete workflow for a solution.
        
        Args:
            solution_id: ID of the solution
            solution_description: Description of the solution
            reasoning_state: AI reasoning state with suggestions
            
        Returns:
            Persisted SolutionWorkflow or None on error
        """
        try:
            # Determine which phases apply to this solution
            selected_phases = self._select_phases(solution_description, reasoning_state)
            
            # Generate task list
            tasks_list = self._generate_tasks(selected_phases)
            
            # Resolve dependencies
            self._resolve_dependencies(tasks_list)
            
            # Calculate timeline
            timeline_data = self._calculate_timeline(tasks_list)
            
            # Generate Gantt data
            gantt_data = self._generate_gantt(tasks_list, timeline_data)
            
            # Create and persist workflow
            workflow = self._create_workflow(
                solution_id=solution_id,
                tasks_list=tasks_list,
                timeline_data=timeline_data,
                gantt_data=gantt_data
            )
            
            logger.info(f"Workflow generated for solution {solution_id}: {workflow.num_tasks} tasks, {workflow.total_duration_days} days")
            return workflow
            
        except Exception as e:
            logger.error(f"Failed to generate workflow for solution {solution_id}: {str(e)}")
            return None
    
    def _select_phases(self, description: str = None, 
                      reasoning_state: SolutionAIReasoningState = None) -> List[str]:
        """
        Select which phases apply to this solution.
        Most solutions follow full path: assessment → design → impl → test → train → cutover
        """
        # Default: all phases
        phases = ['assessment', 'design', 'implementation', 'testing', 'training', 'cutover']
        
        # Could customize based on solution type, but for now use all
        return phases
    
    def _generate_tasks(self, phases: List[str]) -> List[Dict]:
        """Generate task list from selected phases."""
        tasks = []
        task_counter = 0
        
        for phase_name in phases:
            if phase_name not in self.PHASE_TEMPLATES:
                continue
            
            phase_template = self.PHASE_TEMPLATES[phase_name]
            
            for task_template in phase_template['tasks']:
                task_counter += 1
                task = {
                    'task_id': task_template['task_id'],
                    'title': task_template['title'],
                    'description': f"{task_template['title']} for this solution implementation",
                    'duration_days': task_template['duration'],
                    'phase': phase_name,
                    'phase_sequence': phase_template['sequence'],
                    'assignee_role': task_template.get('role', 'TBD'),
                    'risk_score': task_template.get('risk', 0.5),
                    'confidence_score': 0.8,
                    'estimation_method': 'template',
                }
                tasks.append(task)
        
        # Add dependencies between phases
        self._add_phase_dependencies(tasks)
        
        return tasks
    
    def _add_phase_dependencies(self, tasks: List[Dict]):
        """Add dependencies between phases."""
        for i, task in enumerate(tasks):
            # Each task depends on previous tasks in same phase
            same_phase_tasks = [t for t in tasks if t['phase'] == task['phase'] and tasks.index(t) < i]
            if same_phase_tasks:
                task['dependencies'] = [t['task_id'] for t in same_phase_tasks[-1:]]
            else:
                task['dependencies'] = []
            
            # First task of each phase depends on last task of previous phase
            current_phase_seq = task['phase_sequence']
            if current_phase_seq > 1:
                prev_phase_tasks = [t for t in tasks if t['phase_sequence'] == current_phase_seq - 1]
                if prev_phase_tasks and not task['dependencies']:
                    task['dependencies'] = [prev_phase_tasks[-1]['task_id']]
    
    def _resolve_dependencies(self, tasks: List[Dict]) -> bool:
        """
        Resolve task dependencies using dependency resolver.
        Calculates earliest/latest start/finish times.
        """
        # Convert to TaskDependency objects
        task_deps = []
        for task in tasks:
            dep = TaskDependency(
                task_id=task['task_id'],
                title=task['title'],
                duration_days=task['duration_days'],
                dependencies=task.get('dependencies', []),
                phase=task['phase']
            )
            task_deps.append(dep)
            self.dependency_resolver.add_task(dep)
        
        # Resolve
        if not self.dependency_resolver.resolve():
            logger.warning(f"Circular dependency detected")
            return False
        
        # Copy calculated values back to tasks
        for i, task in enumerate(tasks):
            task_dep = self.dependency_resolver.task_map.get(task['task_id'])
            if task_dep:
                task['earliest_start'] = task_dep.earliest_start
                task['earliest_finish'] = task_dep.earliest_finish
                task['latest_start'] = task_dep.latest_start
                task['latest_finish'] = task_dep.latest_finish
                task['slack'] = task_dep.slack
                task['is_critical'] = task_dep.is_critical
                task['parallelizable_with'] = task_dep.parallelizable_with
        
        return True
    
    def _calculate_timeline(self, tasks: List[Dict]) -> Dict:
        """Calculate timeline using critical path analyzer."""
        self.critical_path_analyzer.set_tasks(tasks)
        critical_path = self.critical_path_analyzer.calculate_critical_path()
        buffers = self.critical_path_analyzer.calculate_risk_buffers(risk_adjustment_factor=1.20)
        timeline = self.critical_path_analyzer.apply_buffers_to_timeline(use_buffers=True)
        
        # Add buffer info to tasks
        for task in tasks:
            task['buffer_recommendation'] = buffers.get(task['task_id'], 0)
        
        return {
            'original_duration': timeline['original_duration'],
            'buffered_duration': timeline['buffered_duration'],
            'total_buffer': timeline['total_buffer'],
            'critical_path': critical_path
        }
    
    def _generate_gantt(self, tasks: List[Dict], timeline_data: Dict) -> Dict:
        """Generate Gantt chart data."""
        project_start = datetime.now()
        self.gantt_generator.set_tasks(tasks)
        self.gantt_generator.project_start_date = project_start
        
        return self.gantt_generator.generate_full_gantt_data()
    
    def _create_workflow(self, solution_id: int, tasks_list: List[Dict],
                        timeline_data: Dict, gantt_data: Dict) -> SolutionWorkflow:
        """Create and persist workflow to database."""
        from app import db
        
        # Create workflow record
        workflow = SolutionWorkflow(
            solution_id=solution_id,
            total_duration_days=timeline_data['original_duration'],
            critical_path_length=len(timeline_data['critical_path']),
            num_tasks=len(tasks_list),
            num_phases=len(set(t['phase'] for t in tasks_list)),
            num_critical_tasks=sum(1 for t in tasks_list if t.get('is_critical')),
            avg_parallelization_factor=gantt_data['statistics'].get('parallelization_factor', 1.0),
            total_buffer_days=timeline_data['total_buffer'],
            risk_confidence=0.85,
            project_start_date=datetime.now(),
            project_end_date=datetime.now() + timedelta(days=timeline_data['buffered_duration']),
            phases=gantt_data['phases'],
            generation_method='ai_orchestrated',
        )
        
        # Create task records
        for task_data in tasks_list:
            task = SolutionWorkflowTask(
                workflow=workflow,
                task_id=task_data['task_id'],
                title=task_data['title'],
                description=task_data.get('description'),
                duration_days=task_data['duration_days'],
                earliest_start=task_data.get('earliest_start', 0),
                earliest_finish=task_data.get('earliest_finish', 0),
                latest_start=task_data.get('latest_start', 0),
                latest_finish=task_data.get('latest_finish', 0),
                slack=task_data.get('slack', 0),
                dependencies=task_data.get('dependencies', []),
                parallelizable_with=task_data.get('parallelizable_with', []),
                phase_name=task_data.get('phase'),
                phase_sequence=task_data.get('phase_sequence'),
                assignee_role=task_data.get('assignee_role'),
                is_critical=task_data.get('is_critical', False),
                buffer_recommendation=task_data.get('buffer_recommendation', 0),
                confidence_score=task_data.get('confidence_score', 0.8),
                estimation_method=task_data.get('estimation_method', 'template'),
                risk_adjustment=task_data.get('risk_score', 0.5),
            )
            workflow.tasks.append(task)
        
        db.session.add(workflow)
        db.session.commit()
        
        return workflow
    
    def get_workflow_summary(self, solution_id: int) -> Optional[Dict]:
        """Get summary of solution's workflow."""
        workflow = SolutionWorkflow.query.filter_by(solution_id=solution_id).first()
        if not workflow:
            return None
        
        critical_tasks = [t for t in workflow.tasks if t.is_critical]
        
        return {
            'total_tasks': workflow.num_tasks,
            'total_duration_days': workflow.total_duration_days,
            'critical_path_length': workflow.critical_path_length,
            'critical_tasks': [t.task_id for t in critical_tasks],
            'phases': workflow.phases,
            'project_start': workflow.project_start_date.isoformat() if workflow.project_start_date else None,
            'project_end': workflow.project_end_date.isoformat() if workflow.project_end_date else None,
        }
