import uuid
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

class JobManager:
    """In-memory thread-safe background job runner for long-running pipeline tasks.
    
    NOTE: Job state is stored in-memory and will not survive a backend server restart.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(JobManager, cls).__new__(cls)
                    cls._instance.jobs = {}
        return cls._instance

    def submit_job(self, task_name: str, target: Callable, project_id: Optional[str] = None, *args, **kwargs) -> str:
        """Submit a background job. Prevents duplicate active jobs for the same project if project_id is provided."""
        with self._lock:
            if project_id:
                for jid, job in self.jobs.items():
                    if job.get("project_id") == project_id and job.get("status") in ["queued", "running"]:
                        raise ValueError(f"An active job already exists for project {project_id} (job_id: {jid})")

            job_id = str(uuid.uuid4())
            self.jobs[job_id] = {
                "id": job_id,
                "project_id": project_id,
                "task_name": task_name,
                "status": "running",
                "progress": 0.0,
                "message": "Starting task...",
                "result": None,
                "error": None,
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": None
            }

        def worker():
            try:
                logger.info(f"Background job {job_id} ({task_name}) started.")
                result = target(job_id, *args, **kwargs)
                with self._lock:
                    if isinstance(result, dict) and result.get("errors"):
                        self.jobs[job_id]["status"] = "failed"
                        self.jobs[job_id]["progress"] = 100.0
                        self.jobs[job_id]["message"] = f"Partial generation with errors: {'; '.join(result['errors'])}"
                        self.jobs[job_id]["error"] = "; ".join(result["errors"])
                        self.jobs[job_id]["result"] = result
                        self.jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
                    else:
                        self.jobs[job_id]["status"] = "completed"
                        self.jobs[job_id]["progress"] = 100.0
                        self.jobs[job_id]["message"] = "Completed successfully."
                        self.jobs[job_id]["result"] = result
                        self.jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
                logger.info(f"Background job {job_id} ({task_name}) finished.")
            except Exception as e:
                logger.error(f"Background job {job_id} ({task_name}) failed: {e}", exc_info=True)
                with self._lock:
                    self.jobs[job_id]["status"] = "failed"
                    self.jobs[job_id]["error"] = str(e)
                    self.jobs[job_id]["message"] = f"Generation failed: {str(e)}"
                    self.jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return job_id

    def update_progress(self, job_id: str, progress: float, message: str, extra: Optional[Dict[str, Any]] = None):
        """Update the progress percentage and status message of a running job."""
        with self._lock:
            if job_id in self.jobs:
                self.jobs[job_id]["progress"] = progress
                self.jobs[job_id]["message"] = message
                if extra:
                    self.jobs[job_id].update(extra)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve job state by job ID."""
        with self._lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None

    def get_active_job_for_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the currently active job for a project, if any."""
        with self._lock:
            for job in self.jobs.values():
                if job.get("project_id") == project_id and job.get("status") in ["queued", "running"]:
                    return dict(job)
            return None

    def clear_jobs(self):
        """Reset in-memory job state (useful for test isolation)."""
        with self._lock:
            self.jobs.clear()

job_manager = JobManager()
