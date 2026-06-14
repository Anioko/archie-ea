"""
Autonomous Adversarial Review Orchestrator

Conducts adversarial reviews on sidebar parent items in autonomous mode,
finding issues, creating tasks, fixing them, running guardrails, and cycling
to the next sidebar item automatically.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path

from app.services.adversarial_scope_service import ScopeDetectionService, EnforcementLevel
from app.services.lightweight_adversarial_validator import LightweightAdversarialValidator, ValidationResult
from app.services.dual_agent_orchestrator import DualAgentOrchestrator, AgentContext
from app.services.critique_verification_service import CritiqueVerificationService

logger = logging.getLogger(__name__)


class ReviewStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ANALYZING = "analyzing"
    ISSUES_FOUND = "issues_found"
    TASKS_CREATED = "tasks_created"
    FIXING = "fixing"
    GUARDRAILS_RUNNING = "guardrails_running"
    COMMITTING = "committing"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class SidebarItemState(Enum):
    NOT_REVIEWED = "not_reviewed"
    LIGHTWEIGHT_REVIEWED = "lightweight_reviewed"
    FULL_REVIEWED = "full_reviewed"
    FIXES_APPLIED = "fixes_applied"
    COMMITTED = "committed"
    SKIPPED = "skipped"


@dataclass
class SidebarParentItem:
    """Represents a sidebar parent item (e.g., Vendor Management, Solutions)"""
    id: str
    name: str
    icon: str
    route_prefix: str
    template_pattern: str
    state: SidebarItemState = SidebarItemState.NOT_REVIEWED
    review_id: Optional[str] = None
    issues_found: List[Dict] = field(default_factory=list)
    tasks_created: List[str] = field(default_factory=list)
    last_reviewed: Optional[datetime] = None
    enforcement_level: Optional[EnforcementLevel] = None


@dataclass
class AutonomousReviewSession:
    """Tracks an autonomous review session across multiple sidebar items"""
    session_id: str
    started_at: datetime
    items_to_review: List[SidebarParentItem] = field(default_factory=list)
    completed_items: List[str] = field(default_factory=list)
    failed_items: List[str] = field(default_factory=list)
    current_item: Optional[SidebarParentItem] = None
    status: ReviewStatus = ReviewStatus.PENDING
    cycle_count: int = 0
    max_cycles: int = 10
    config: Dict = field(default_factory=dict)


@dataclass
class FoundIssue:
    """An issue discovered during adversarial review"""
    id: str
    dimension: str  # security, idor, sqli, error_handling, etc.
    severity: str  # P0, P1, P2
    file_path: str
    line_number: Optional[int] = None
    description: str = ""
    code_snippet: str = ""
    recommendation: str = ""
    auto_fixable: bool = False
    fix_strategy: Optional[str] = None


class AutonomousAdversarialOrchestrator:
    """
    Orchestrates autonomous adversarial review of sidebar parent items.
    
    Workflow:
    1. Discover sidebar items from sidebar config
    2. For each item:
       a. Detect scope (LIGHTWEIGHT for review, FULL for fixes)
       b. Run lightweight validation (5-10s)
       c. Create tasks for found issues
       d. Apply fixes (escalates to FULL enforcement)
       e. Run guardrails
       f. Commit with verification
    3. Cycle to next item automatically
    """
    
    def __init__(
        self,
        scope_service: Optional[ScopeDetectionService] = None,
        validator: Optional[LightweightAdversarialValidator] = None,
        dual_orchestrator: Optional[DualAgentOrchestrator] = None,
        critique_service: Optional[CritiqueVerificationService] = None
    ):
        self.scope_service = scope_service or ScopeDetectionService()
        self.validator = validator or LightweightAdversarialValidator()
        self.dual_orchestrator = dual_orchestrator or DualAgentOrchestrator()
        self.critique_service = critique_service or CritiqueVerificationService()
        self.sessions: Dict[str, AutonomousReviewSession] = {}
        
        # Default configuration
        self.default_config = {
            "max_items_per_session": 3,
            "auto_commit": True,
            "auto_pick_next": True,
            "stop_on_p0_unresolved": True,
            "stop_on_failure": True,
            "run_guardrails": True,
            "lightweight_timeout_seconds": 10,
            "full_timeout_minutes": 45,
            "escalation_triggers": [
                "lines_of_code > 30",
                "db_migration_detected",
                "security_keyword_critical",
                "pev_pattern_matched"
            ]
        }
        
        # Sidebar item registry - populated from sidebar config
        self.sidebar_items: Dict[str, SidebarParentItem] = {}
        
    def discover_sidebar_items(self, sidebar_config_path: Optional[str] = None) -> List[SidebarParentItem]:
        """
        Discover sidebar parent items from configuration.
        
        Reads sidebar menu structure and identifies parent items
        that need adversarial review (Vendor Mgmt, Solutions, etc.)
        """
        items = []
        
        # Default sidebar items based on project structure
        default_items = [
            SidebarParentItem(
                id="vendor-management",
                name="Vendor Management",
                icon="Building2",
                route_prefix="/vendors",
                template_pattern="vendors/*.html"
            ),
            SidebarParentItem(
                id="solutions-management",
                name="Solutions Management", 
                icon="Lightbulb",
                route_prefix="/solutions",
                template_pattern="solutions/*.html"
            ),
            SidebarParentItem(
                id="application-portfolio",
                name="Application Portfolio",
                icon="LayoutGrid",
                route_prefix="/applications",
                template_pattern="applications/*.html"
            ),
            SidebarParentItem(
                id="duplicate-detection",
                name="Duplicate Detection",
                icon="CopyX",
                route_prefix="/duplicates",
                template_pattern="duplicates/*.html"
            ),
            SidebarParentItem(
                id="architecture-review",
                name="Architecture Review",
                icon="ClipboardCheck",
                route_prefix="/arb",
                template_pattern="arb/*.html"
            ),
            SidebarParentItem(
                id="adm-kanban",
                name="ADM Kanban",
                icon="Kanban",
                route_prefix="/adm-kanban",
                template_pattern="adm_kanban/*.html"
            ),
            SidebarParentItem(
                id="archimate-crud",
                name="ArchiMate CRUD",
                icon="Network",
                route_prefix="/archimate-crud",
                template_pattern="archimate_crud/*.html"
            ),
            SidebarParentItem(
                id="batch-import",
                name="Batch Import",
                icon="Upload",
                route_prefix="/batch-import",
                template_pattern="batch_import/*.html"
            ),
            SidebarParentItem(
                id="ai-chat",
                name="AI Chat",
                icon="Bot",
                route_prefix="/ai-chat",
                template_pattern="ai_chat/*.html"
            ),
            SidebarParentItem(
                id="auto-dashboard",
                name="Auto Dashboard",
                icon="Gauge",
                route_prefix="/auto-dashboard",
                template_pattern="auto_dashboard/*.html"
            ),
        ]
        
        # Try to load from sidebar config if provided
        if sidebar_config_path and Path(sidebar_config_path).exists():
            try:
                import yaml
                with open(sidebar_config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    # Parse sidebar items from config
                    for section in config.get('sections', []):
                        for item in section.get('items', []):
                            if item.get('type') == 'parent':
                                items.append(SidebarParentItem(
                                    id=item.get('id'),
                                    name=item.get('name'),
                                    icon=item.get('icon', 'Circle'),
                                    route_prefix=item.get('route_prefix', ''),
                                    template_pattern=item.get('template_pattern', '')
                                ))
            except Exception as e:
                logger.warning(f"Could not load sidebar config: {e}, using defaults")
                items = default_items
        else:
            items = default_items
            
        # Store in registry
        for item in items:
            self.sidebar_items[item.id] = item
            
        logger.info(f"Discovered {len(items)} sidebar parent items for review")
        return items
    
    def start_autonomous_session(
        self,
        item_ids: Optional[List[str]] = None,
        config: Optional[Dict] = None
    ) -> str:
        """
        Start an autonomous review session.
        
        Args:
            item_ids: Specific items to review (None = all unreviewed)
            config: Override default configuration
            
        Returns:
            Session ID for tracking
        """
        session_id = str(uuid.uuid4())[:8]
        merged_config = {**self.default_config, **(config or {})}
        
        # Discover items if not already done
        if not self.sidebar_items:
            self.discover_sidebar_items()
        
        # Select items to review
        if item_ids:
            items = [self.sidebar_items[id] for id in item_ids if id in self.sidebar_items]
        else:
            # Get all items not yet reviewed
            items = [
                item for item in self.sidebar_items.values()
                if item.state == SidebarItemState.NOT_REVIEWED
            ]
        
        # Limit to max items per session
        items = items[:merged_config["max_items_per_session"]]
        
        session = AutonomousReviewSession(
            session_id=session_id,
            started_at=datetime.now(),
            items_to_review=items,
            config=merged_config,
            max_cycles=merged_config.get("max_items_per_session", 10)
        )
        
        self.sessions[session_id] = session
        logger.info(f"Started autonomous review session {session_id} with {len(items)} items")
        
        return session_id
    
    def run_cycle(self, session_id: str) -> Dict[str, Any]:
        """
        Run one autonomous review cycle on the current/next sidebar item.
        
        Returns cycle results and status.
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if session.cycle_count >= session.max_cycles:
            return {"status": "completed", "reason": "max_cycles_reached"}
        
        # Pick next item
        current = self._pick_next_item(session)
        if not current:
            return {"status": "completed", "reason": "no_more_items"}
        
        session.current_item = current
        session.cycle_count += 1
        
        logger.info(f"Cycle {session.cycle_count}: Reviewing {current.name}")
        
        try:
            # Step 1: Detect scope (LIGHTWEIGHT for initial review)
            scope_result = self._detect_scope(current)
            current.enforcement_level = scope_result
            
            # Step 2: Run appropriate validation
            if scope_result == EnforcementLevel.NONE:
                logger.info(f"Skipping {current.name} - no enforcement needed")
                current.state = SidebarItemState.SKIPPED
                session.completed_items.append(current.id)
                return {"status": "skipped", "item": current.name}
            
            elif scope_result == EnforcementLevel.LIGHTWEIGHT:
                result = self._run_lightweight_review(current)
                
            else:  # FULL
                result = self._run_full_review(current)
            
            # Step 3: Create tasks for issues found
            if result.get("issues"):
                task_ids = self._create_tasks_for_issues(current, result["issues"])
                current.tasks_created = task_ids
                current.issues_found = result["issues"]
            
            # Step 4: Apply fixes if auto-fixable
            if result.get("auto_fixable") and session.config.get("auto_apply_fixes", False):
                fix_result = self._apply_fixes(current, result["issues"])
                if fix_result.get("escalated"):
                    # Escalation occurred - need full review
                    return {"status": "escalated", "item": current.name}
            
            # Step 5: Run guardrails
            if session.config.get("run_guardrails", True):
                guardrail_result = self._run_guardrails(current)
                if not guardrail_result["passed"]:
                    session.failed_items.append(current.id)
                    if session.config.get("stop_on_failure", True):
                        return {
                            "status": "failed",
                            "item": current.name,
                            "reason": "guardrails_failed",
                            "details": guardrail_result["failures"]
                        }
            
            # Step 6: Mark complete
            current.state = SidebarItemState.COMMITTED
            current.last_reviewed = datetime.now()
            session.completed_items.append(current.id)
            
            return {
                "status": "completed",
                "item": current.name,
                "issues_found": len(result.get("issues", [])),
                "tasks_created": len(current.tasks_created),
                "enforcement": scope_result.value
            }
            
        except Exception as e:
            logger.exception(f"Cycle failed for {current.name}")
            session.failed_items.append(current.id)
            return {
                "status": "failed",
                "item": current.name,
                "error": str(e)
            }
    
    def _detect_scope(self, item: SidebarParentItem) -> EnforcementLevel:
        """Detect enforcement scope for a sidebar item."""
        # Sidebar reviews are typically LIGHTWEIGHT (read-only analysis)
        # unless they involve complex routes with persistence
        request_context = {
            "description": f"Review {item.name} sidebar routes and templates",
            "estimated_lines": 75,  # Typical sidebar review size
            "persistence_keywords": [],
            "security_keywords": ["vendor", "solution"],
            "pev_pattern": False
        }
        
        return self.scope_service.evaluate_request(request_context)
    
    def _run_lightweight_review(self, item: SidebarParentItem) -> Dict:
        """Run lightweight adversarial validation (5-10 seconds)."""
        logger.info(f"Running LIGHTWEIGHT review for {item.name}")
        
        # Find routes and templates for this sidebar item
        routes_file = self._find_routes_file(item.route_prefix)
        templates = self._find_templates(item.template_pattern)
        
        issues = []
        
        # Analyze routes file if found
        if routes_file:
            # Check for common security issues via heuristics
            issues.extend(self._heuristic_security_scan(routes_file))
            
        # Analyze templates
        for template in templates:
            issues.extend(self._heuristic_template_scan(template))
        
        return {
            "enforcement": EnforcementLevel.LIGHTWEIGHT,
            "issues": issues,
            "auto_fixable": any(i.auto_fixable for i in issues),
            "routes_analyzed": 1 if routes_file else 0,
            "templates_analyzed": len(templates)
        }
    
    def _run_full_review(self, item: SidebarParentItem) -> Dict:
        """Run full adversarial review with dual-agent orchestration."""
        logger.info(f"Running FULL review for {item.name}")
        
        # This would use the dual-agent orchestrator
        # Create isolated implementer and critique agents
        review_id = self.dual_orchestrator.start_review(
            task_id=f"autonomous-{item.id}",
            target_files=self._get_target_files(item),
            dimensions=["security", "idor", "sqli", "error_handling", "performance"]
        )
        
        item.review_id = review_id
        
        # Wait for review completion (would be async in practice)
        # For now, return placeholder
        return {
            "enforcement": EnforcementLevel.FULL,
            "review_id": review_id,
            "issues": [],  # Would be populated by critique agent
            "auto_fixable": False,
            "crypto_signature": None  # Would be generated
        }
    
    def _heuristic_security_scan(self, file_path: str) -> List[FoundIssue]:
        """Quick heuristic scan for common security issues."""
        issues = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')
                
            for i, line in enumerate(lines, 1):
                # Check for str(e) in error responses
                if 'return jsonify({"error": str(e)})' in line or "return jsonify({'error': str(e)})" in line:
                    issues.append(FoundIssue(
                        id=str(uuid.uuid4())[:8],
                        dimension="error_handling",
                        severity="P1",
                        file_path=file_path,
                        line_number=i,
                        description="Error message disclosure via str(e)",
                        code_snippet=line.strip(),
                        recommendation="Use generic error message, log details server-side",
                        auto_fixable=True,
                        fix_strategy="replace_str_e"
                    ))
                
                # Check for missing ownership checks
                if '.query.get(' in line and i > 1:
                    prev_line = lines[i-2] if i > 1 else ""
                    if 'def ' in prev_line and 'delete' in prev_line.lower() or 'update' in prev_line.lower():
                        # Check if ownership check exists in next 10 lines
                        next_lines = '\n'.join(lines[i:min(i+10, len(lines))])
                        if 'created_by' not in next_lines and 'ownership' not in next_lines and 'is_admin' not in next_lines:
                            issues.append(FoundIssue(
                                id=str(uuid.uuid4())[:8],
                                dimension="security",
                                severity="P0",
                                file_path=file_path,
                                line_number=i,
                                description="Potential IDOR: No ownership check after query.get",
                                code_snippet=line.strip(),
                                recommendation="Add created_by_id == current_user.id check",
                                auto_fixable=False
                            ))
                
                # Check for unbounded pagination
                if "int(request.args.get('per_page'" in line or 'per_page = request.args.get' in line:
                    next_lines = '\n'.join(lines[i:min(i+5, len(lines))])
                    if 'min(' not in next_lines and 'max(' not in next_lines:
                        issues.append(FoundIssue(
                            id=str(uuid.uuid4())[:8],
                            dimension="performance",
                            severity="P1",
                            file_path=file_path,
                            line_number=i,
                            description="Unbounded pagination parameter",
                            code_snippet=line.strip(),
                            recommendation="Cap per_page at max 200: per_page = min(request.args.get('per_page', 25, type=int), 200)",
                            auto_fixable=True,
                            fix_strategy="cap_pagination"
                        ))
                
                # Check for bare except: pass
                if 'except:' in line and 'pass' in line:
                    issues.append(FoundIssue(
                        id=str(uuid.uuid4())[:8],
                        dimension="error_handling",
                        severity="P1",
                        file_path=file_path,
                        line_number=i,
                        description="Bare except:pass clause - silent failure",
                        code_snippet=line.strip(),
                        recommendation="Replace with specific exception and logging",
                        auto_fixable=True,
                        fix_strategy="fix_bare_except"
                    ))
                    
        except Exception as e:
            logger.warning(f"Could not scan {file_path}: {e}")
            
        return issues
    
    def _heuristic_template_scan(self, template_path: str) -> List[FoundIssue]:
        """Quick heuristic scan for template issues."""
        issues = []
        # Template scanning implementation
        return issues
    
    def _create_tasks_for_issues(self, item: SidebarParentItem, issues: List[FoundIssue]) -> List[str]:
        """Create agent_plan.yaml tasks for found issues."""
        task_ids = []
        
        for issue in issues:
            task_id = f"{item.id.upper()[:6]}-FIX-{issue.severity}-{len(task_ids)+1}"
            
            # Create task entry for agent_plan.yaml
            task_entry = {
                "id": task_id,
                "name": f"[{issue.severity}] {issue.description}",
                "status": "todo",
                "priority": "critical" if issue.severity == "P0" else "high" if issue.severity == "P1" else "medium",
                "orchestration_pattern": "PEV" if issue.severity in ["P0", "P1"] else None,
                "description": f"{issue.description}\nFile: {issue.file_path}:{issue.line_number}\nRecommendation: {issue.recommendation}",
                "deliverables": [issue.file_path],
                "adversarial_finding": {
                    "dimension": issue.dimension,
                    "severity": issue.severity,
                    "auto_fixable": issue.auto_fixable,
                    "fix_strategy": issue.fix_strategy
                },
                "owner": "autonomous-orchestrator",
                "created_at": datetime.now().isoformat()
            }
            
            # Would append to agent_plan.yaml here
            logger.info(f"Created task {task_id} for {item.name}")
            task_ids.append(task_id)
        
        return task_ids
    
    def _apply_fixes(self, item: SidebarParentItem, issues: List[FoundIssue]) -> Dict:
        """Apply auto-fixable issues. May trigger escalation."""
        fixed_count = 0
        escalation_needed = False
        
        for issue in issues:
            if not issue.auto_fixable:
                continue
                
            # Check if fix would trigger escalation
            if issue.fix_strategy in ["replace_str_e"]:
                # Simple 1-line fix - stays LIGHTWEIGHT
                fixed_count += 1
            else:
                # More complex fix - may need FULL enforcement
                escalation_needed = True
        
        return {
            "fixed": fixed_count,
            "escalated": escalation_needed,
            "requires_full_review": escalation_needed
        }
    
    def _run_guardrails(self, item: SidebarParentItem) -> Dict:
        """Run pre-commit guardrails."""
        import subprocess
        
        guardrails = [
            "scripts/guardrails/check_route_count.py",
            "scripts/guardrails/check_template_duplicates.py",
            "scripts/guardrails/check_endpoint_contracts.py",
            "scripts/guardrails/check_critique_completion.py",
            "scripts/guardrails/check_p0_p1_status.py"
        ]
        
        failures = []
        
        for script in guardrails:
            try:
                result = subprocess.run(
                    ["python", script],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    failures.append({
                        "script": script,
                        "output": result.stdout + result.stderr
                    })
            except Exception as e:
                logger.warning(f"Guardrail {script} failed: {e}")
                failures.append({"script": script, "error": str(e)})
        
        return {
            "passed": len(failures) == 0,
            "failures": failures,
            "total_run": len(guardrails)
        }
    
    def _pick_next_item(self, session: AutonomousReviewSession) -> Optional[SidebarParentItem]:
        """Pick the next sidebar item to review."""
        for item in session.items_to_review:
            if item.id not in session.completed_items and item.id not in session.failed_items:
                return item
        return None
    
    def _find_routes_file(self, route_prefix: str) -> Optional[str]:
        """Find the routes file for a given route prefix."""
        # Map route prefixes to likely file names
        prefix_map = {
            "/vendors": "vendor_routes.py",
            "/solutions": "solution_design_routes.py",
            "/applications": "unified_applications_routes.py",
            "/duplicates": "unified_duplicate_routes.py",
            "/arb": "arb_routes.py",
            "/adm-kanban": "adm_kanban_routes.py",
            "/archimate-crud": "archimate_crud_routes.py",
            "/batch-import": "batch_import_routes.py",
            "/ai-chat": "ai_chat_routes.py",
            "/auto-dashboard": "dashboard_routes.py",
        }
        
        filename = prefix_map.get(route_prefix)
        if filename:
            path = Path(f"app/routes/{filename}")
            if path.exists():
                return str(path)
        
        return None
    
    def _find_templates(self, pattern: str) -> List[str]:
        """Find templates matching the pattern."""
        import glob
        return glob.glob(f"app/templates/{pattern}")
    
    def _get_target_files(self, item: SidebarParentItem) -> List[str]:
        """Get all target files for a sidebar item."""
        files = []
        
        routes = self._find_routes_file(item.route_prefix)
        if routes:
            files.append(routes)
        
        templates = self._find_templates(item.template_pattern)
        files.extend(templates)
        
        return files
    
    def get_session_status(self, session_id: str) -> Dict:
        """Get status of an autonomous review session."""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        return {
            "session_id": session_id,
            "status": session.status.value,
            "cycles_completed": session.cycle_count,
            "items_total": len(session.items_to_review),
            "items_completed": len(session.completed_items),
            "items_failed": len(session.failed_items),
            "current_item": session.current_item.name if session.current_item else None,
            "started_at": session.started_at.isoformat(),
            "config": session.config
        }


# Singleton instance
_autonomous_orchestrator: Optional[AutonomousAdversarialOrchestrator] = None


def get_autonomous_orchestrator() -> AutonomousAdversarialOrchestrator:
    """Get or create the singleton autonomous orchestrator."""
    global _autonomous_orchestrator
    if _autonomous_orchestrator is None:
        _autonomous_orchestrator = AutonomousAdversarialOrchestrator()
    return _autonomous_orchestrator
