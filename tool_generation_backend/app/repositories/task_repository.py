"""
Task repository for single tool generation task management.
A Task represents one tool being generated within a Job.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import logging

from .base import BaseRepository
from app.models.task import (
    Task, TaskStatus
)

logger = logging.getLogger(__name__)


class TaskRepository(BaseRepository[Task]):
    """Repository for task data (single tool generation tasks)."""

    def __init__(self):
        super().__init__(Task, "tasks")

    async def create_task(self, task_data: Dict[str, Any]) -> str:
        """
        Create a new task from task data dict.

        Args:
            task_data: Task data dictionary

        Returns:
            str: Created task ID
        """
        return await self.create(task_data)

    async def update_status(self, task_id: str, status: TaskStatus, error_message: Optional[str] = None) -> bool:
        """
        Update task status and optionally error message.

        Args:
            task_id: Task ID
            status: New task status
            error_message: Error message if status is FAILED

        Returns:
            bool: True if updated successfully
        """
        update_data = {"status": status.value}

        if error_message:
            update_data["error_message"] = error_message
        elif status != TaskStatus.FAILED:
            # Clear error message if status is not failed
            update_data["error_message"] = None

        return await self.update(task_id, update_data)

    async def set_tool_id(self, task_id: str, tool_id: str) -> bool:
        """
        Set the tool_id field for a successful tool generation.

        Args:
            task_id: Task ID
            tool_id: Tool ID to set (stored as ObjectId in MongoDB)

        Returns:
            bool: True if set successfully
        """
        try:
            # Convert tool_id string to ObjectId for MongoDB storage
            tool_object_id = ObjectId(tool_id)

            # Use MongoDB set operation
            result = await self.collection.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"tool_id": tool_object_id, "updated_at": datetime.now(timezone.utc)}}
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Set tool ID for task {task_id}: {tool_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to set tool ID for task {task_id}: {e}")
            return False

    async def set_tool_failure_id(self, task_id: str, failure_id: str) -> bool:
        """
        Set the tool_failure_id field for a failed tool generation.

        Args:
            task_id: Task ID
            failure_id: Failure ID to set (stored as ObjectId in MongoDB)

        Returns:
            bool: True if set successfully
        """
        try:
            # Convert failure_id string to ObjectId for MongoDB storage
            failure_object_id = ObjectId(failure_id)

            # Use MongoDB set operation
            result = await self.collection.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"tool_failure_id": failure_object_id, "updated_at": datetime.now(timezone.utc)}}
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Set tool failure ID for task {task_id}: {failure_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to set tool failure ID for task {task_id}: {e}")
            return False

    async def get_tasks_by_job(self, job_id: str, limit: Optional[int] = None) -> List[Task]:
        """
        Get all tasks for a specific job.

        Args:
            job_id: Job identifier
            limit: Maximum number of tasks to return

        Returns:
            List[Task]: Tasks for the job ordered by creation date
        """
        return await self.find_by_field("job_id", job_id, limit)

    async def get_by_task_id(self, task_id: str) -> Optional[Task]:
        """
        Get task by task_id field (not MongoDB _id).

        Args:
            task_id: Task identifier

        Returns:
            Optional[Task]: Task if found, None otherwise
        """
        results = await self.find_by_field("task_id", task_id, limit=1)
        return results[0] if results else None



    async def get_tasks_by_user(self, user_id: str, limit: int = 50) -> List[Task]:
        """
        Get tasks for a specific user.

        Args:
            user_id: User identifier
            limit: Maximum number of tasks to return

        Returns:
            List[Task]: User's tasks ordered by creation date (newest first)
        """
        return await self.find_by_field("user_id", user_id, limit)

    async def get_tasks_by_status(self, status: TaskStatus, limit: Optional[int] = None) -> List[Task]:
        """
        Get tasks by status.

        Args:
            status: Task status to filter by
            limit: Maximum number of tasks to return

        Returns:
            List[Task]: Tasks with specified status
        """
        return await self.find_by_field("status", status.value, limit)

    async def get_active_tasks(self, limit: Optional[int] = None) -> List[Task]:
        """
        Get tasks that are currently active (not completed or failed).

        Args:
            limit: Maximum number of tasks to return

        Returns:
            List[Task]: Active tasks
        """
        active_statuses = [
            TaskStatus.PENDING.value,
            TaskStatus.PLANNING.value,
            TaskStatus.SEARCHING.value,
            TaskStatus.IMPLEMENTING.value,
            TaskStatus.EXECUTING.value
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

            # Index for job_id queries (find all tasks for a job)
            await self.collection.create_index("job_id")

            # Index for task_id queries (direct lookup) - UNIQUE
            await self.collection.create_index("task_id", unique=True)

            # Compound index for user + status queries
            await self.collection.create_index([("user_id", 1), ("status", 1)])

            # Index for created_at for sorting
            await self.collection.create_index("created_at")

            logger.info("Task repository indexes created successfully")

        except Exception as e:
            logger.error(f"Failed to create task repository indexes: {e}")

