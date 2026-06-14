"""
Task Auto-Generator for Adversarial Review Findings

Automatically creates agent_plan.yaml task entries for issues found
during autonomous adversarial review. Integrates with the sidebar
parent item review cycle.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class AdversarialFinding:
    """A finding from adversarial review that needs a task created"""
    id: str
    dimension: str  # security, idor, sqli, error_handling, performance
    severity: str  # P0, P1, P2
    file_path: str
    line_number: Optional[int]
    description: str
    code_snippet: str
    recommendation: str
    sidebar_item_id: str
    sidebar_item_name: str
    auto_fixable: bool = False
    fix_strategy: Optional[str] = None
    estimated_effort_minutes: int = 30


class TaskAutoGenerator:
    """
    Automatically generates agent_plan.yaml task entries from adversarial findings.
    
    Features:
    - Converts findings to structured task entries
    - Assigns appropriate priority based on severity
    - Sets orchestration pattern (PEV for P0/P1)
    - Links to sidebar parent items
    - Updates agent_plan.yaml atomically
    """
    
    # Dimension to category mapping
    DIMENSION_CATEGORIES = {
        "security": "Security",
        "idor": "Security - IDOR",
        "sqli": "Security - SQL Injection",
        "error_handling": "Error Handling",
        "performance": "Performance",
        "architecture": "Architecture",
        "api_design": "API Design",
        "data_model": "Data Model",
        "test_coverage": "Test Coverage",
        "documentation": "Documentation",
    }
    
    # Severity to priority mapping
    SEVERITY_PRIORITY = {
        "P0": "critical",
        "P1": "high", 
        "P2": "medium",
        "P3": "low"
    }
    
    # Severity to orchestration pattern
    SEVERITY_PATTERN = {
        "P0": "PEV",
        "P1": "PEV",
        "P2": None,
        "P3": None
    }
    
    def __init__(self, agent_plan_path: str = "agent_plan.yaml"):
        self.agent_plan_path = Path(agent_plan_path)
        self.backup_dir = Path(".agent/backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_task(self, finding: AdversarialFinding) -> Dict[str, Any]:
        """Generate a single task entry from a finding."""
        
        task_id = self._generate_task_id(finding)
        
        task = {
            "id": task_id,
            "name": self._generate_task_name(finding),
            "status": "todo",
            "priority": self.SEVERITY_PRIORITY.get(finding.severity, "medium"),
            "orchestration_pattern": self.SEVERITY_PATTERN.get(finding.severity),
            "description": self._generate_description(finding),
            "adversarial_source": {
                "sidebar_item_id": finding.sidebar_item_id,
                "sidebar_item_name": finding.sidebar_item_name,
                "review_type": "autonomous_lightweight",
                "finding_id": finding.id,
                "dimension": finding.dimension,
                "severity": finding.severity,
                "detected_at": datetime.now().isoformat()
            },
            "technical_details": {
                "file_path": finding.file_path,
                "line_number": finding.line_number,
                "code_snippet": finding.code_snippet,
                "vulnerability_type": finding.dimension,
            },
            "fix_requirements": {
                "auto_fixable": finding.auto_fixable,
                "fix_strategy": finding.fix_strategy,
                "recommendation": finding.recommendation,
                "acceptance_criteria": self._generate_acceptance_criteria(finding)
            },
            "deliverables": [finding.file_path],
            "estimated_effort_minutes": finding.estimated_effort_minutes,
            "owner": "autonomous-orchestrator",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Add adversarial review tracking fields
        if finding.severity in ["P0", "P1"]:
            task["adversarial_review"] = {
                "required": True,
                "completed": False,
                "findings": [],
                "crypto_signature": None
            }
        
        return task
    
    def generate_tasks(self, findings: List[AdversarialFinding]) -> List[Dict[str, Any]]:
        """Generate multiple task entries from findings."""
        return [self.generate_task(f) for f in findings]
    
    def add_tasks_to_agent_plan(
        self, 
        findings: List[AdversarialFinding],
        section_name: str = "autonomous_adversarial_fixes"
    ) -> List[str]:
        """
        Add generated tasks to agent_plan.yaml.
        
        Returns list of created task IDs.
        """
        if not self.agent_plan_path.exists():
            logger.error(f"agent_plan.yaml not found at {self.agent_plan_path}")
            return []
        
        # Create backup
        self._create_backup()
        
        # Load existing plan
        with open(self.agent_plan_path, 'r') as f:
            plan = yaml.safe_load(f)
        
        # Generate tasks
        tasks = self.generate_tasks(findings)
        task_ids = []
        
        # Find or create section
        phases = plan.get('phases', [])
        adversarial_phase = None
        
        for phase in phases:
            if phase.get('name') == section_name or phase.get('id') == section_name:
                adversarial_phase = phase
                break
        
        if not adversarial_phase:
            # Create new phase for autonomous fixes
            adversarial_phase = {
                'id': section_name,
                'name': 'Autonomous Adversarial Review Fixes',
                'description': 'Issues discovered and fixed through autonomous adversarial review',
                'tasks': []
            }
            phases.append(adversarial_phase)
        
        # Add tasks
        for task in tasks:
            # Check for duplicates
            existing = self._find_existing_task(adversarial_phase['tasks'], task)
            if existing:
                logger.info(f"Task {task['id']} already exists, skipping")
                continue
            
            adversarial_phase['tasks'].append(task)
            task_ids.append(task['id'])
            logger.info(f"Added task {task['id']}: {task['name']}")
        
        # Update statistics
        self._update_statistics(plan, len(task_ids))
        
        # Save updated plan
        with open(self.agent_plan_path, 'w') as f:
            yaml.dump(plan, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Added {len(task_ids)} tasks to {self.agent_plan_path}")
        return task_ids
    
    def _generate_task_id(self, finding: AdversarialFinding) -> str:
        """Generate a unique task ID."""
        prefix = finding.sidebar_item_id.upper()[:6]
        severity = finding.severity
        # Create a hash from file path and line number for uniqueness
        unique_str = f"{finding.file_path}:{finding.line_number or 0}"
        hash_suffix = uuid.uuid5(uuid.NAMESPACE_DNS, unique_str).hex[:4]
        
        return f"{prefix}-{severity}-{hash_suffix}"
    
    def _generate_task_name(self, finding: AdversarialFinding) -> str:
        """Generate a descriptive task name."""
        category = self.DIMENSION_CATEGORIES.get(finding.dimension, finding.dimension)
        short_desc = finding.description[:50] + "..." if len(finding.description) > 50 else finding.description
        return f"[{finding.severity}] {category}: {short_desc}"
    
    def _generate_description(self, finding: AdversarialFinding) -> str:
        """Generate detailed task description."""
        lines = [
            f"## Issue: {finding.description}",
            "",
            f"**Location:** `{finding.file_path}:{finding.line_number or 'unknown'}`",
            f"**Sidebar Item:** {finding.sidebar_item_name}",
            f"**Severity:** {finding.severity}",
            f"**Dimension:** {finding.dimension}",
            "",
            "### Problem Code",
            "```python",
            finding.code_snippet,
            "```",
            "",
            "### Recommendation",
            finding.recommendation,
            "",
            "### Auto-Fix Available" if finding.auto_fixable else "### Manual Fix Required",
        ]
        
        if finding.auto_fixable:
            lines.append(f"Strategy: `{finding.fix_strategy}`")
        
        return "\n".join(lines)
    
    def _generate_acceptance_criteria(self, finding: AdversarialFinding) -> List[str]:
        """Generate acceptance criteria for the fix."""
        criteria = [
            f"Issue at {finding.file_path}:{finding.line_number or 'unknown'} is resolved",
            "Code compiles without errors",
            "No new warnings introduced"
        ]
        
        if finding.dimension == "security" or finding.dimension == "idor":
            criteria.append("Security review confirms vulnerability is fixed")
        elif finding.dimension == "sqli":
            criteria.append("SQL injection vector eliminated")
        elif finding.dimension == "error_handling":
            criteria.append("Error messages are generic (no info disclosure)")
        elif finding.dimension == "performance":
            criteria.append("Performance impact is neutral or positive")
        
        # Add adversarial review criteria for P0/P1
        if finding.severity in ["P0", "P1"]:
            criteria.append("Adversarial review completed with no unresolved P0/P1 findings")
            criteria.append("Cryptographic signature attached to critique")
        
        return criteria
    
    def _find_existing_task(self, tasks: List[Dict], new_task: Dict) -> Optional[Dict]:
        """Check if a similar task already exists."""
        new_details = new_task.get('technical_details', {})
        
        for task in tasks:
            existing_details = task.get('technical_details', {})
            
            # Match by file path and line number
            if (existing_details.get('file_path') == new_details.get('file_path') and
                existing_details.get('line_number') == new_details.get('line_number') and
                task.get('adversarial_source', {}).get('dimension') == new_task.get('adversarial_source', {}).get('dimension')):
                return task
        
        return None
    
    def _create_backup(self):
        """Create a backup of agent_plan.yaml."""
        if not self.agent_plan_path.exists():
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"agent_plan_{timestamp}.yaml"
        
        with open(self.agent_plan_path, 'r') as src:
            with open(backup_path, 'w') as dst:
                dst.write(src.read())
        
        logger.info(f"Created backup at {backup_path}")
    
    def _update_statistics(self, plan: Dict, new_tasks_count: int):
        """Update plan statistics."""
        # Add autonomous fixes counter
        if 'autonomous_fixes' not in plan:
            plan['autonomous_fixes'] = 0
        plan['autonomous_fixes'] += new_tasks_count
        
        # Update existing counters if present
        if 'total_tasks' in plan:
            plan['total_tasks'] = plan.get('total_tasks', 0) + new_tasks_count
    
    def mark_task_complete(
        self, 
        task_id: str, 
        crypto_signature: Optional[str] = None,
        findings_summary: Optional[Dict] = None
    ):
        """Mark a task as complete with adversarial review data."""
        if not self.agent_plan_path.exists():
            return False
        
        with open(self.agent_plan_path, 'r') as f:
            plan = yaml.safe_load(f)
        
        # Find and update task
        for phase in plan.get('phases', []):
            for task in phase.get('tasks', []):
                if task.get('id') == task_id:
                    task['status'] = 'done'
                    task['updated_at'] = datetime.now().isoformat()
                    task['completed_at'] = datetime.now().isoformat()
                    
                    if crypto_signature:
                        task.setdefault('adversarial_review', {})
                        task['adversarial_review']['completed'] = True
                        task['adversarial_review']['crypto_signature'] = crypto_signature
                    
                    if findings_summary:
                        task['adversarial_review']['findings'] = findings_summary
                    
                    # Save
                    with open(self.agent_plan_path, 'w') as f:
                        yaml.dump(plan, f, default_flow_style=False, sort_keys=False)
                    
                    logger.info(f"Marked task {task_id} as complete")
                    return True
        
        return False
    
    def get_pending_adversarial_tasks(self, sidebar_item_id: Optional[str] = None) -> List[Dict]:
        """Get all pending tasks with adversarial review requirements."""
        if not self.agent_plan_path.exists():
            return []
        
        with open(self.agent_plan_path, 'r') as f:
            plan = yaml.safe_load(f)
        
        pending = []
        
        for phase in plan.get('phases', []):
            for task in phase.get('tasks', []):
                # Check if this is an adversarial task
                adversarial = task.get('adversarial_review', {})
                if task.get('status') in ['todo', 'in_progress']:
                    if sidebar_item_id:
                        task_sidebar = task.get('adversarial_source', {}).get('sidebar_item_id')
                        if task_sidebar == sidebar_item_id:
                            pending.append(task)
                    else:
                        pending.append(task)
        
        return pending


# Singleton instance
_task_generator: Optional[TaskAutoGenerator] = None


def get_task_auto_generator() -> TaskAutoGenerator:
    """Get or create the singleton task auto-generator."""
    global _task_generator
    if _task_generator is None:
        _task_generator = TaskAutoGenerator()
    return _task_generator
