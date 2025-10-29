"""
Tool failure repository for storing and retrieving failed tool generation attempts.
"""

from typing import List, Optional
from bson import ObjectId
import logging

from .base import BaseRepository
from app.models.tool_failure import ToolFailure
from app.models.tool_generation import ToolGenerationFailure
from app.models.job import UserToolRequirement

logger = logging.getLogger(__name__)


class ToolFailureRepository(BaseRepository[ToolFailure]):
    """Repository for tool generation failures."""

    def __init__(self):
        super().__init__(ToolFailure, "tool_failures")

    async def create_from_generation_failure(
        self,
        failure: ToolGenerationFailure,
        task_id: str
    ) -> str:
        """
        Create a tool failure record from a ToolGenerationFailure.

        Args:
            failure: ToolGenerationFailure object from agent
            task_id: Task ID that attempted generation

        Returns:
            str: Created failure record ID
        """
        try:
            # Extract error type from error message if possible

            failure_data = {
                "task_id": task_id,
                "user_requirement": failure.toolRequirement.model_dump() if hasattr(failure.toolRequirement, 'model_dump') else failure.toolRequirement,
                "error_message": failure.error,
                "error_type": failure.error_type,
            }

            failure_id = await self.create(failure_data)
            logger.info(f"Created tool failure record with ID {failure_id}")
            return failure_id

        except Exception as e:
            logger.error(f"Failed to create tool failure record: {e}")
            raise

    async def get_by_ids(self, failure_ids: List[str]) -> List[ToolFailure]:
        """
        Get multiple tool failures by their IDs.

        Args:
            failure_ids: List of failure IDs (as strings)

        Returns:
            List[ToolFailure]: List of tool failures
        """
        try:
            failures = []
            for failure_id in failure_ids:
                failure = await self.get_by_id(failure_id)
                if failure:
                    failures.append(failure)
            return failures
        except Exception as e:
            logger.error(f"Failed to get tool failures by IDs: {e}")
            return []

    async def ensure_indexes(self):
        """Create indexes for optimal query performance."""
        try:
            # Index for session queries
            await self.collection.create_index("task_id")

            # Index for error type queries
            await self.collection.create_index("error_type")

            # Compound index for session + error type
            await self.collection.create_index([("task_id", 1), ("error_type", 1)])

            logger.info("Tool failure repository indexes created successfully")

        except Exception as e:
            logger.error(f"Failed to create tool failure repository indexes: {e}")
