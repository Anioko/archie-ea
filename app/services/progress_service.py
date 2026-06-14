"""
Progress Tracking Service for Long-Running Operations

Provides real-time progress updates using Server-Sent Events (SSE).
Supports multi-stage pipeline progress tracking.
"""

import json
import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, Generator, Optional


class ProgressTracker:
    """
    Tracks progress for long-running operations and provides SSE streams
    """

    def __init__(self):
        """Initialize progress tracker with in-memory storage"""
        self._progress_data = {}  # {task_id: progress_info}
        self._lock = threading.Lock()

    def create_task(self, task_id: str, total_stages: int, description: str = "") -> None:
        """
        Create a new task to track

        Args:
            task_id: Unique identifier for the task
            total_stages: Total number of stages in the task
            description: Optional description of the task
        """
        with self._lock:
            self._progress_data[task_id] = {
                "task_id": task_id,
                "description": description,
                "total_stages": total_stages,
                "current_stage": 0,
                "stage_name": "",
                "status": "pending",
                "progress_percent": 0,
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": None,
                "stages_completed": [],
                "current_stage_progress": 0,
                "errors": [],
                "warnings": [],
                "metadata": {},
            }

    def update_stage(
        self,
        task_id: str,
        stage_number: int,
        stage_name: str,
        stage_progress: int = 0,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Update the current stage of a task

        Args:
            task_id: Unique identifier for the task
            stage_number: Current stage number (1 - indexed)
            stage_name: Name of the current stage
            stage_progress: Progress within the current stage (0 - 100)
            metadata: Optional metadata about the stage
        """
        with self._lock:
            if task_id not in self._progress_data:
                return

            task = self._progress_data[task_id]
            task["current_stage"] = stage_number
            task["stage_name"] = stage_name
            task["current_stage_progress"] = stage_progress
            task["status"] = "in_progress"

            # Calculate overall progress
            completed_stages = stage_number - 1
            stage_weight = 100 / task["total_stages"]
            current_stage_contribution = (stage_progress / 100) * stage_weight
            task["progress_percent"] = int(
                (completed_stages * stage_weight) + current_stage_contribution
            )

            if metadata:
                task["metadata"].update(metadata)

    def complete_stage(self, task_id: str, stage_name: str, result: Optional[Dict] = None) -> None:
        """
        Mark a stage as completed

        Args:
            task_id: Unique identifier for the task
            stage_name: Name of the completed stage
            result: Optional result data from the stage
        """
        with self._lock:
            if task_id not in self._progress_data:
                return

            task = self._progress_data[task_id]
            stage_info = {
                "stage_name": stage_name,
                "completed_at": datetime.utcnow().isoformat(),
                "result": result or {},
            }
            task["stages_completed"].append(stage_info)

    def add_error(self, task_id: str, error: str) -> None:
        """
        Add an error message to the task

        Args:
            task_id: Unique identifier for the task
            error: Error message
        """
        with self._lock:
            if task_id not in self._progress_data:
                return
            self._progress_data[task_id]["errors"].append(
                {"timestamp": datetime.utcnow().isoformat(), "message": error}
            )

    def add_warning(self, task_id: str, warning: str) -> None:
        """
        Add a warning message to the task

        Args:
            task_id: Unique identifier for the task
            warning: Warning message
        """
        with self._lock:
            if task_id not in self._progress_data:
                return
            self._progress_data[task_id]["warnings"].append(
                {"timestamp": datetime.utcnow().isoformat(), "message": warning}
            )

    def complete_task(
        self, task_id: str, status: str = "completed", final_result: Optional[Dict] = None
    ) -> None:
        """
        Mark a task as completed

        Args:
            task_id: Unique identifier for the task
            status: Final status ('completed', 'failed', 'cancelled')
            final_result: Optional final result data
        """
        with self._lock:
            if task_id not in self._progress_data:
                return

            task = self._progress_data[task_id]
            task["status"] = status
            task["progress_percent"] = 100 if status == "completed" else task["progress_percent"]
            task["completed_at"] = datetime.utcnow().isoformat()

            if final_result:
                task["metadata"]["final_result"] = final_result

    def get_progress(self, task_id: str) -> Optional[Dict]:
        """
        Get current progress for a task

        Args:
            task_id: Unique identifier for the task

        Returns:
            Progress information or None if task doesn't exist
        """
        with self._lock:
            return self._progress_data.get(task_id, None)

    def stream_progress(self, task_id: str, timeout: int = 300) -> Generator[str, None, None]:
        """
        Stream progress updates using Server-Sent Events (SSE)

        Args:
            task_id: Unique identifier for the task
            timeout: Maximum time to stream in seconds

        Yields:
            SSE-formatted progress messages
        """
        start_time = time.time()
        last_progress = None

        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                yield f'event: error\ndata: {{"error": "Stream timeout"}}\n\n'
                break

            # Get current progress
            current_progress = self.get_progress(task_id)

            if current_progress is None:
                yield f'event: error\ndata: {{"error": "Task not found"}}\n\n'
                break

            # Send update if progress changed
            if current_progress != last_progress:
                progress_json = json.dumps(current_progress)
                yield f"event: progress\ndata: {progress_json}\n\n"
                last_progress = current_progress.copy()

            # Check if task is complete
            if current_progress["status"] in ["completed", "failed", "cancelled"]:
                yield f"event: complete\ndata: {progress_json}\n\n"
                break

            # Poll every 0.5 seconds
            time.sleep(0.5)

    def cleanup_task(self, task_id: str) -> None:
        """
        Remove task data from memory

        Args:
            task_id: Unique identifier for the task
        """
        with self._lock:
            if task_id in self._progress_data:
                del self._progress_data[task_id]

    def cleanup_old_tasks(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up tasks older than max_age_seconds

        Args:
            max_age_seconds: Maximum age in seconds (default 1 hour)

        Returns:
            Number of tasks cleaned up
        """
        now = datetime.utcnow()
        removed_count = 0

        with self._lock:
            task_ids = list(self._progress_data.keys())
            for task_id in task_ids:
                task = self._progress_data[task_id]
                if task["completed_at"]:
                    completed_at = datetime.fromisoformat(task["completed_at"])
                    age = (now - completed_at).total_seconds()
                    if age > max_age_seconds:
                        del self._progress_data[task_id]
                        removed_count += 1

        return removed_count


# Global singleton instance
_progress_tracker = None


def get_progress_tracker() -> ProgressTracker:
    """
    Get the global ProgressTracker instance

    Returns:
        ProgressTracker singleton
    """
    global _progress_tracker
    if _progress_tracker is None:
        _progress_tracker = ProgressTracker()
    return _progress_tracker
