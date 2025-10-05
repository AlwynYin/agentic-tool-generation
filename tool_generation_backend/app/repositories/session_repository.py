"""
Session repository for workflow data management.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import logging

from .base import BaseRepository
from app.models.session import (
    Session, SessionStatus, ToolSpec, ImplementationPlan, SearchPlan, ApiSpec
)

logger = logging.getLogger(__name__)


class SessionRepository(BaseRepository[Session]):
    """Repository for session data and workflow management."""

    def __init__(self):
        super().__init__(Session, "sessions")

    async def create_session(self, session_data: Dict[str, Any]) -> str:
        """
        Create a new session from session data dict.

        Args:
            session_data: Session data dictionary

        Returns:
            str: Created session ID
        """
        return await self.create(session_data)

    async def update_status(self, session_id: str, status: SessionStatus, error_message: Optional[str] = None) -> bool:
        """
        Update session status and optionally error message.

        Args:
            session_id: Session ID
            status: New session status
            error_message: Error message if status is FAILED

        Returns:
            bool: True if updated successfully
        """
        update_data = {"status": status}

        if error_message:
            update_data["error_message"] = error_message
        elif status != SessionStatus.FAILED:
            # Clear error message if status is not failed
            update_data["error_message"] = None

        return await self.update(session_id, update_data)

    # async def store_implementation_plan(self, session_id: str, plan: ImplementationPlan) -> bool:
    #     """
    #     Store implementation plan from orchestrator agent.
    #
    #     Args:
    #         session_id: Session ID
    #         plan: Implementation plan data
    #
    #     Returns:
    #         bool: True if stored successfully
    #     """
    #     plan_dict = plan.model_dump()
    #     return await self.update(session_id, {"implementation_plan": plan_dict})
    #
    # async def store_search_plan(self, session_id: str, plan: SearchPlan) -> bool:
    #     """
    #     Store search plan for browser agent.
    #
    #     Args:
    #         session_id: Session ID
    #         plan: Search plan data
    #
    #     Returns:
    #         bool: True if stored successfully
    #     """
    #     plan_dict = plan.model_dump()
    #     return await self.update(session_id, {"search_plan": plan_dict})
    #
    # async def add_api_spec(self, session_id: str, api_spec: ApiSpec) -> bool:
    #     """
    #     Add an API specification to session.
    #
    #     Args:
    #         session_id: Session ID
    #         api_spec: API specification data
    #
    #     Returns:
    #         bool: True if added successfully
    #     """
    #     try:
    #         api_spec_dict = api_spec.model_dump()
    #
    #         # Use MongoDB array push operation
    #         result = await self.collection.update_one(
    #             {"_id": ObjectId(session_id)},
    #             {"$push": {"api_specs": api_spec_dict}}
    #         )
    #
    #         success = result.modified_count > 0
    #         if success:
    #             logger.info(f"Added API spec to session {session_id}: {api_spec.function_name}")
    #
    #         return success
    #
    #     except Exception as e:
    #         logger.error(f"Failed to add API spec to session {session_id}: {e}")
    #         return False
    #
    # async def store_api_specs(self, session_id: str, api_specs: List[ApiSpec]) -> bool:
    #     """
    #     Store multiple API specifications from browser agent.
    #
    #     Args:
    #         session_id: Session ID
    #         api_specs: List of API specifications
    #
    #     Returns:
    #         bool: True if stored successfully
    #     """
    #     api_specs_dicts = [spec.model_dump() for spec in api_specs]
    #     return await self.update(session_id, {"api_specs": api_specs_dicts})

    async def add_generated_tool(self, session_id: str, tool: ToolSpec) -> bool:
        """
        Add a generated tool to session's generated_tools list.

        Args:
            session_id: Session ID
            tool: Tool specification

        Returns:
            bool: True if added successfully
        """
        try:
            tool_dict = tool.model_dump()

            # Use MongoDB array push operation
            result = await self.collection.update_one(
                {"_id": ObjectId(session_id)},
                {"$push": {"generated_tools": tool_dict}}
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Added generated tool to session {session_id}: {tool.name}")

            return success

        except Exception as e:
            logger.error(f"Failed to add generated tool to session {session_id}: {e}")
            return False

    async def store_tools(self, session_id: str, tools: List[ToolSpec]) -> bool:
        """
        Store multiple generated tools from implementer agent.

        Args:
            session_id: Session ID
            tools: List of tool specifications

        Returns:
            bool: True if stored successfully
        """
        tools_dicts = [tool.model_dump() for tool in tools]
        return await self.update(session_id, {"tools": tools_dicts})

    async def update_tool_registration(self, session_id: str, tool_name: str, endpoint: str) -> bool:
        """
        Update tool registration status and endpoint.

        Args:
            session_id: Session ID
            tool_name: Name of the tool that was registered
            endpoint: SimpleTooling endpoint URL

        Returns:
            bool: True if updated successfully
        """
        try:
            # Update tool in the tools array
            result = await self.collection.update_one(
                {
                    "_id": ObjectId(session_id),
                    "tools.name": tool_name
                },
                {
                    "$set": {
                        "tools.$.registered": True,
                        "tools.$.endpoint": endpoint,
                        "tools.$.status": "registered"
                    }
                }
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Updated tool registration for session {session_id}, tool {tool_name}")

            return success

        except Exception as e:
            logger.error(f"Failed to update tool registration for session {session_id}, tool {tool_name}: {e}")
            return False

    async def get_sessions_by_user(self, user_id: str, limit: int = 50) -> List[Session]:
        """
        Get sessions for a specific user.

        Args:
            user_id: User identifier
            limit: Maximum number of sessions to return

        Returns:
            List[Session]: User's sessions ordered by creation date (newest first)
        """
        return await self.find_by_field("user_id", user_id, limit)

    async def get_sessions_by_status(self, status: SessionStatus, limit: Optional[int] = None) -> List[Session]:
        """
        Get sessions by status.

        Args:
            status: Session status to filter by
            limit: Maximum number of sessions to return

        Returns:
            List[Session]: Sessions with specified status
        """
        return await self.find_by_field("status", status.value, limit)

    async def get_active_sessions(self, limit: Optional[int] = None) -> List[Session]:
        """
        Get sessions that are currently active (not completed or failed).

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List[Session]: Active sessions
        """
        active_statuses = [
            SessionStatus.PENDING.value,
            SessionStatus.PLANNING.value,
            SessionStatus.SEARCHING.value,
            SessionStatus.IMPLEMENTING.value,
            SessionStatus.EXECUTING.value
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

            # Index for job_id queries (direct lookup)
            await self.collection.create_index("job_id")

            # Compound index for user + status queries
            await self.collection.create_index([("user_id", 1), ("status", 1)])

            # Index for created_at for sorting
            await self.collection.create_index("created_at")

            logger.info("Session repository indexes created successfully")

        except Exception as e:
            logger.error(f"Failed to create session repository indexes: {e}")

