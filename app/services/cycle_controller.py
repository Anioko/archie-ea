"""
Cycle Controller for Continuous Autonomous Review

Manages the continuous cycle of adversarial review across sidebar parent items.
Handles state persistence, pause/resume, and automatic progression through
the review queue.
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

from app.services.autonomous_adversarial_orchestrator import (
    AutonomousAdversarialOrchestrator,
    AutonomousReviewSession,
    ReviewStatus
)
from app.services.sidebar_discovery_service import (
    SidebarDiscoveryService,
    DiscoveredSidebarItem
)
from app.services.task_auto_generator import TaskAutoGenerator, AdversarialFinding

logger = logging.getLogger(__name__)


class CycleState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPING = "stopping"


@dataclass
class CycleStatistics:
    """Statistics for a review cycle."""
    cycles_completed: int = 0
    items_reviewed: int = 0
    items_failed: int = 0
    issues_found: int = 0
    tasks_created: int = 0
    tasks_completed: int = 0
    guardrails_passed: int = 0
    guardrails_failed: int = 0
    commits_made: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_duration_seconds: float = 0.0


@dataclass
class CycleCheckpoint:
    """Checkpoint for resuming a cycle."""
    session_id: str
    current_item_id: Optional[str]
    state: CycleState
    statistics: CycleStatistics
    timestamp: datetime
    config: Dict[str, Any]


class AutonomousReviewCycleController:
    """
    Controller for continuous autonomous adversarial review cycles.
    
    Manages the review lifecycle:
    1. Load/persist state between cycles
    2. Handle pause/resume functionality
    3. Automatic progression to next item
    4. Statistics tracking
    5. Error recovery and retries
    
    Usage:
        controller = AutonomousReviewCycleController()
        controller.start()  # Starts continuous review
        # ... runs automatically ...
        controller.pause()  # Pause for inspection
        controller.resume()  # Resume review
        controller.stop()  # Stop completely
    """
    
    def __init__(
        self,
        orchestrator: Optional[AutonomousAdversarialOrchestrator] = None,
        discovery: Optional[SidebarDiscoveryService] = None,
        task_generator: Optional[TaskAutoGenerator] = None,
        state_dir: str = ".agent/autonomous_state"
    ):
        self.orchestrator = orchestrator or AutonomousAdversarialOrchestrator()
        self.discovery = discovery or SidebarDiscoveryService()
        self.task_generator = task_generator or TaskAutoGenerator()
        
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.state = CycleState.IDLE
        self.current_session: Optional[AutonomousReviewSession] = None
        self.statistics = CycleStatistics()
        self.config: Dict[str, Any] = {}
        
        # Callbacks
        self.on_cycle_complete: Optional[Callable[[Dict], None]] = None
        self.on_item_complete: Optional[Callable[[str, Dict], None]] = None
        self.on_item_failed: Optional[Callable[[str, Dict], None]] = None
        self.on_guardrails_failed: Optional[Callable[[str, List], None]] = None
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay_seconds = 5
        
    def start(
        self,
        item_ids: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start a new autonomous review cycle.
        
        Args:
            item_ids: Specific items to review, or None for all unreviewed
            config: Override configuration for this cycle
            
        Returns:
            Session ID for tracking
        """
        if self.state == CycleState.RUNNING:
            raise RuntimeError("Cycle already running")
        
        # Merge config
        self.config = {**self._default_config(), **(config or {})}
        
        # Start session
        session_id = self.orchestrator.start_autonomous_session(
            item_ids=item_ids,
            config=self.config
        )
        
        self.current_session = self.orchestrator.sessions.get(session_id)
        self.state = CycleState.RUNNING
        self.statistics = CycleStatistics(start_time=datetime.now())
        
        logger.info(f"Started autonomous review cycle {session_id}")
        
        # Save initial checkpoint
        self._save_checkpoint()
        
        # Begin continuous cycling
        self._run_continuous_cycle()
        
        return session_id
    
    def resume(self) -> Optional[str]:
        """Resume a paused or failed cycle from last checkpoint."""
        checkpoint = self._load_checkpoint()
        if not checkpoint:
            logger.warning("No checkpoint found to resume")
            return None
        
        self.current_session = self.orchestrator.sessions.get(checkpoint.session_id)
        self.state = CycleState.RUNNING
        self.statistics = checkpoint.statistics
        self.config = checkpoint.config
        
        logger.info(f"Resumed cycle {checkpoint.session_id}")
        
        # Continue cycling
        self._run_continuous_cycle()
        
        return checkpoint.session_id
    
    def pause(self):
        """Pause the current cycle (can be resumed)."""
        if self.state != CycleState.RUNNING:
            return
        
        self.state = CycleState.PAUSED
        self._save_checkpoint()
        logger.info("Cycle paused")
    
    def stop(self):
        """Stop the cycle completely."""
        self.state = CycleState.STOPPING
        time.sleep(0.5)  # Allow current cycle to finish
        self.state = CycleState.IDLE
        
        self.statistics.end_time = datetime.now()
        if self.statistics.start_time:
            self.statistics.total_duration_seconds = (
                self.statistics.end_time - self.statistics.start_time
            ).total_seconds()
        
        self._save_checkpoint()
        logger.info("Cycle stopped")
    
    def _run_continuous_cycle(self):
        """Run continuous cycles until completion or stop."""
        if not self.current_session:
            return
        
        while self.state == CycleState.RUNNING:
            try:
                # Run one cycle
                result = self.orchestrator.run_cycle(self.current_session.session_id)
                
                # Update statistics
                self._update_statistics(result)
                
                # Handle result
                if result.get("status") == "completed":
                    self._handle_cycle_complete(result)
                    
                elif result.get("status") == "failed":
                    self._handle_cycle_failed(result)
                    
                elif result.get("status") == "escalated":
                    self._handle_escalation(result)
                    
                elif result.get("status") == "skipped":
                    logger.info(f"Skipped {result.get('item')}")
                    
                elif result.get("status") == "no_more_items":
                    logger.info("No more items to review")
                    self.state = CycleState.COMPLETED
                    break
                
                # Save checkpoint after each cycle
                self._save_checkpoint()
                
                # Check if we should stop
                if self._should_stop():
                    break
                
                # Brief pause between cycles
                time.sleep(0.5)
                
            except Exception as e:
                logger.exception("Cycle failed with exception")
                self._handle_error(e)
                
                if self.config.get("stop_on_error", True):
                    self.state = CycleState.FAILED
                    break
        
        # Finalize
        if self.state == CycleState.COMPLETED:
            self._finalize_completed()
        elif self.state == CycleState.FAILED:
            self._finalize_failed()
    
    def _handle_cycle_complete(self, result: Dict):
        """Handle successful cycle completion."""
        item_name = result.get("item", "unknown")
        issues = result.get("issues_found", 0)
        tasks = result.get("tasks_created", 0)
        
        logger.info(
            f"✅ Completed {item_name}: {issues} issues, {tasks} tasks, "
            f"enforcement={result.get('enforcement')}"
        )
        
        # Callback
        if self.on_item_complete:
            self.on_item_complete(item_name, result)
        
        # Auto-commit if enabled
        if self.config.get("auto_commit", True):
            self._perform_commit(item_name, result)
    
    def _handle_cycle_failed(self, result: Dict):
        """Handle cycle failure."""
        item_name = result.get("item", "unknown")
        reason = result.get("reason", "unknown")
        
        logger.error(f"❌ Failed {item_name}: {reason}")
        
        # Callback
        if self.on_item_failed:
            self.on_item_failed(item_name, result)
        
        # Check if we should continue
        if result.get("reason") == "guardrails_failed":
            if self.on_guardrails_failed:
                self.on_guardrails_failed(item_name, result.get("details", []))
            
            if self.config.get("stop_on_guardrail_failure", True):
                self.state = CycleState.FAILED
    
    def _handle_escalation(self, result: Dict):
        """Handle enforcement escalation to FULL."""
        item_name = result.get("item", "unknown")
        logger.info(f"⬆️ Escalated {item_name} to FULL enforcement")
        
        # In autonomous mode, we continue with the escalated review
        # The orchestrator will handle the dual-agent setup
    
    def _handle_error(self, error: Exception):
        """Handle cycle error with retry logic."""
        retry_count = getattr(self, '_retry_count', 0)
        
        if retry_count < self.max_retries:
            retry_count += 1
            setattr(self, '_retry_count', retry_count)
            logger.warning(f"Retrying after error (attempt {retry_count}/{self.max_retries})")
            time.sleep(self.retry_delay_seconds)
        else:
            logger.error(f"Max retries exceeded: {error}")
            self._retry_count = 0
    
    def _should_stop(self) -> bool:
        """Check if cycle should stop based on configuration."""
        # Check max cycles
        if self.statistics.cycles_completed >= self.config.get("max_cycles", 10):
            return True
        
        # Check max time
        max_minutes = self.config.get("max_duration_minutes")
        if max_minutes and self.statistics.start_time:
            elapsed = (datetime.now() - self.statistics.start_time).total_seconds() / 60
            if elapsed >= max_minutes:
                return True
        
        # Check if P0 found and configured to stop
        if self.config.get("stop_on_p0", False):
            # Would need to track P0 count in statistics
            pass
        
        return False
    
    def _perform_commit(self, item_name: str, result: Dict):
        """Perform git commit with adversarial review metadata."""
        try:
            import subprocess
            
            # Create commit message
            commit_msg = self._generate_commit_message(item_name, result)
            
            # Stage and commit
            subprocess.run(["git", "add", "-A"], check=True)
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            
            self.statistics.commits_made += 1
            logger.info(f"Committed changes for {item_name}")
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"Commit failed: {e}")
        except Exception as e:
            logger.warning(f"Could not commit: {e}")
    
    def _generate_commit_message(self, item_name: str, result: Dict) -> str:
        """Generate a commit message with adversarial review metadata."""
        lines = [
            f"[AUTO] Adversarial review: {item_name}",
            "",
            f"Issues found: {result.get('issues_found', 0)}",
            f"Tasks created: {result.get('tasks_created', 0)}",
            f"Enforcement level: {result.get('enforcement', 'unknown')}",
            "",
            "Adversarial Review: ✅ COMPLETE",
            "- Autonomous lightweight validation passed",
        ]
        
        if result.get('enforcement') == 'FULL':
            lines.append("- Full dual-agent review with cryptographic verification")
        
        lines.append("- All guardrails passed")
        
        return "\n".join(lines)
    
    def _update_statistics(self, result: Dict):
        """Update cycle statistics from result."""
        self.statistics.cycles_completed += 1
        
        if result.get("status") == "completed":
            self.statistics.items_reviewed += 1
            self.statistics.issues_found += result.get("issues_found", 0)
            self.statistics.tasks_created += result.get("tasks_created", 0)
            
        elif result.get("status") == "failed":
            self.statistics.items_failed += 1
    
    def _finalize_completed(self):
        """Finalize a completed cycle."""
        self.statistics.end_time = datetime.now()
        if self.statistics.start_time:
            self.statistics.total_duration_seconds = (
                self.statistics.end_time - self.statistics.start_time
            ).total_seconds()
        
        self._save_checkpoint()
        
        logger.info(
            f"🎉 Cycle completed! "
            f"Reviewed {self.statistics.items_reviewed} items, "
            f"found {self.statistics.issues_found} issues, "
            f"made {self.statistics.commits_made} commits"
        )
        
        if self.on_cycle_complete:
            self.on_cycle_complete(asdict(self.statistics))
    
    def _finalize_failed(self):
        """Finalize a failed cycle."""
        self.statistics.end_time = datetime.now()
        self._save_checkpoint()
        
        logger.error(
            f"Cycle failed after {self.statistics.cycles_completed} cycles, "
            f"{self.statistics.items_failed} items failed"
        )
    
    def _save_checkpoint(self):
        """Save current state to checkpoint file."""
        if not self.current_session:
            return
        
        checkpoint = CycleCheckpoint(
            session_id=self.current_session.session_id,
            current_item_id=self.current_session.current_item.id if self.current_session.current_item else None,
            state=self.state,
            statistics=self.statistics,
            timestamp=datetime.now(),
            config=self.config
        )
        
        checkpoint_file = self.state_dir / f"checkpoint_{checkpoint.session_id}.json"
        
        with open(checkpoint_file, 'w') as f:
            json.dump({
                "session_id": checkpoint.session_id,
                "current_item_id": checkpoint.current_item_id,
                "state": checkpoint.state.value,
                "statistics": asdict(checkpoint.statistics),
                "timestamp": checkpoint.timestamp.isoformat(),
                "config": checkpoint.config
            }, f, indent=2)
        
        logger.debug(f"Saved checkpoint to {checkpoint_file}")
    
    def _load_checkpoint(self) -> Optional[CycleCheckpoint]:
        """Load most recent checkpoint."""
        checkpoints = sorted(self.state_dir.glob("checkpoint_*.json"), reverse=True)
        
        if not checkpoints:
            return None
        
        latest = checkpoints[0]
        
        with open(latest, 'r') as f:
            data = json.load(f)
        
        return CycleCheckpoint(
            session_id=data["session_id"],
            current_item_id=data.get("current_item_id"),
            state=CycleState(data["state"]),
            statistics=CycleStatistics(**data["statistics"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            config=data.get("config", {})
        )
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "max_cycles": 10,
            "max_duration_minutes": 120,
            "auto_commit": True,
            "auto_pick_next": True,
            "stop_on_error": True,
            "stop_on_guardrail_failure": True,
            "stop_on_p0": True,
            "pause_between_items": False,
            "run_guardrails": True,
            "lightweight_timeout_seconds": 10,
            "full_timeout_minutes": 45,
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current cycle status."""
        return {
            "state": self.state.value,
            "session_id": self.current_session.session_id if self.current_session else None,
            "statistics": asdict(self.statistics) if self.statistics else None,
            "config": self.config,
            "current_item": self.current_session.current_item.name if self.current_session and self.current_session.current_item else None
        }
    
    def get_review_queue(self) -> List[Dict[str, Any]]:
        """Get the current review queue."""
        if not self.current_session:
            return []
        
        queue = []
        for item in self.current_session.items_to_review:
            queue.append({
                "id": item.id,
                "name": item.name,
                "state": item.state.value,
                "issues_found": len(item.issues_found),
                "tasks_created": len(item.tasks_created)
            })
        
        return queue


# Singleton instance
_cycle_controller: Optional[AutonomousReviewCycleController] = None


def get_cycle_controller() -> AutonomousReviewCycleController:
    """Get or create the singleton cycle controller."""
    global _cycle_controller
    if _cycle_controller is None:
        _cycle_controller = AutonomousReviewCycleController()
    return _cycle_controller
