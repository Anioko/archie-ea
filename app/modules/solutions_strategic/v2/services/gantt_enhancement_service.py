"""
ent-05 Gantt Chart Enhancement — Export and Advanced Features
- Export to PNG, SVG, CSV formats
- Enhanced critical path calculation
- Risk scoring and visualization
- Mobile optimization
"""

import csv
import io
from datetime import datetime
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class GanttExportService:
    """Handles Gantt chart export to various formats."""
    
    @staticmethod
    def export_to_csv(tasks: List[Dict], gantt_data: Dict) -> str:
        """Export Gantt tasks to CSV format."""
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                'Task ID',
                'Task Name',
                'Phase',
                'Start Date',
                'End Date',
                'Duration (days)',
                'Status',
                'Progress %',
                'Risk Level',
                'Priority',
                'Assigned To',
                'Est. Cost',
                'Is Critical',
                'Dependencies'
            ]
        )
        
        writer.writeheader()
        
        for task in tasks:
            start_date = task.get('start_date')
            end_date = task.get('end_date')
            
            # Calculate duration in days
            duration = ''
            if start_date and end_date:
                try:
                    start = datetime.fromisoformat(start_date)
                    end = datetime.fromisoformat(end_date)
                    duration = (end - start).days
                except (ValueError, TypeError):
                    logger.exception("Failed to compute start")
                    pass
            
            writer.writerow({
                'Task ID': task.get('id', ''),
                'Task Name': task.get('name', ''),
                'Phase': task.get('group', ''),
                'Start Date': start_date,
                'End Date': end_date,
                'Duration (days)': duration,
                'Status': task.get('status', ''),
                'Progress %': task.get('progress', 0),
                'Risk Level': task.get('meta', {}).get('risk_level', ''),
                'Priority': task.get('meta', {}).get('priority', ''),
                'Assigned To': task.get('meta', {}).get('assigned_to', ''),
                'Est. Cost': task.get('meta', {}).get('estimated_cost', ''),
                'Is Critical': 'Yes' if task.get('is_critical') else 'No',
                'Dependencies': ','.join(task.get('dependencies', []))
            })
        
        return output.getvalue()
    
    @staticmethod
    def export_to_svg(tasks: List[Dict], gantt_data: Dict, width: int = 1200, height: int = 600) -> str:
        """Export Gantt chart to SVG format."""
        svg_lines = [
            f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
            '<defs>',
            '<style>',
            '.task-bar { stroke: #333; stroke-width: 1; }',
            '.task-label { font-family: Arial; font-size: 12px; fill: #000; }',
            '.critical { fill: #ef4444; }',
            '.completed { fill: #22c55e; }',
            '.in-progress { fill: #f59e0b; }',
            '.planned { fill: #d1d5db; }',
            '</style>',
            '</defs>',
            '<g>',
        ]
        
        # Add background
        svg_lines.append(f'<rect width="{width}" height="{height}" fill="#fff" stroke="#ccc" stroke-width="1"/>')
        
        # Add title
        svg_lines.append(f'<text x="10" y="25" class="task-label" font-weight="bold">Gantt Chart Export</text>')
        svg_lines.append(f'<text x="10" y="45" class="task-label" font-size="10">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</text>')
        
        # Add tasks (simplified SVG rendering)
        y_pos = 70
        row_height = 25
        
        for task in tasks:
            task_class = 'critical' if task.get('is_critical') else task.get('status', 'planned')
            
            # Task bar
            svg_lines.append(
                f'<rect x="200" y="{y_pos}" width="300" height="20" class="task-bar {task_class}"/>'
            )
            
            # Task label
            svg_lines.append(
                f'<text x="10" y="{y_pos + 15}" class="task-label">{task.get("name", "")[:40]}</text>'
            )
            
            # Status label
            svg_lines.append(
                f'<text x="520" y="{y_pos + 15}" class="task-label" font-size="10">{task.get("status", "")}</text>'
            )
            
            y_pos += row_height
        
        svg_lines.append('</g>')
        svg_lines.append('</svg>')
        
        return '\n'.join(svg_lines)
    
    @staticmethod
    async def export_to_png(tasks: List[Dict], gantt_data: Dict) -> bytes:
        """
        Export Gantt chart to PNG format.
        Requires: html2canvas or similar rendering engine.
        This is a placeholder for implementation with a rendering service.
        """
        # In production, use html2canvas, Playwright, or similar
        # For now, return a placeholder error message
        raise NotImplementedError(
            "PNG export requires html2canvas or server-side rendering. "
            "Consider using Playwright or similar headless browser."
        )


class CriticalPathAnalyzer:
    """Enhanced critical path analysis for Gantt visualization."""
    
    @staticmethod
    def calculate_critical_path(tasks: List[Dict]) -> Tuple[List[str], int]:
        """
        Calculate critical path through task network.
        
        Returns:
            (critical_task_ids, critical_path_length_days)
        """
        if not tasks:
            return [], 0
        
        # Build dependency graph
        task_map = {t['id']: t for t in tasks}
        
        # Find tasks with no predecessors (start tasks)
        all_deps = set()
        for task in tasks:
            all_deps.update(task.get('dependencies', []))
        
        start_tasks = [t for t in tasks if t['id'] not in all_deps]
        
        if not start_tasks:
            # No dependencies, just take first task
            start_tasks = [tasks[0]]
        
        # Calculate forward pass (earliest start/finish)
        earliest_start = {}
        earliest_finish = {}
        
        for task in start_tasks:
            earliest_start[task['id']] = 0
            earliest_finish[task['id']] = CriticalPathAnalyzer._get_task_duration(task)
        
        # Forward pass through dependency chain
        for task in tasks:
            if task['id'] in earliest_start:
                continue
            
            # Get max earliest finish of predecessors
            max_pred_finish = 0
            deps = task.get('dependencies', [])
            
            for dep_id in deps:
                if dep_id in earliest_finish:
                    max_pred_finish = max(max_pred_finish, earliest_finish[dep_id])
            
            earliest_start[task['id']] = max_pred_finish
            earliest_finish[task['id']] = max_pred_finish + CriticalPathAnalyzer._get_task_duration(task)
        
        # Find end tasks
        end_tasks = [
            t for t in tasks 
            if not any(dep_id == t['id'] for t in tasks for dep_id in t.get('dependencies', []))
        ]
        
        if not end_tasks:
            end_tasks = [tasks[-1]]
        
        # Project completion is max earliest finish
        project_duration = max(
            (earliest_finish.get(t['id'], 0) for t in end_tasks),
            default=0
        )
        
        # Backward pass (latest start/finish)
        latest_finish = {}
        latest_start = {}
        
        for task in end_tasks:
            latest_finish[task['id']] = project_duration
            latest_start[task['id']] = project_duration - CriticalPathAnalyzer._get_task_duration(task)
        
        # Calculate slack for each task
        critical_tasks = []
        
        for task in tasks:
            duration = CriticalPathAnalyzer._get_task_duration(task)
            es = earliest_start.get(task['id'], 0)
            ef = earliest_finish.get(task['id'], es + duration)
            ls = latest_start.get(task['id'], es)
            lf = latest_finish.get(task['id'], ef)
            
            slack = ls - es
            
            # Critical if slack is 0 (no flexibility)
            if slack == 0:
                critical_tasks.append(task['id'])
        
        return critical_tasks, project_duration
    
    @staticmethod
    def _get_task_duration(task: Dict) -> int:
        """Get task duration in days."""
        start = task.get('start_date')
        end = task.get('end_date')
        
        if not start or not end:
            return 1
        
        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            return max(1, (end_dt - start_dt).days)
        except (ValueError, TypeError):
            return 1


class RiskScoringService:
    """Risk assessment and visualization for Gantt tasks."""
    
    RISK_COLORS = {
        'critical': '#dc2626',
        'high': '#ea580c',
        'medium': '#d97706',
        'low': '#16a34a'
    }
    
    RISK_WEIGHTS = {
        'critical': 1.0,
        'high': 0.75,
        'medium': 0.5,
        'low': 0.25
    }
    
    @staticmethod
    def assess_task_risk(task: Dict) -> str:
        """
        Assess risk level for a task based on:
        - Criticality (on critical path)
        - Status
        - Progress vs. timeline
        - Explicit risk_level if provided
        """
        # If risk level explicitly set, use it
        if task.get('meta', {}).get('risk_level'):
            return task['meta']['risk_level']
        
        risk_score = 0
        
        # Critical path adds risk
        if task.get('is_critical'):
            risk_score += 0.3
        
        # Status impact
        status = task.get('status', 'planned')
        if status == 'blocked':
            risk_score += 0.4
        elif status == 'at_risk':
            risk_score += 0.35
        elif status == 'in_progress':
            # Check progress vs. timeline
            progress = task.get('progress', 0)
            if progress == 0:
                risk_score += 0.2  # Should have started
        
        # Map to risk level
        if risk_score >= 0.7:
            return 'critical'
        elif risk_score >= 0.5:
            return 'high'
        elif risk_score >= 0.25:
            return 'medium'
        else:
            return 'low'
    
    @staticmethod
    def get_risk_color(risk_level: str) -> str:
        """Get hex color for risk level."""
        return RiskScoringService.RISK_COLORS.get(risk_level, '#9ca3af')
    
    @staticmethod
    def calculate_portfolio_risk(tasks: List[Dict]) -> Dict:
        """Calculate overall risk metrics for project portfolio."""
        if not tasks:
            return {
                'overall_risk': 'low',
                'critical_count': 0,
                'at_risk_count': 0,
                'risk_score': 0
            }
        
        risks = [RiskScoringService.assess_task_risk(t) for t in tasks]
        
        critical = sum(1 for r in risks if r == 'critical')
        high = sum(1 for r in risks if r == 'high')
        medium = sum(1 for r in risks if r == 'medium')
        
        # Weighted risk score
        risk_score = (
            (critical * RiskScoringService.RISK_WEIGHTS['critical']) +
            (high * RiskScoringService.RISK_WEIGHTS['high']) +
            (medium * RiskScoringService.RISK_WEIGHTS['medium'])
        ) / len(tasks)
        
        if risk_score >= 0.6:
            overall_risk = 'critical'
        elif risk_score >= 0.4:
            overall_risk = 'high'
        elif risk_score >= 0.25:
            overall_risk = 'medium'
        else:
            overall_risk = 'low'
        
        return {
            'overall_risk': overall_risk,
            'critical_count': critical,
            'high_count': high,
            'medium_count': medium,
            'risk_score': round(risk_score, 2),
            'total_tasks': len(tasks)
        }
