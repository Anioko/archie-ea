"""
Critical Path Analyzer - Identifies critical path and calculates realistic timelines.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta


class CriticalPathAnalyzer:
    """
    Analyzes critical path to:
    - Identify which tasks are on the critical path
    - Calculate project duration
    - Recommend risk buffers
    - Identify acceleration opportunities
    """
    
    def __init__(self, tasks_data: List[Dict] = None):
        """
        Initialize with task dependency data.
        Each task should have: task_id, duration, dependencies, risk_score
        """
        self.tasks = tasks_data or []
        self.critical_path = []
        self.project_duration = 0
        self.risk_buffers = {}
        self.buffers_applied = False
    
    def set_tasks(self, tasks: List[Dict]):
        """Update task list."""
        self.tasks = tasks
    
    def calculate_critical_path(self) -> List[str]:
        """
        Calculate and return the critical path.
        Critical path is the longest path through the dependency graph.
        """
        if not self.tasks:
            return []
        
        # Use dynamic programming to find longest path
        memo = {}
        
        def longest_path_from(task_id: str) -> Tuple[int, List[str]]:
            if task_id in memo:
                return memo[task_id]
            
            task = next((t for t in self.tasks if t['task_id'] == task_id), None)
            if not task:
                return (0, [])
            
            duration = task.get('duration_days', 0)
            
            # Find longest path through dependents
            max_length = duration
            max_path = [task_id]
            
            for other_task in self.tasks:
                if task_id in other_task.get('dependencies', []):
                    # This task is a dependent
                    dep_length, dep_path = longest_path_from(other_task['task_id'])
                    total_length = duration + dep_length
                    
                    if total_length > max_length:
                        max_length = total_length
                        max_path = [task_id] + dep_path
            
            memo[task_id] = (max_length, max_path)
            return (max_length, max_path)
        
        # Find path starting from each task with no dependencies
        best_length = 0
        best_path = []
        
        for task in self.tasks:
            if not task.get('dependencies', []):
                # This could be a start task
                length, path = longest_path_from(task['task_id'])
                if length > best_length:
                    best_length = length
                    best_path = path
        
        self.project_duration = best_length
        self.critical_path = best_path
        return best_path
    
    def calculate_risk_buffers(self, risk_adjustment_factor: float = 1.15) -> Dict[str, int]:
        """
        Calculate recommended buffers for each task based on risk.
        
        Args:
            risk_adjustment_factor: Multiplier for estimated durations (default 1.15 = 15% buffer)
        
        Returns:
            Dict mapping task_id to recommended buffer days
        """
        self.risk_buffers = {}
        
        for task in self.tasks:
            task_id = task['task_id']
            duration = task.get('duration_days', 0)
            risk_score = task.get('risk_score', 0.5)  # 0.0-1.0
            
            # Buffer = base_buffer + risk_scaled_buffer
            base_buffer = max(1, int(duration * 0.1))  # 10% minimum
            risk_scaled = int(duration * risk_score * 0.15)  # Up to 15% for high risk
            
            buffer = base_buffer + risk_scaled
            
            # Critical path tasks get extra buffer
            if task_id in self.critical_path:
                buffer = int(buffer * 1.3)
            
            self.risk_buffers[task_id] = buffer
        
        return self.risk_buffers
    
    def apply_buffers_to_timeline(self, use_buffers: bool = True) -> Dict:
        """
        Apply buffers to timeline and recalculate duration.
        
        Returns:
            Updated timeline with buffers applied
        """
        if not use_buffers:
            return {
                'original_duration': self.project_duration,
                'buffered_duration': self.project_duration,
                'total_buffer': 0
            }
        
        total_buffer = sum(self.risk_buffers.values())
        buffered_duration = self.project_duration + total_buffer
        
        self.buffers_applied = True
        
        return {
            'original_duration': self.project_duration,
            'buffered_duration': buffered_duration,
            'total_buffer': total_buffer,
            'buffer_percentage': round(100 * total_buffer / self.project_duration, 1) if self.project_duration else 0
        }
    
    def identify_acceleration_opportunities(self) -> List[Dict]:
        """
        Identify tasks that could be parallelized or accelerated
        to reduce critical path length.
        """
        opportunities = []
        
        for task_id in self.critical_path:
            task = next((t for t in self.tasks if t['task_id'] == task_id), None)
            if not task:
                continue
            
            duration = task.get('duration_days', 0)
            dependencies = task.get('dependencies', [])
            
            # Tasks with long duration and few dependencies are good candidates
            if duration > 5 and len(dependencies) <= 1:
                opportunities.append({
                    'task_id': task_id,
                    'title': task.get('title', task_id),
                    'duration': duration,
                    'reason': 'Long duration task on critical path',
                    'acceleration_potential': '30-50% possible with more resources',
                    'impact_on_timeline': int(duration * 0.4)  # Est. 40% reduction
                })
            
            # Check if task blocks many others
            blocked_count = sum(
                1 for t in self.tasks 
                if task_id in t.get('dependencies', [])
            )
            
            if blocked_count >= 3:
                opportunities.append({
                    'task_id': task_id,
                    'title': task.get('title', task_id),
                    'duration': duration,
                    'reason': f'Blocks {blocked_count} other tasks',
                    'acceleration_potential': '20-40% possible with parallelization',
                    'impact_on_timeline': int(duration * 0.3)
                })
        
        return opportunities
    
    def get_phase_timeline(self, phases_data: List[Dict]) -> List[Dict]:
        """
        Calculate timeline for each phase.
        
        Args:
            phases_data: List of phase definitions with task_ids
            
        Returns:
            Phase timeline with start/end dates and durations
        """
        phase_timeline = []
        current_day = 0
        
        for phase in phases_data:
            phase_task_ids = phase.get('task_ids', [])
            phase_tasks = [
                t for t in self.tasks 
                if t['task_id'] in phase_task_ids
            ]
            
            if not phase_tasks:
                continue
            
            # Phase duration is sum of task durations (assumes sequential within phase)
            phase_duration = sum(t.get('duration_days', 0) for t in phase_tasks)
            
            phase_info = {
                'name': phase.get('name', 'Unknown'),
                'sequence': phase.get('sequence', 0),
                'start_day': current_day,
                'end_day': current_day + phase_duration,
                'duration': phase_duration,
                'task_count': len(phase_tasks),
                'num_critical': sum(1 for t in phase_tasks if t['task_id'] in self.critical_path)
            }
            
            phase_timeline.append(phase_info)
            current_day += phase_duration
        
        return phase_timeline
    
    def get_summary(self) -> Dict:
        """Return comprehensive critical path analysis."""
        buffers = self.apply_buffers_to_timeline(use_buffers=True)
        acceleration = self.identify_acceleration_opportunities()
        
        return {
            'project_duration_days': self.project_duration,
            'critical_path': self.critical_path,
            'critical_task_count': len(self.critical_path),
            'buffers': buffers,
            'total_calendar_duration': buffers['buffered_duration'],
            'risk_assessment': {
                'high_risk_tasks': sum(
                    1 for t in self.tasks 
                    if t.get('risk_score', 0) > 0.7 and t['task_id'] in self.critical_path
                ),
                'average_risk': round(sum(t.get('risk_score', 0.5) for t in self.tasks) / len(self.tasks), 2) if self.tasks else 0
            },
            'acceleration_opportunities': acceleration,
            'recommendation': self._generate_recommendation()
        }
    
    def _generate_recommendation(self) -> str:
        """Generate human-readable recommendation."""
        if not self.critical_path:
            return "Analyze dependencies to identify critical path."
        
        num_critical = len(self.critical_path)
        total_tasks = len(self.tasks)
        
        if num_critical / total_tasks > 0.8:
            return f"Most tasks ({num_critical}/{total_tasks}) are on critical path. Any delay impacts timeline. Focus on risk mitigation."
        
        if num_critical < 3:
            return "Few critical tasks. Strong parallelization opportunity. Consider adding buffer for non-critical work."
        
        acceleration = self.identify_acceleration_opportunities()
        if acceleration:
            return f"Timeline can be reduced by {acceleration[0]['impact_on_timeline']} days by accelerating {acceleration[0]['title']}."
        
        return "Timeline is balanced. Monitor critical path tasks closely during execution."
