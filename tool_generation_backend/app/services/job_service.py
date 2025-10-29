"""
Job service for managing bulk tool generation workflows.
Orchestrates multiple task spawns and tracks overall job progress.
"""

import logging
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.models.job import Job, JobStatus
from app.models.specs import UserToolRequirement
from app.repositories.job_repository import JobRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.tool_repository import ToolRepository
from app.repositories.tool_failure_repository import ToolFailureRepository
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


class JobService:
    """
    Service for managing jobs (bulk tool generation workflows).

    A Job represents a user request to generate multiple tools.
    This service spawns multiple Tasks (one per tool) and tracks overall progress.
    """

    def __init__(self):
        self.job_repo = JobRepository()
        self.task_repo = TaskRepository()
        self.tool_repo = ToolRepository()
        self.tool_failure_repo = ToolFailureRepository()

    async def create_job(
        self,
        user_id: str,
        tool_requirements: List[UserToolRequirement]
    ) -> str:
        """
        Create a new job and spawn tasks for each tool requirement.

        Args:
            user_id: User identifier
            tool_requirements: List of tool requirements to generate

        Returns:
            str: Job ID (MongoDB _id)
        """
        try:
            # Generate short job_id (e.g., job_abc123)
            job_id_short = f"job_{uuid.uuid4().hex[:8]}"

            # Create job document
            job_data = {
                "job_id": job_id_short,
                "user_id": user_id,
                "operation_type": "generate",
                "tool_requirements": [req.model_dump() for req in tool_requirements],
                "status": JobStatus.PENDING.value,
                "task_ids": [],
                "tools_completed": 0,
                "tools_failed": 0,
                "tools_in_progress": 0,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            job_id = await self.job_repo.create_job(job_data)
            logger.info(f"Created job {job_id_short} (DB ID: {job_id}) with {len(tool_requirements)} tool requirements")

            # Update job status to PROCESSING
            await self.job_repo.update_status(job_id, JobStatus.PROCESSING)

            # Spawn tasks for each tool requirement (asynchronously)
            # Don't await here - let tasks run in background
            asyncio.create_task(self._spawn_tasks(job_id, job_id_short, user_id, tool_requirements))

            return job_id

        except Exception as e:
            logger.error(f"Error creating job: {e}")
            raise

    async def _spawn_tasks(
        self,
        job_id: str,
        job_id_short: str,
        user_id: str,
        tool_requirements: List[UserToolRequirement]
    ):
        """
        Spawn multiple tasks (one per tool requirement).

        Args:
            job_id: Job ID (MongoDB _id)
            job_id_short: Short job identifier (e.g., job_abc123)
            user_id: User identifier
            tool_requirements: List of tool requirements
        """
        try:
            logger.info(f"Spawning {len(tool_requirements)} tasks for job {job_id_short}")

            # Import TaskService here to avoid circular imports
            task_service = TaskService(
                task_repo=self.task_repo,
                tool_repo=self.tool_repo,
                tool_failure_repo=self.tool_failure_repo
            )

            # Create tasks for each requirement (in parallel)
            task_creation_coroutines = []
            for req in tool_requirements:
                coro = task_service.create_task(
                    job_id=job_id,
                    job_id_short=job_id_short,
                    user_id=user_id,
                    requirement=req
                )
                task_creation_coroutines.append(coro)

            # Wait for all tasks to be created (but not completed)
            task_ids = await asyncio.gather(*task_creation_coroutines, return_exceptions=True)

            # Filter out exceptions and add task IDs to job
            for result in task_ids:
                if isinstance(result, str):  # Successful task creation
                    await self.job_repo.add_task_id(job_id, result)
                else:  # Exception occurred
                    logger.error(f"Failed to create task for job {job_id_short}: {result}")
                    await self.job_repo.increment_failed(job_id)

            logger.info(f"Spawned {len([r for r in task_ids if isinstance(r, str)])} tasks for job {job_id_short}")

        except Exception as e:
            logger.error(f"Error spawning tasks for job {job_id_short}: {e}")
            await self.job_repo.update_status(job_id, JobStatus.FAILED, error_message=str(e))

    async def get_job_by_id(self, job_id: str) -> Optional[Job]:
        """
        Get job by MongoDB _id.

        Args:
            job_id: Job ID (MongoDB _id)

        Returns:
            Optional[Job]: Job if found
        """
        return await self.job_repo.get_by_id(job_id)

    async def get_job_by_job_id(self, job_id_short: str) -> Optional[Job]:
        """
        Get job by short job_id field.

        Args:
            job_id_short: Short job identifier (e.g., job_abc123)

        Returns:
            Optional[Job]: Job if found
        """
        return await self.job_repo.get_by_job_id(job_id_short)

    async def increment_completed(self, job_id: str):
        """
        Atomically increment the tools_completed counter.
        Called by TaskService when a tool is successfully generated.

        Args:
            job_id: Job ID (MongoDB _id)
        """
        await self.job_repo.increment_completed(job_id)
        await self._check_job_completion(job_id)

    async def increment_failed(self, job_id: str):
        """
        Atomically increment the tools_failed counter.
        Called by TaskService when a tool generation fails.

        Args:
            job_id: Job ID (MongoDB _id)
        """
        await self.job_repo.increment_failed(job_id)
        await self._check_job_completion(job_id)

    async def increment_in_progress(self, job_id: str):
        """
        Atomically increment the tools_in_progress counter.
        Called by TaskService when a task starts processing.

        Args:
            job_id: Job ID (MongoDB _id)
        """
        await self.job_repo.increment_in_progress(job_id)

    async def decrement_in_progress(self, job_id: str):
        """
        Atomically decrement the tools_in_progress counter.
        Called by TaskService when a task completes (success or failure).

        Args:
            job_id: Job ID (MongoDB _id)
        """
        await self.job_repo.decrement_in_progress(job_id)

    async def _check_job_completion(self, job_id: str):
        """
        Check if job is complete and update status accordingly.

        Args:
            job_id: Job ID (MongoDB _id)
        """
        try:
            job = await self.job_repo.get_by_id(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            # Check if all tools have been processed
            if job.is_complete:
                logger.info(f"Job {job.job_id} is complete: {job.tools_completed} succeeded, {job.tools_failed} failed")
                await self.job_repo.update_status(job_id, JobStatus.COMPLETED)

        except Exception as e:
            logger.error(f"Error checking job completion for {job_id}: {e}")

    async def get_job_tasks(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get all tasks for a job.

        Args:
            job_id: Job ID (MongoDB _id)

        Returns:
            List[Dict]: List of task data
        """
        try:
            job = await self.job_repo.get_by_id(job_id)
            if not job:
                return []

            # Get all tasks for this job
            tasks = await self.task_repo.get_tasks_by_job(job.job_id)

            return [task.model_dump() for task in tasks]

        except Exception as e:
            logger.error(f"Error getting tasks for job {job_id}: {e}")
            return []

    async def get_job_tools(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get all tools generated by a job.

        Args:
            job_id: Job ID (MongoDB _id)

        Returns:
            List[Dict]: List of tool data
        """
        try:
            # Get all tasks for this job
            tasks = await self.get_job_tasks(job_id)

            # Extract tool IDs from tasks
            tool_ids = [
                task["tool_id"]
                for task in tasks
                if task.get("tool_id")
            ]

            if not tool_ids:
                return []

            # Get tools by IDs
            tools = await self.tool_repo.get_by_ids(tool_ids)

            return [tool.model_dump() for tool in tools]

        except Exception as e:
            logger.error(f"Error getting tools for job {job_id}: {e}")
            return []

    async def get_job_failures(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get all tool failures for a job.

        Args:
            job_id: Job ID (MongoDB _id)

        Returns:
            List[Dict]: List of failure data
        """
        try:
            # Get all tasks for this job
            tasks = await self.get_job_tasks(job_id)

            # Extract failure IDs from tasks
            failure_ids = [
                task["tool_failure_id"]
                for task in tasks
                if task.get("tool_failure_id")
            ]

            if not failure_ids:
                return []

            # Get failures by IDs
            failures = await self.tool_failure_repo.get_by_ids(failure_ids)

            return [failure.model_dump() for failure in failures]

        except Exception as e:
            logger.error(f"Error getting failures for job {job_id}: {e}")
            return []
