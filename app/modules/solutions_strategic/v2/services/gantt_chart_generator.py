"""
Gantt Chart Generator - Generates timeline visualization data for workflows.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


@dataclass
class GanttBar:
    """Single bar in a Gantt chart."""
    task_id: str
    title: str
    start_day: int
    duration: int
    end_day: int
    phase: str
    is_critical: bool
    progress: int = 0
    assignee: str = None
    risk_level: str = 'low'
    dependencies: List[str] = None
    
    def to_dict(self):
        return {
            **asdict(self),
            'dependencies': self.dependencies or []
        }


class GanttChartGenerator:
    """
    Generates Gantt chart data structure from task list.
    Formats for frontend rendering (e.g., using Chart.js, D3, or custom visualization).
    """
    
    def __init__(self, project_start_date: datetime = None, tasks: List[Dict] = None):
        self.project_start_date = project_start_date or datetime.now()
        self.tasks = tasks or []
        self.bars = []
        self.timeline = {}
    
    def set_tasks(self, tasks: List[Dict]):
        """Update task list."""
        self.tasks = tasks
        self.bars = []
        self.timeline = {}
    
    def generate_bars(self) -> List[Dict]:
        """
        Generate Gantt bars from task data.
        
        Returns:
            List of bar dictionaries with positioning
        """
        self.bars = []
        
        for task in self.tasks:
            bar = GanttBar(
                task_id=task['task_id'],
                title=task.get('title', task['task_id']),
                start_day=task.get('earliest_start', 0),
                duration=task.get('duration_days', 1),
                end_day=task.get('earliest_finish', task.get('earliest_start', 0) + task.get('duration_days', 1)),
                phase=task.get('phase', 'General'),
                is_critical=task.get('is_critical', False),
                progress=task.get('progress', 0),
                assignee=task.get('assignee_role', 'TBD'),
                risk_level=self._assess_risk_level(task),
                dependencies=task.get('dependencies', [])
            )
            
            self.bars.append(bar)
        
        # Sort by start day
        self.bars.sort(key=lambda b: b.start_day)
        return [b.to_dict() for b in self.bars]
    
    def generate_timeline(self, num_weeks: int = None) -> List[Dict]:
        """
        Generate timeline structure showing weeks and milestones.
        
        Args:
            num_weeks: Override number of weeks to display
            
        Returns:
            Timeline data with week breaks and milestone markers
        """
        if not self.tasks:
            return []
        
        # Calculate project duration in days
        max_day = max(t.get('earliest_finish', 0) for t in self.tasks)
        
        if not num_weeks:
            num_weeks = int((max_day + 4) / 7)  # Round up to weeks
        
        timeline = []
        
        for week in range(num_weeks):
            start_day = week * 7
            end_day = min((week + 1) * 7, max_day)
            start_date = self.project_start_date + timedelta(days=start_day)
            end_date = self.project_start_date + timedelta(days=end_day)
            
            timeline.append({
                'week': week + 1,
                'start_day': start_day,
                'end_day': end_day,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'width_percent': (end_day - start_day) / max_day * 100 if max_day else 0
            })
        
        self.timeline = {week['week']: week for week in timeline}
        return timeline
    
    def generate_phase_rows(self) -> List[Dict]:
        """
        Generate row structure for phases.
        Each phase is a row containing its tasks.
        
        Returns:
            Phase rows with task lists
        """
        phases = {}
        
        for bar in self.bars:
            phase = bar.phase or 'General'
            if phase not in phases:
                phases[phase] = {
                    'name': phase,
                    'bars': [],
                    'start_day': bar.start_day,
                    'end_day': bar.end_day,
                    'is_critical': False
                }
            
            phases[phase]['bars'].append(bar.to_dict())
            phases[phase]['end_day'] = max(phases[phase]['end_day'], bar.end_day)
            if bar.is_critical:
                phases[phase]['is_critical'] = True
        
        # Convert to list
        phase_rows = list(phases.values())
        
        # Calculate phase sequence
        phase_rows.sort(key=lambda p: p['start_day'])
        for i, phase in enumerate(phase_rows):
            phase['sequence'] = i + 1
        
        return phase_rows
    
    def generate_resource_schedule(self) -> Dict:
        """
        Generate resource allocation schedule.
        Shows which roles are needed when.
        
        Returns:
            Resource schedule by day
        """
        resource_schedule = {}
        
        for bar in self.bars:
            assignee = bar.assignee or 'Unassigned'
            
            for day in range(bar.start_day, bar.end_day):
                if day not in resource_schedule:
                    resource_schedule[day] = []
                
                resource_schedule[day].append({
                    'role': assignee,
                    'task_id': bar.task_id,
                    'task_title': bar.title
                })
        
        return resource_schedule
    
    def generate_milestone_markers(self, milestones: List[Dict] = None) -> List[Dict]:
        """
        Generate milestone markers for key dates.
        
        Args:
            milestones: Optional list of milestone definitions
                       [{name, day}, ...]
            
        Returns:
            Milestone markers positioned on timeline
        """
        if not milestones:
            # Auto-generate milestones at phase transitions
            milestones = []
            current_phase = None
            
            for bar in self.bars:
                if bar.phase != current_phase:
                    milestones.append({
                        'name': f'{bar.phase} Start',
                        'day': bar.start_day
                    })
                    current_phase = bar.phase
        
        markers = []
        for milestone in milestones:
            day = milestone.get('day', 0)
            date = self.project_start_date + timedelta(days=day)
            
            markers.append({
                'name': milestone.get('name', 'Milestone'),
                'day': day,
                'date': date.isoformat(),
                'week': int(day / 7) + 1
            })
        
        return sorted(markers, key=lambda m: m['day'])
    
    def generate_dependencies_graph(self) -> Dict:
        """
        Generate dependency graph for visualization.
        Shows which tasks block which other tasks.
        
        Returns:
            Graph structure with nodes and edges
        """
        nodes = []
        edges = []
        
        for bar in self.bars:
            nodes.append({
                'id': bar.task_id,
                'label': bar.title,
                'phase': bar.phase,
                'is_critical': bar.is_critical,
                'start_day': bar.start_day,
                'duration': bar.duration
            })
            
            for dep_id in (bar.dependencies or []):
                edges.append({
                    'from': dep_id,
                    'to': bar.task_id,
                    'type': 'dependency'
                })
        
        return {
            'nodes': nodes,
            'edges': edges
        }
    
    def generate_full_gantt_data(self) -> Dict:
        """
        Generate complete Gantt chart data structure for rendering.
        
        Returns:
            Complete data object ready for frontend
        """
        # Generate all components
        bars = self.generate_bars()
        timeline = self.generate_timeline()
        phases = self.generate_phase_rows()
        resources = self.generate_resource_schedule()
        milestones = self.generate_milestone_markers()
        dependencies = self.generate_dependencies_graph()
        
        # Calculate metrics
        total_days = max((b['end_day'] for b in bars), default=0)
        critical_count = sum(1 for b in bars if b['is_critical'])
        
        return {
            'metadata': {
                'project_start_date': self.project_start_date.isoformat(),
                'total_tasks': len(bars),
                'total_duration_days': total_days,
                'critical_task_count': critical_count,
                'total_phases': len(phases),
                'generated_at': datetime.now().isoformat()
            },
            'timeline': timeline,
            'phases': phases,
            'bars': bars,
            'resources': resources,
            'milestones': milestones,
            'dependencies': dependencies,
            'statistics': self._calculate_statistics(bars)
        }
    
    def _assess_risk_level(self, task: Dict) -> str:
        """Assess risk level for a task."""
        risk_score = task.get('risk_score', 0.5)
        confidence = task.get('confidence_score', 0.8)
        
        # Low confidence or high risk score = higher risk
        if confidence < 0.6 or risk_score > 0.7:
            return 'high'
        if confidence < 0.75 or risk_score > 0.5:
            return 'medium'
        return 'low'
    
    def _calculate_statistics(self, bars: List[Dict]) -> Dict:
        """Calculate Gantt statistics."""
        if not bars:
            return {}
        
        critical_bars = [b for b in bars if b['is_critical']]
        
        return {
            'average_task_duration': round(sum(b['duration'] for b in bars) / len(bars), 1),
            'max_task_duration': max(b['duration'] for b in bars),
            'parallelization_factor': len(bars) / len(critical_bars) if critical_bars else 1.0,
            'critical_path_percentage': round(100 * len(critical_bars) / len(bars), 1),
            'risk_distribution': {
                'high': sum(1 for b in bars if b['risk_level'] == 'high'),
                'medium': sum(1 for b in bars if b['risk_level'] == 'medium'),
                'low': sum(1 for b in bars if b['risk_level'] == 'low')
            }
        }
