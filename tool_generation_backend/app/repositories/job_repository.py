"""
Job repository for bulk tool generation workflow management.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import logging

from .base import BaseRepository
from app.models.job import Job, JobStatus

logger = logging.getLogger(__name__)


class JobRepository(BaseRepository[Job]):
    """Repository for job data and workflow management."""

    def __init__(self):
        super().__init__(Job, "jobs")

    async def create_job(self, job_data: Dict[str, Any]) -> str:
        """
        Create a new job from job data dict.

        Args:
            job_data: Job data dictionary

        Returns:
            str: Created job ID
        """
        return await self.create(job_data)

    async def get_by_job_id(self, job_id: str) -> Optional[Job]:
        """
        Get job by job_id field (not MongoDB _id).

        Args:
            job_id: Job identifier (e.g., job_abc123)

        Returns:
            Optional[Job]: Job if found, None otherwise
        """
        results = await self.find_by_field("job_id", job_id, limit=1)
        return results[0] if results else None

    async def update_status(self, job_id: str, status: JobStatus, error_message: Optional[str] = None) -> bool:
        """
        Update job status and optionally error message.

        Args:
            job_id: MongoDB _id of the job
            status: New job status
            error_message: Error message if status is FAILED

        Returns:
            bool: True if updated successfully
        """
        update_data = {"status": status.value}

        if error_message:
            update_data["error_message"] = error_message
        elif status != JobStatus.FAILED:
            # Clear error message if status is not failed
            update_data["error_message"] = None

        return await self.update(job_id, update_data)

    async def add_task_id(self, job_id: str, task_id: str) -> bool:
        """
        Add a task ID to job's task_ids list.

        Args:
            job_id: MongoDB _id of the job
            task_id: Task ID to add

        Returns:
            bool: True if added successfully
        """
        try:
            # Use MongoDB array push operation
            result = await self.collection.update_one(
                {"_id": ObjectId(job_id)},
                {"$push": {"task_ids": task_id}}
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Added task ID to job {job_id}: {task_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to add task ID to job {job_id}: {e}")
            return False

    async def increment_completed(self, job_id: str) -> bool:
        """
        Atomically increment the tools_completed counter.

        Args:
            job_id: MongoDB _id of the job

        Returns:
            bool: True if incremented successfully
        """
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(job_id)},
                {
                    "$inc": {"tools_completed": 1},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Incremented tools_completed for job {job_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to increment tools_completed for job {job_id}: {e}")
            return False

    async def increment_failed(self, job_id: str) -> bool:
        """
        Atomically increment the tools_failed counter.

        Args:
            job_id: MongoDB _id of the job

        Returns:
            bool: True if incremented successfully
        """
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(job_id)},
                {
                    "$inc": {"tools_failed": 1},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Incremented tools_failed for job {job_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to increment tools_failed for job {job_id}: {e}")
            return False

    async def increment_in_progress(self, job_id: str) -> bool:
        """
        Atomically increment the tools_in_progress counter.

        Args:
            job_id: MongoDB _id of the job

        Returns:
            bool: True if incremented successfully
        """
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(job_id)},
                {
                    "$inc": {"tools_in_progress": 1},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Incremented tools_in_progress for job {job_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to increment tools_in_progress for job {job_id}: {e}")
            return False

    async def decrement_in_progress(self, job_id: str) -> bool:
        """
        Atomically decrement the tools_in_progress counter.

        Args:
            job_id: MongoDB _id of the job

        Returns:
            bool: True if decremented successfully
        """
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(job_id)},
                {
                    "$inc": {"tools_in_progress": -1},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Decremented tools_in_progress for job {job_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to decrement tools_in_progress for job {job_id}: {e}")
            return False

    async def get_jobs_by_user(self, user_id: str, limit: int = 50) -> List[Job]:
        """
        Get jobs for a specific user.

        Args:
            user_id: User identifier
            limit: Maximum number of jobs to return

        Returns:
            List[Job]: User's jobs ordered by creation date (newest first)
        """
        return await self.find_by_field("user_id", user_id, limit)

    async def get_jobs_by_status(self, status: JobStatus, limit: Optional[int] = None) -> List[Job]:
        """
        Get jobs by status.

        Args:
            status: Job status to filter by
            limit: Maximum number of jobs to return

        Returns:
            List[Job]: Jobs with specified status
        """
        return await self.find_by_field("status", status.value, limit)

    async def get_active_jobs(self, limit: Optional[int] = None) -> List[Job]:
        """
        Get jobs that are currently active (not completed or failed).

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List[Job]: Active jobs
        """
        active_statuses = [
            JobStatus.PENDING.value,
            JobStatus.PROCESSING.value
        ]

        return await self.find_many(
            {"status": {"$in": active_statuses}},
            limit=limit,
            sort_by="created_at"
        )

    async def ensure_indexes(self):
        """Create indexes for optimal query performance."""
        try:
            # Index for user queries
            await self.collection.create_index("user_id")

            # Index for status queries
            await self.collection.create_index("status")

            # Index for job_id queries (direct lookup) - UNIQUE
            await self.collection.create_index("job_id", unique=True)

            # Compound index for user + status queries
            await self.collection.create_index([("user_id", 1), ("status", 1)])

            # Index for created_at for sorting
            await self.collection.create_index("created_at")

            logger.info("Job repository indexes created successfully")

        except Exception as e:
            logger.error(f"Failed to create job repository indexes: {e}")
