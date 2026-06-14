"""
Task Dependency Resolver - Analyzes task relationships and identifies parallelizable work.
"""

from typing import List, Dict, Set, Tuple
from datetime import datetime, timedelta


class TaskDependency:
    """Represents a single task in the workflow."""
    
    def __init__(self, task_id: str, title: str, duration_days: int, 
                 dependencies: List[str] = None, phase: str = None):
        self.task_id = task_id
        self.title = title
        self.duration_days = duration_days
        self.dependencies = dependencies or []
        self.phase = phase
        self.earliest_start = 0
        self.earliest_finish = 0
        self.latest_start = 0
        self.latest_finish = 0
        self.slack = 0
        self.is_critical = False
        self.parallelizable_with = []


class TaskDependencyResolver:
    """
    Resolves task dependencies to:
    - Build dependency graph
    - Calculate earliest/latest start times
    - Identify critical path tasks
    - Find parallelizable work
    """
    
    def __init__(self, tasks: List[TaskDependency] = None):
        self.tasks = tasks or []
        self.task_map = {t.task_id: t for t in self.tasks}
        self.project_duration = 0
    
    def add_task(self, task: TaskDependency):
        """Add a task to the resolver."""
        self.tasks.append(task)
        self.task_map[task.task_id] = task
    
    def resolve(self) -> bool:
        """
        Resolve all dependencies and calculate timing.
        Returns True if successful, False if circular dependency detected.
        """
        # Check for circular dependencies
        if self._has_circular_dependency():
            return False
        
        # Calculate forward pass (earliest start/finish)
        self._forward_pass()
        
        # Calculate backward pass (latest start/finish)
        self._backward_pass()
        
        # Calculate slack and identify critical path
        self._calculate_slack()
        
        # Identify parallelizable tasks
        self._identify_parallelizable()
        
        return True
    
    def _has_circular_dependency(self) -> bool:
        """Detect circular dependencies using DFS."""
        visited = set()
        rec_stack = set()
        
        def _dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            
            task = self.task_map.get(node_id)
            if not task:
                return False
            
            for dep_id in task.dependencies:
                if dep_id not in visited:
                    if _dfs(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        for task_id in self.task_map:
            if task_id not in visited:
                if _dfs(task_id):
                    return True
        
        return False
    
    def _forward_pass(self):
        """
        Calculate earliest start and finish times.
        Process tasks in dependency order.
        """
        # Topological sort
        processed = set()
        
        def process_task(task_id: str) -> int:
            if task_id in processed:
                return self.task_map[task_id].earliest_finish
            
            task = self.task_map.get(task_id)
            if not task:
                return 0
            
            # Process all dependencies first
            max_predecessor_finish = 0
            for dep_id in task.dependencies:
                pred_finish = process_task(dep_id)
                max_predecessor_finish = max(max_predecessor_finish, pred_finish)
            
            # Set this task's timing
            task.earliest_start = max_predecessor_finish
            task.earliest_finish = task.earliest_start + task.duration_days
            
            processed.add(task_id)
            return task.earliest_finish
        
        # Process all tasks
        for task_id in self.task_map:
            process_task(task_id)
        
        # Project duration is max finish time
        self.project_duration = max(
            (t.earliest_finish for t in self.tasks),
            default=0
        )
    
    def _backward_pass(self):
        """
        Calculate latest start and finish times.
        Work backwards from project end.
        """
        # Initialize latest finish times
        project_end = self.project_duration
        
        for task in self.tasks:
            task.latest_finish = project_end
            task.latest_start = project_end
        
        # Reverse topological sort to process dependencies
        processed = set()
        
        def process_task_backward(task_id: str) -> int:
            if task_id in processed:
                return self.task_map[task_id].latest_start
            
            task = self.task_map.get(task_id)
            if not task:
                return project_end
            
            # Find all tasks that depend on this one (dependents)
            dependents = [
                t for t in self.tasks 
                if task_id in t.dependencies
            ]
            
            if not dependents:
                # Terminal task - latest finish is project end
                task.latest_finish = project_end
            else:
                # Latest finish is minimum latest start of dependents
                min_dependent_start = min(
                    (process_task_backward(d.task_id) for d in dependents),
                    default=project_end
                )
                task.latest_finish = min_dependent_start
            
            task.latest_start = task.latest_finish - task.duration_days
            processed.add(task_id)
            return task.latest_start
        
        # Process all tasks
        for task_id in self.task_map:
            process_task_backward(task_id)
    
    def _calculate_slack(self):
        """
        Calculate slack time for each task.
        Tasks with zero slack are on critical path.
        """
        for task in self.tasks:
            task.slack = task.latest_start - task.earliest_start
            task.is_critical = (task.slack == 0)
    
    def _identify_parallelizable(self):
        """
        Identify which tasks can run in parallel.
        Two tasks can run in parallel if:
        - Neither depends on the other
        - They don't share resources (simplified: always assume they can)
        """
        for i, task1 in enumerate(self.tasks):
            for task2 in self.tasks[i+1:]:
                # Check if task1 depends on task2
                if task2.task_id in task1.dependencies:
                    continue
                
                # Check if task2 depends on task1
                if task1.task_id in task2.dependencies:
                    continue
                
                # No dependency relationship - can parallelize
                task1.parallelizable_with.append(task2.task_id)
                task2.parallelizable_with.append(task1.task_id)
    
    def get_critical_path(self) -> List[str]:
        """Return task IDs on the critical path."""
        return [t.task_id for t in self.tasks if t.is_critical]
    
    def get_parallel_groups(self) -> List[List[str]]:
        """
        Group tasks into waves that can run in parallel.
        Each wave contains tasks that have no dependencies on each other
        and can theoretically run at the same time.
        """
        groups = []
        processed = set()
        
        for day in range(self.project_duration + 1):
            group = []
            for task in self.tasks:
                if task.task_id in processed:
                    continue
                
                # Task can be in this group if:
                # 1. Its earliest start <= current day
                # 2. It hasn't been processed yet
                if task.earliest_start <= day <= task.earliest_finish:
                    group.append(task.task_id)
                    processed.add(task.task_id)
            
            if group:
                groups.append(group)
        
        return groups
    
    def get_resource_profile(self) -> Dict[int, int]:
        """
        Calculate resource requirements per day.
        Assumes 1 resource per task.
        Returns dict of {day: num_tasks_active}
        """
        profile = {}
        for day in range(self.project_duration + 1):
            active_count = sum(
                1 for t in self.tasks 
                if t.earliest_start <= day < t.earliest_finish
            )
            if active_count > 0:
                profile[day] = active_count
        
        return profile
    
    def get_bottlenecks(self) -> List[Dict]:
        """
        Identify tasks that are critical path constraints.
        These tasks have many dependents or long duration on critical path.
        """
        bottlenecks = []
        
        for task in self.tasks:
            if not task.is_critical:
                continue
            
            # Count how many tasks depend on this one
            dependents = sum(
                1 for t in self.tasks 
                if task.task_id in t.dependencies
            )
            
            if dependents > 1 or task.duration_days > 5:
                bottlenecks.append({
                    'task_id': task.task_id,
                    'title': task.title,
                    'duration': task.duration_days,
                    'dependent_count': dependents,
                    'impact_score': (dependents * task.duration_days) / 10.0
                })
        
        # Sort by impact
        bottlenecks.sort(key=lambda x: x['impact_score'], reverse=True)
        return bottlenecks
    
    def get_summary(self) -> Dict:
        """Return comprehensive summary of dependency analysis."""
        critical_tasks = [t for t in self.tasks if t.is_critical]
        parallelizable_groups = self.get_parallel_groups()
        resource_profile = self.get_resource_profile()
        
        return {
            'total_tasks': len(self.tasks),
            'total_duration': self.project_duration,
            'critical_path_length': len(critical_tasks),
            'num_phases': len(set(t.phase for t in self.tasks if t.phase)),
            'critical_tasks': [t.task_id for t in critical_tasks],
            'avg_parallelization': (
                len(self.tasks) / len(parallelizable_groups) 
                if parallelizable_groups else 1.0
            ),
            'max_concurrent_tasks': max(resource_profile.values()) if resource_profile else 1,
            'bottlenecks': self.get_bottlenecks(),
        }
