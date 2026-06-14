"""
Solution Workflow Model - Stores auto-generated implementation roadmaps.
"""

from datetime import datetime
from app import db
from app.models.mixins import TenantMixin


class SolutionWorkflowTask(db.Model):
    """Individual task within a solution workflow."""
    __tablename__ = 'solution_workflow_tasks'

    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('solution_workflows.id', ondelete='CASCADE'), nullable=False)
    task_id = db.Column(db.String(50), nullable=False)  # e.g., "PHASE_ASSESS_DATA"
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Duration & timing
    duration_days = db.Column(db.Integer, nullable=False)
    earliest_start = db.Column(db.Integer, default=0)  # Days from project start
    earliest_finish = db.Column(db.Integer, default=0)
    latest_start = db.Column(db.Integer, default=0)
    latest_finish = db.Column(db.Integer, default=0)
    slack = db.Column(db.Integer, default=0)  # Flexibility in scheduling
    
    # Relationships
    dependencies = db.Column(db.JSON, default=list)  # List of task IDs this task depends on
    parallelizable_with = db.Column(db.JSON, default=list)  # Can run in parallel with these
    
    # Resource & phase
    phase_name = db.Column(db.String(100))  # e.g., "Assessment", "Implementation", "Testing"
    phase_sequence = db.Column(db.Integer)  # 1, 2, 3, etc.
    assignee_role = db.Column(db.String(100))  # e.g., "Data Architect", "Project Manager"
    
    # Criticality
    is_critical = db.Column(db.Boolean, default=False)  # On critical path
    buffer_recommendation = db.Column(db.Integer, default=0)  # Days of buffer recommended
    
    # Estimation confidence
    confidence_score = db.Column(db.Float, default=0.8)  # 0.0-1.0
    estimation_method = db.Column(db.String(50))  # "historical", "expert", "parametric"
    risk_adjustment = db.Column(db.Float, default=1.0)  # Multiplier for duration
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'title': self.title,
            'description': self.description,
            'duration_days': self.duration_days,
            'earliest_start': self.earliest_start,
            'earliest_finish': self.earliest_finish,
            'latest_start': self.latest_start,
            'latest_finish': self.latest_finish,
            'slack': self.slack,
            'dependencies': self.dependencies,
            'parallelizable_with': self.parallelizable_with,
            'phase_name': self.phase_name,
            'phase_sequence': self.phase_sequence,
            'assignee_role': self.assignee_role,
            'is_critical': self.is_critical,
            'buffer_recommendation': self.buffer_recommendation,
            'confidence_score': self.confidence_score,
            'estimation_method': self.estimation_method,
            'risk_adjustment': self.risk_adjustment,
        }


class SolutionWorkflow(TenantMixin, db.Model):
    """Stores complete workflow orchestration for a solution."""
    __tablename__ = 'solution_workflows'

    id = db.Column(db.Integer, primary_key=True)
    solution_id = db.Column(db.Integer, db.ForeignKey('solutions.id', ondelete='CASCADE'), nullable=False)
    
    # Timeline metrics
    total_duration_days = db.Column(db.Integer, nullable=False)
    critical_path_length = db.Column(db.Integer, nullable=False)
    project_start_date = db.Column(db.DateTime)
    project_end_date = db.Column(db.DateTime)
    
    # Structure
    num_tasks = db.Column(db.Integer, default=0)
    num_phases = db.Column(db.Integer, default=0)
    num_critical_tasks = db.Column(db.Integer, default=0)
    
    # Parallelization metrics
    avg_parallelization_factor = db.Column(db.Float, default=1.0)  # 1.0 = all sequential, 2.0+ = good parallelization
    min_team_size = db.Column(db.Integer)
    max_team_size = db.Column(db.Integer)
    
    # Risk assessment
    total_buffer_days = db.Column(db.Integer, default=0)  # Risk-adjusted buffers
    risk_confidence = db.Column(db.Float, default=0.85)  # Confidence in estimates
    major_risks = db.Column(db.JSON, default=list)  # [{risk_id, description, impact, mitigation}]
    
    # Phases captured
    phases = db.Column(db.JSON, default=list)  # [{name, sequence, start_day, end_day, tasks}]
    
    # Tasks relationship
    tasks = db.relationship('SolutionWorkflowTask', backref='workflow', lazy=True, cascade='all, delete-orphan')
    
    # Metadata
    generation_method = db.Column(db.String(50))  # "ai_orchestrated", "manual", etc.
    version = db.Column(db.Integer, default=1)
    is_locked = db.Column(db.Boolean, default=False)  # Once locked, shouldn't auto-regenerate
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_tasks=True):
        data = {
            'id': self.id,
            'solution_id': self.solution_id,
            'total_duration_days': self.total_duration_days,
            'critical_path_length': self.critical_path_length,
            'project_start_date': self.project_start_date.isoformat() if self.project_start_date else None,
            'project_end_date': self.project_end_date.isoformat() if self.project_end_date else None,
            'num_tasks': self.num_tasks,
            'num_phases': self.num_phases,
            'num_critical_tasks': self.num_critical_tasks,
            'avg_parallelization_factor': self.avg_parallelization_factor,
            'min_team_size': self.min_team_size,
            'max_team_size': self.max_team_size,
            'total_buffer_days': self.total_buffer_days,
            'risk_confidence': self.risk_confidence,
            'major_risks': self.major_risks,
            'phases': self.phases,
            'generation_method': self.generation_method,
            'version': self.version,
            'is_locked': self.is_locked,
        }
        if include_tasks:
            data['tasks'] = [t.to_dict() for t in self.tasks]
        return data

    @property
    def critical_path_tasks(self):
        """Return tasks on the critical path."""
        return [t for t in self.tasks if t.is_critical]

    @property
    def longest_phase(self):
        """Return the phase with longest duration."""
        if not self.phases:
            return None
        return max(self.phases, key=lambda p: p.get('duration', 0))

    @property
    def parallelizable_groups(self):
        """Group tasks that can run in parallel."""
        groups = []
        remaining = set(t.task_id for t in self.tasks)
        
        while remaining:
            group = set()
            for task_id in list(remaining):
                task = next((t for t in self.tasks if t.task_id == task_id), None)
                if not task:
                    continue
                
                # Check if task can run with others in current group
                can_run_parallel = True
                for other_id in group:
                    if other_id not in (task.parallelizable_with or []):
                        can_run_parallel = False
                        break
                
                if can_run_parallel and not task.dependencies:
                    group.add(task_id)
                    remaining.discard(task_id)
            
            if group:
                groups.append(list(group))
            else:
                # Avoid infinite loop: move first remaining to next group
                if remaining:
                    groups.append([remaining.pop()])
        
        return groups
