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
        session_id: str
    ) -> str:
        """
        Create a tool failure record from a ToolGenerationFailure.

        Args:
            failure: ToolGenerationFailure object from agent
            session_id: Session ID that attempted generation

        Returns:
            str: Created failure record ID
        """
        try:
            # Extract error type from error message if possible

            failure_data = {
                "session_id": session_id,
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

    async def get_by_session(self, session_id: str) -> List[ToolFailure]:
        """
        Get all tool failures for a specific session.

        Args:
            session_id: Session ID

        Returns:
            List[ToolFailure]: Tool failures from the session
        """
        return await self.find_by_field("session_id", session_id)

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

    async def get_failures_by_type(self, error_type: str, limit: Optional[int] = None) -> List[ToolFailure]:
        """
        Get tool failures by error type.

        Args:
            error_type: Error type category
            limit: Maximum number of failures to return

        Returns:
            List[ToolFailure]: Tool failures with specified error type
        """
        return await self.find_by_field("error_type", error_type, limit)

    async def get_failure_statistics(self) -> dict:
        """
        Get statistics about tool generation failures.

        Returns:
            dict: Failure statistics by type
        """
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": "$error_type",
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$sort": {"count": -1}
                }
            ]

            results = await self.collection.aggregate(pipeline).to_list(length=None)

            stats = {
                "total": sum(r["count"] for r in results),
                "by_type": {r["_id"]: r["count"] for r in results}
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get failure statistics: {e}")
            return {"total": 0, "by_type": {}}

    async def ensure_indexes(self):
        """Create indexes for optimal query performance."""
        try:
            # Index for session queries
            await self.collection.create_index("session_id")

            # Index for error type queries
            await self.collection.create_index("error_type")

            # Compound index for session + error type
            await self.collection.create_index([("session_id", 1), ("error_type", 1)])

            logger.info("Tool failure repository indexes created successfully")

        except Exception as e:
            logger.error(f"Failed to create tool failure repository indexes: {e}")
