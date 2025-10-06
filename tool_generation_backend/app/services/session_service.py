"""
Session service for workflow orchestration and management.
"""

import asyncio
import logging
import os

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from app.models.session import (
    SessionUpdate, SessionStatus, Session, ToolGenerationResult
)
from app.models.tool import Tool
from app.models.job import UserToolRequirement
from app.models.operation import OperationContext
from app.repositories.session_repository import SessionRepository
from app.repositories.tool_repository import ToolRepository
from app.agents.pipeline import ToolGenerationPipeline
from app.config import get_settings

logger = logging.getLogger(__name__)


class SessionService:
    """Service for managing session workflows and orchestration."""

    def __init__(
        self,
        session_repo: SessionRepository,
        tool_repo: ToolRepository,
        websocket_manager: Optional[Any] = None
    ):
        """
        Initialize session service.

        Args:
            session_repo: Session repository
            tool_repo: Tool repository for deduplication
            websocket_manager: WebSocket manager for real-time updates
        """
        self.session_repo = session_repo
        self.tool_repo = tool_repo

        # Initialize Chemistry Tool Pipeline
        self.pipeline = ToolGenerationPipeline()

        self.websocket_manager = websocket_manager
        self.active_workflows: Dict[str, asyncio.Task] = {}
        self.settings = get_settings()

    async def create_session(self, job_id: str, user_id: str, tool_requirements: list[UserToolRequirement], operation_type: str = "generate", base_job_id: Optional[str] = None) -> str:
        """
        Create new session and start processing workflow.

        Args:
            job_id: Associated job ID
            user_id: User identifier
            tool_requirements: List of tool requirements
            operation_type: "generate" or "update"
            base_job_id: Base job ID for update operations

        Returns:
            str: Created session ID
        """
        try:
            # Create session data
            session_data = {
                "job_id": job_id,
                "user_id": user_id,
                "operation_type": operation_type,
                "tool_requirements": [req.model_dump() for req in tool_requirements] if operation_type == "generate" else [],
                "update_requirements": [req.model_dump() for req in tool_requirements] if operation_type == "update" else [],
                "base_job_id": base_job_id,
                "status": SessionStatus.PENDING
            }

            # Create session in database
            session_id = await self.session_repo.create_session(session_data)

            logger.info(f"Created session {session_id} for job {job_id} user {user_id}")

            # Start async workflow processing
            workflow_task = asyncio.create_task(
                self._process_workflow(session_id)
            )
            self.active_workflows[session_id] = workflow_task

            return session_id

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise

    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Optional[Session]: Session or None if not found
        """
        return await self.session_repo.get_by_id(session_id)

    async def get_session_by_job_id(self, job_id: str) -> Optional[Session]:
        """
        Get session by job ID.

        Args:
            job_id: Job ID to search for

        Returns:
            Optional[Session]: Session or None if not found
        """
        try:
            sessions = await self.session_repo.find_many({
                "job_id": job_id
            }, limit=1)
            return sessions[0] if sessions else None
        except Exception as e:
            logger.error(f"Error finding session by job ID {job_id}: {e}")
            return None

    async def update_session(self, session_id: str, update_data: SessionUpdate) -> bool:
        """
        Update session data.

        Args:
            session_id: Session ID
            update_data: Update data

        Returns:
            bool: True if updated successfully
        """
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        return await self.session_repo.update(session_id, update_dict)

    async def get_user_sessions(self, user_id: str, limit: int = 50) -> list[Session]:
        """
        Get sessions for a user.

        Args:
            user_id: User ID
            limit: Maximum number of sessions

        Returns:
            list[Session]: User's sessions
        """
        return await self.session_repo.get_sessions_by_user(user_id, limit)

    async def get_session_tools(self, session_id: str) -> List[Tool]:
        """
        Get tools for a session from the tools collection.

        Args:
            session_id: Session ID

        Returns:
            List[Tool]: Tools associated with the session
        """
        try:
            session = await self.session_repo.get_by_id(session_id)
            if not session:
                logger.warning(f"Session not found: {session_id}")
                return []

            # Get tools from tools collection using tool_ids
            if session.tool_ids:
                tools = await self.tool_repo.get_by_ids(session.tool_ids)
                return tools
            else:
                logger.info(f"No tool_ids for session {session_id}")
                return []

        except Exception as e:
            logger.error(f"Error getting tools for session {session_id}: {e}")
            return []

    async def get_active_sessions(self, limit: Optional[int] = None) -> list[Session]:
        """
        Get active sessions.

        Args:
            limit: Maximum number of sessions

        Returns:
            list[Session]: Active sessions
        """
        return await self.session_repo.get_active_sessions(limit)

    async def cancel_session(self, session_id: str, reason: str = "User cancelled") -> bool:
        """
        Cancel an active session.

        Args:
            session_id: Session ID
            reason: Cancellation reason

        Returns:
            bool: True if cancelled successfully
        """
        try:
            # Cancel workflow task if running
            if session_id in self.active_workflows:
                workflow_task = self.active_workflows[session_id]
                workflow_task.cancel()
                del self.active_workflows[session_id]

            # Update session status
            success = await self.session_repo.update_status(
                session_id, SessionStatus.FAILED, f"Cancelled: {reason}"
            )

            if success:
                await self._notify_session_update(session_id, {
                    "type": "session-cancelled",
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            return success

        except Exception as e:
            logger.error(f"Failed to cancel session {session_id}: {e}")
            return False

    async def _process_workflow(self, session_id: str):
        """
        Execute agent workflow for all tool generation requests.

        Args:
            session_id: Session ID
        """
        try:
            logger.info(f"Starting agent workflow for session {session_id}")

            # Get session data
            session = await self.session_repo.get_by_id(session_id)
            if not session:
                raise ValueError(f"Session not found: {session_id}")

            # Create operation context and process through pipeline
            operation_context = self._create_operation_context(session)
            generation_results = await self.pipeline.process_operation(operation_context)

            # Store the generated tool requirements in the session
            if generation_results:
                await self._store_tool_specs(session_id, generation_results)

            # Mark session as completed
            await self._update_session_status(session_id, SessionStatus.COMPLETED)
            logger.info(f"Agent workflow completed for session {session_id}")

        except asyncio.CancelledError:
            logger.info(f"Workflow cancelled for session {session_id}")
            await self._update_session_status(session_id, SessionStatus.FAILED, "Workflow cancelled")

        except Exception as e:
            error_msg = f"Workflow failed: {str(e)}"
            logger.error(f"Workflow failed for session {session_id}: {e}")
            await self._update_session_status(session_id, SessionStatus.FAILED, error_msg)

            # Notify via WebSocket that workflow failed
            await self._notify_session_update(session_id, {
                "type": "workflow-failed",
                "session_id": session_id,
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        finally:
            # Clean up workflow tracking
            if session_id in self.active_workflows:
                del self.active_workflows[session_id]

    def _create_operation_context(self, session: Session) -> OperationContext:
        """
        Create operation context from session data.

        Args:
            session: Session with tool requirements

        Returns:
            OperationContext: Context for pipeline processing
        """
        if session.operation_type == "generate":
            # Convert dict requirements to UserToolRequirement objects
            tools = []
            for req in session.tool_requirements:
                if isinstance(req, dict):
                    tools.append(UserToolRequirement(**req))
                else:
                    tools.append(req)

            return OperationContext.create_implement_operation(
                session_id=session.id,
                tools=tools,
                metadata={"job_id": session.job_id}
            )

        elif session.operation_type == "update":
            # Convert dict requirements to UserToolRequirement objects
            raise NotImplementedError()
        else:
            raise ValueError(f"Unsupported operation type: {session.operation_type}")

    async def _store_tool_specs(self, session_id: str, tool_generation_results: List[ToolGenerationResult]) -> None:
        """
        Store generated tools in tools collection with deduplication.

        Args:
            session_id: Session ID
            tool_generation_results: List of ToolGenerationResult objects
        """
        try:
            tools_processed = []
            tool_ids = []

            for tool_res in tool_generation_results:
                # Read generated code from file
                file_path = os.path.join(self.settings.tools_path, tool_res.file_name)
                with open(file_path, "r") as file:
                    tool_code = file.read()

                # Check if tool already exists (deduplication)
                existing_tool = await self.tool_repo.get_by_name(tool_res.name)

                if existing_tool:
                    # Tool exists - update session_id to current session
                    logger.info(f"Tool {tool_res.name} already exists (ID: {existing_tool.id}), updating session_id")
                    await self.tool_repo.update(existing_tool.id, {"session_id": session_id})
                    tool_id = existing_tool.id
                else:
                    # Create new tool in tools collection
                    logger.info(f"Creating new tool {tool_res.name}")
                    tool_id = await self.tool_repo.create_from_generation_result(
                        result=tool_res,
                        session_id=session_id,
                        file_path=file_path,
                        code=tool_code
                    )

                # Add tool ID to session
                await self.session_repo.add_tool_id(session_id, tool_id)
                tool_ids.append(tool_id)
                tools_processed.append(tool_res.name)

            logger.info(f"Stored {len(tool_generation_results)} tools for session {session_id}")

        except Exception as e:
            logger.error(f"Error storing tool specs for session {session_id}: {e}")
            raise

        if tools_processed:
            logger.info(f"Processed {len(tools_processed)} tools for session {session_id}: {tools_processed}")
            await self._notify_session_update(session_id, {
                "type": "tools-generated",
                "session_id": session_id,
                "tool_names": tools_processed,
                "tool_count": len(tools_processed)
            })

    async def _update_session_status(self, session_id: str, status: SessionStatus, error_message: Optional[str] = None):
        """Update session status and notify via WebSocket."""
        await self.session_repo.update_status(session_id, status, error_message)

        await self._notify_session_update(session_id, {
            "type": "status-update",
            "status": status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error_message
        })

    async def _notify_session_update(self, session_id: str, message: Dict[str, Any]):
        """Send WebSocket notification for session update."""
        if self.websocket_manager:
            try:
                await self.websocket_manager.send_to_session(session_id, message)
            except Exception as e:
                logger.error(f"Failed to send WebSocket notification: {e}")

    async def _notify_agent_progress(self, session_id: str, progress: Dict[str, Any]):
        """Notify OpenAI agent progress via WebSocket."""
        await self._notify_session_update(session_id, {
            "type": "agent-progress",
            "agent": "openai_agent",
            "session_id": session_id,
            **progress
        })

    async def cleanup_completed_workflows(self):
        """Clean up completed workflow tasks."""
        completed_sessions = []

        for session_id, task in self.active_workflows.items():
            if task.done():
                completed_sessions.append(session_id)

        for session_id in completed_sessions:
            del self.active_workflows[session_id]

        if completed_sessions:
            logger.info(f"Cleaned up {len(completed_sessions)} completed workflows")

    def get_workflow_status(self, session_id: str) -> Optional[str]:
        """
        Get workflow status for a session.

        Args:
            session_id: Session ID

        Returns:
            Optional[str]: Workflow status or None if not found
        """
        if session_id not in self.active_workflows:
            return None

        task = self.active_workflows[session_id]

        if task.done():
            if task.cancelled():
                return "cancelled"
            elif task.exception():
                return "failed"
            else:
                return "completed"
        else:
            return "running"