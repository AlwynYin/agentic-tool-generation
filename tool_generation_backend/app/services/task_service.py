"""
Task service for single tool generation workflow management.
A Task represents generating ONE tool within a Job.
"""

import asyncio
import logging
import os
import uuid

from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timezone

from app.models.task import (
    TaskUpdate, TaskStatus, Task
)
from app.models.tool_generation import ToolGenerationResult, ToolGenerationFailure
from app.models.tool import Tool
from app.models.specs import UserToolRequirement
from app.repositories.task_repository import TaskRepository
from app.repositories.tool_repository import ToolRepository
from app.repositories.tool_failure_repository import ToolFailureRepository
from app.agents.pipeline_v2 import ToolGenerationPipelineV2
from app.config import get_settings

logger = logging.getLogger(__name__)


class TaskService:
    """Service for managing task workflows and orchestration."""

    # Class-level semaphore to limit concurrent tool generation
    # Shared across all TaskService instances
    # Initialized on first use to use settings value
    _concurrency_semaphore = None

    def __init__(
        self,
        task_repo: TaskRepository,
        tool_repo: ToolRepository,
        tool_failure_repo: Optional[ToolFailureRepository] = None,
        websocket_manager: Optional[Any] = None,
        job_service: Optional[Any] = None  # Using Any to avoid circular import at type hint level
    ):
        """
        Initialize task service.

        Args:
            task_repo: Task repository
            tool_repo: Tool repository for deduplication
            tool_failure_repo: Tool failure repository for storing failures
            websocket_manager: WebSocket manager for real-time updates
            job_service: Optional JobService instance (lazy-loaded if not provided)
        """
        self.task_repo = task_repo
        self.tool_repo = tool_repo
        self.tool_failure_repo = tool_failure_repo or ToolFailureRepository()
        self._job_service = job_service
        self._websocket_manager = websocket_manager

        # Initialize settings
        self.settings = get_settings()

        # Initialize class-level semaphore on first instance creation
        if TaskService._concurrency_semaphore is None:
            TaskService._concurrency_semaphore = asyncio.Semaphore(self.settings.max_concurrent_tools)
            logger.info(f"Initialized concurrency semaphore with limit: {self.settings.max_concurrent_tools}")

        self.pipeline = ToolGenerationPipelineV2()

        self.active_workflows: Dict[str, asyncio.Task] = {}

    @property
    def job_service(self) -> Any:
        """Lazy-load JobService if not provided in constructor."""
        if self._job_service is None:
            # Import here to avoid circular imports at module level
            from app.dependencies import get_job_service
            self._job_service = get_job_service()
        return self._job_service

    @property
    def websocket_manager(self) -> Optional[Any]:
        """Lazy-load WebSocket manager if not provided in constructor."""
        if self._websocket_manager is None:
            # Import here to avoid circular imports at module level
            from app.dependencies import get_websocket_manager_direct
            self._websocket_manager = get_websocket_manager_direct()
        return self._websocket_manager

    async def create_task(
        self,
        job_id: str,  # MongoDB _id of the Job
        job_id_short: str,  # Short job identifier (e.g., job_abc123)
        user_id: str,
        requirement: UserToolRequirement  # SINGLE requirement, not a list!
    ) -> str:
        """
        Create new task for SINGLE tool generation and start processing workflow.

        Args:
            job_id: Job MongoDB _id
            job_id_short: Short job identifier (e.g., job_abc123)
            user_id: User identifier
            requirement: Single tool requirement (not a list!)

        Returns:
            str: Created task ID (MongoDB _id)
        """
        try:
            # Generate unique task_id
            task_id_str = f"task_{uuid.uuid4().hex[:12]}"

            # Create task data
            task_data = {
                "task_id": task_id_str,
                "job_id": job_id_short,  # Store the short job_id for lookups
                "user_id": user_id,
                "tool_requirement": requirement.model_dump(),  # Single requirement
                "status": TaskStatus.PENDING.value,
                "tool_id": None,
                "tool_failure_id": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            # Create task in database
            task_db_id = await self.task_repo.create_task(task_data)

            logger.info(f"Created task {task_id_str} (DB ID: {task_db_id}) for job {job_id_short}")

            # Notify job that task started
            await self.job_service.increment_in_progress(job_id)

            # Start async workflow processing
            workflow_task = asyncio.create_task(
                self._process_workflow(task_db_id, job_id)
            )
            self.active_workflows[task_db_id] = workflow_task

            return task_db_id

        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            raise

    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            Optional[Task]: Task or None if not found
        """
        return await self.task_repo.get_by_id(task_id)

    async def get_task_by_job_id(self, job_id: str) -> Optional[Task]:
        """
        Get task by job ID.

        Args:
            job_id: Job ID to search for

        Returns:
            Optional[Task]: Task or None if not found
        """
        try:
            tasks = await self.task_repo.find_many({
                "job_id": job_id
            }, limit=1)
            return tasks[0] if tasks else None
        except Exception as e:
            logger.error(f"Error finding task by job ID {job_id}: {e}")
            return None

    async def update_task(self, task_id: str, update_data: TaskUpdate) -> bool:
        """
        Update task data.

        Args:
            task_id: Task ID
            update_data: Update data

        Returns:
            bool: True if updated successfully
        """
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        return await self.task_repo.update(task_id, update_dict)

    async def get_user_tasks(self, user_id: str, limit: int = 50) -> list[Task]:
        """
        Get tasks for a user.

        Args:
            user_id: User ID
            limit: Maximum number of tasks

        Returns:
            list[Task]: User's tasks
        """
        return await self.task_repo.get_tasks_by_user(user_id, limit)

    async def get_task_tool(self, task_id: str) -> Optional[Tool]:
        """
        Get tool for a task from the tools collection.

        Args:
            task_id: Task ID

        Returns:
            Optional[Tool]: Tool associated with the task, if any
        """
        try:
            task = await self.task_repo.get_by_id(task_id)
            if not task:
                logger.warning(f"Task not found: {task_id}")
                return None

            # Get tool from tools collection using tool_id (singular)
            if task.tool_id:
                tool = await self.tool_repo.get_by_id(task.tool_id)
                return tool
            else:
                logger.info(f"No tool_id for task {task_id}")
                return None

        except Exception as e:
            logger.error(f"Error getting tool for task {task_id}: {e}")
            return None

    async def get_task_failure(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tool generation failure for a task from the tool_failures collection.

        Args:
            task_id: Task ID

        Returns:
            Optional[ToolFailure]: Tool failure associated with the task, if any
        """
        try:
            task = await self.task_repo.get_by_id(task_id)
            if not task:
                logger.warning(f"Task not found: {task_id}")
                return None

            # Get failure from tool_failures collection using tool_failure_id (singular)
            if task.tool_failure_id:
                failure = await self.tool_failure_repo.get_by_id(task.tool_failure_id)
                return failure
            else:
                logger.info(f"No tool_failure_id for task {task_id}")
                return None

        except Exception as e:
            logger.error(f"Error getting failure for task {task_id}: {e}")
            return None

    async def get_active_tasks(self, limit: Optional[int] = None) -> list[Task]:
        """
        Get active tasks.

        Args:
            limit: Maximum number of tasks

        Returns:
            list[Task]: Active tasks
        """
        return await self.task_repo.get_active_tasks(limit)

    async def cancel_task(self, task_id: str, reason: str = "User cancelled") -> bool:
        """
        Cancel an active task.

        Args:
            task_id: Task ID
            reason: Cancellation reason

        Returns:
            bool: True if cancelled successfully
        """
        try:
            # Cancel workflow task if running
            if task_id in self.active_workflows:
                workflow_task = self.active_workflows[task_id]
                workflow_task.cancel()
                del self.active_workflows[task_id]

            # Update task status
            success = await self.task_repo.update_status(
                task_id, TaskStatus.FAILED, f"Cancelled: {reason}"
            )

            if success:
                await self._notify_task_update(task_id, {
                    "type": "task-cancelled",
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            return success

        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return False

    async def _process_workflow(self, task_id: str, job_id: str):
        """
        Execute agent workflow for SINGLE tool generation.

        Limited to 6 concurrent executions via class-level semaphore.

        Args:
            task_id: Task ID (MongoDB _id)
            job_id: Job ID (MongoDB _id)
        """
        # Acquire semaphore to limit concurrency
        async with self._concurrency_semaphore:
            max_concurrent = self.settings.max_concurrent_tools
            currently_running = max_concurrent - self._concurrency_semaphore._value
            logger.info(f"Starting tool generation for task {task_id} ({currently_running}/{max_concurrent} slots in use)")

            try:
                logger.info(f"Starting single tool generation workflow for task {task_id}")

                # Get task data
                task = await self.task_repo.get_by_id(task_id)
                if not task:
                    raise ValueError(f"Task not found: {task_id}")

                output = await self.pipeline.process_tool_generation(
                    task_id=task.task_id,
                    requirement=task.tool_requirement,
                    job_id=task.job_id  # Short job_id like "job_abc123"
                )

                # Handle result based on success/failure
                if output.success:
                    # Success: store tool and mark task as COMPLETED
                    logger.info(f"Tool generation succeeded for task {task_id}")
                    await self._store_tool_spec(task_id, job_id, output.result)
                    await self._update_task_status(task_id, TaskStatus.COMPLETED)
                    logger.info(f"Agent workflow completed successfully for task {task_id}")
                else:
                    # Failure: store failure and mark task as FAILED
                    logger.warning(f"Tool generation failed for task {task_id}: {output.failure.error}")
                    await self._store_generation_failure(task_id, job_id, output.failure)
                    await self._update_task_status(task_id, TaskStatus.FAILED)
                    logger.info(f"Agent workflow completed with failure for task {task_id}")

            except asyncio.CancelledError:
                logger.info(f"Workflow cancelled for task {task_id}")
                await self._update_task_status(task_id, TaskStatus.FAILED, "Workflow cancelled")
                # Notify job that tool failed
                await self.job_service.decrement_in_progress(job_id)
                await self.job_service.increment_failed(job_id)

            except Exception as e:
                error_msg = f"Workflow failed: {str(e)}"
                logger.error(f"Workflow failed for task {task_id}: {e}")
                await self._update_task_status(task_id, TaskStatus.FAILED, error_msg)

                # Notify via WebSocket that workflow failed
                await self._notify_task_update(task_id, {
                    "type": "workflow-failed",
                    "task_id": task_id,
                    "error": error_msg,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                # Notify job that tool failed
                await self.job_service.decrement_in_progress(job_id)
                await self.job_service.increment_failed(job_id)

            finally:
                # Clean up workflow tracking
                if task_id in self.active_workflows:
                    del self.active_workflows[task_id]

    async def _store_tool_spec(self, task_id: str, job_id: str, tool_result: ToolGenerationResult) -> None:
        """
        Store generated tool in tools collection with deduplication.

        Args:
            task_id: Task ID (MongoDB _id)
            job_id: Job ID (MongoDB _id)
            tool_result: Single ToolGenerationResult object
        """
        try:
            # Get task to retrieve job_id_short
            task = await self.task_repo.get_by_id(task_id)
            if not task:
                raise ValueError(f"Task not found: {task_id}")

            file_path = os.path.join(self.settings.tools_path, task.job_id, task.task_id, tool_result.file_name)

            # Read all files (code, test, plan, search results)
            additional_files = self._read_task_files(task, tool_result.name)

            # Check if tool already exists (deduplication)
            existing_tool = await self.tool_repo.get_by_name(tool_result.name)

            if existing_tool:
                # Tool exists - update task_id and file contents
                logger.info(f"Tool {tool_result.name} already exists (ID: {existing_tool.id}), updating task_id and files")
                update_data = {
                    "task_id": task_id,
                    **additional_files  # Update all file contents
                }
                await self.tool_repo.update(existing_tool.id, update_data)
                tool_id = existing_tool.id
            else:
                # Create new tool in tools collection
                logger.info(f"Creating new tool {tool_result.name}")
                tool_id = await self.tool_repo.create_from_generation_result(
                    result=tool_result,
                    task_id=task_id,
                    file_path=file_path,
                    **additional_files  # Pass all file contents
                )

            # Set tool ID in task (singular field, not array)
            await self.task_repo.set_tool_id(task_id, tool_id)

            logger.info(f"Stored tool {tool_result.name} for task {task_id}")

            # Notify via WebSocket
            await self._notify_task_update(task_id, {
                "type": "tool-generated",
                "task_id": task_id,
                "tool_name": tool_result.name
            })

            # Notify job that tool completed
            await self.job_service.decrement_in_progress(job_id)
            await self.job_service.increment_completed(job_id)

        except Exception as e:
            logger.error(f"Error storing tool spec for task {task_id}: {e}")
            raise

    async def _store_generation_failure(self, task_id: str, job_id: str, failure: ToolGenerationFailure) -> None:
        """
        Store tool generation failure in tool_failures collection.

        Args:
            task_id: Task ID (MongoDB _id)
            job_id: Job ID (MongoDB _id)
            failure: Single ToolGenerationFailure object
        """
        try:
            # Get task to retrieve job_id_short and read partial files
            task = await self.task_repo.get_by_id(task_id)
            if task:
                # Try to read partial files (using generic tool name from requirement)
                tool_name = failure.toolRequirement.description.split()[0] if failure.toolRequirement.description else "unknown"
                # Sanitize tool name
                tool_name = "".join(c for c in tool_name if c.isalnum() or c == "_").lower()
                partial_files = self._read_task_files(task, tool_name)
            else:
                partial_files = {}

            # Create failure record in tool_failures collection
            failure_id = await self.tool_failure_repo.create_from_generation_failure(
                failure=failure,
                task_id=task_id,
                **partial_files  # Pass partial file contents
            )

            # Set failure ID in task (singular field, not array)
            await self.task_repo.set_tool_failure_id(task_id, failure_id)

            # Collect summary for logging
            req = failure.toolRequirement
            failure_summary = {
                "requirement": req.description if hasattr(req, 'description') else 'Unknown',
                "error": failure.error,
                "error_type": failure.error_type
            }

            logger.warning(f"Task {task_id} tool generation failed: {failure.error}")
            logger.info(f"Stored failure record: {failure_id}")

            # Notify about failure
            await self._notify_task_update(task_id, {
                "type": "generation-failure",
                "task_id": task_id,
                "failure": failure_summary
            })

            # Notify job that tool failed
            await self.job_service.decrement_in_progress(job_id)
            await self.job_service.increment_failed(job_id)

        except Exception as e:
            logger.error(f"Error storing generation failure for task {task_id}: {e}")
            # Don't raise - we don't want this to fail the entire workflow

    def _read_task_files(self, task: Task, tool_name: str) -> Dict[str, Optional[str]]:
        """
        Read all generated files for a task (tool code, test, plan, search results).

        Args:
            task: Task object with job_id and task_id
            tool_name: Name of the tool (without .py extension)

        Returns:
            Dict with file contents (None if file doesn't exist)
        """
        task_dir = os.path.join(self.settings.tools_path, task.job_id, task.task_id)

        files = {
            "code": None,
            "test_code": None,
            "implementation_plan": None,
            "function_spec": None,
            "contracts_plan": None,
            "validation_rules": None,
            "test_requirements": None,
            "search_results": None
        }

        # Read main tool code file
        tool_file = os.path.join(task_dir, f"{tool_name}.py")
        if os.path.exists(tool_file):
            try:
                with open(tool_file, "r") as f:
                    files["code"] = f.read()
                    logger.debug(f"Read tool code file: {tool_file}")
            except Exception as e:
                logger.warning(f"Failed to read tool code file {tool_file}: {e}")

        # Read test file
        test_file = os.path.join(task_dir, "tests", f"test_{tool_name}.py")
        if os.path.exists(test_file):
            try:
                with open(test_file, "r") as f:
                    files["test_code"] = f.read()
                    logger.debug(f"Read test file: {test_file}")
            except Exception as e:
                logger.warning(f"Failed to read test file {test_file}: {e}")

        # Read plan files
        plan_dir = os.path.join(task_dir, "plan")
        plan_files_map = {
            "implementation_plan": "implementation_plan.txt",
            "function_spec": "function_spec.txt",
            "contracts_plan": "contracts.txt",
            "validation_rules": "validation_rules.txt",
            "test_requirements": "test_requirements.txt"
        }

        for key, filename in plan_files_map.items():
            file_path = os.path.join(plan_dir, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r") as f:
                        files[key] = f.read()
                        logger.debug(f"Read plan file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to read plan file {file_path}: {e}")

        # Read search results (find the most recent api_refs_*.md file)
        searches_dir = os.path.join(task_dir, "searches")
        if os.path.exists(searches_dir):
            try:
                # Find all api_refs files (both .md and .json for backwards compatibility)
                api_ref_files = [f for f in os.listdir(searches_dir)
                                if f.startswith("api_refs_") and (f.endswith(".md") or f.endswith(".json"))]
                if api_ref_files:
                    # Sort by modification time, get most recent
                    api_ref_files.sort(key=lambda f: os.path.getmtime(os.path.join(searches_dir, f)), reverse=True)
                    latest_file = os.path.join(searches_dir, api_ref_files[0])
                    with open(latest_file, "r") as f:
                        files["search_results"] = f.read()
                        logger.debug(f"Read search results: {latest_file}")
            except Exception as e:
                logger.warning(f"Failed to read search results from {searches_dir}: {e}")

        return files

    async def _update_task_status(self, task_id: str, status: TaskStatus, error_message: Optional[str] = None):
        """Update task status and notify via WebSocket."""
        await self.task_repo.update_status(task_id, status, error_message)

        await self._notify_task_update(task_id, {
            "type": "status-update",
            "status": status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error_message
        })

    async def _notify_task_update(self, task_id: str, message: Dict[str, Any]):
        """Send WebSocket notification for task update."""
        if self.websocket_manager:
            try:
                # Get task to retrieve job_id
                task = await self.task_repo.get_by_id(task_id)
                if task:
                    # Format message according to frontend expectations
                    ws_message = {
                        "type": "task-status-changed",
                        "data": {
                            "taskId": task.task_id,
                            "jobId": task.job_id,
                            "status": message.get("status", str(task.status)),
                            "updatedAt": message.get("timestamp", datetime.now(timezone.utc).isoformat())
                        }
                    }
                    # Add any additional data from the original message
                    if "error" in message:
                        ws_message["data"]["error"] = message["error"]

                    await self.websocket_manager.send_to_task(task.task_id, task.job_id, ws_message)
                    logger.debug(f"Sent WebSocket notification for task {task_id}")
            except Exception as e:
                logger.error(f"Failed to send WebSocket notification for task {task_id}: {e}")

    async def _notify_agent_progress(self, task_id: str, progress: Dict[str, Any]):
        """Notify OpenAI agent progress via WebSocket."""
        await self._notify_task_update(task_id, {
            "type": "agent-progress",
            "agent": "openai_agent",
            "task_id": task_id,
            **progress
        })

    async def cleanup_completed_workflows(self):
        """Clean up completed workflow tasks."""
        completed_tasks = []

        for task_id, task in self.active_workflows.items():
            if task.done():
                completed_tasks.append(task_id)

        for task_id in completed_tasks:
            del self.active_workflows[task_id]

        if completed_tasks:
            logger.info(f"Cleaned up {len(completed_tasks)} completed workflows")

    def get_workflow_status(self, task_id: str) -> Optional[str]:
        """
        Get workflow status for a task.

        Args:
            task_id: Task ID

        Returns:
            Optional[str]: Workflow status or None if not found
        """
        if task_id not in self.active_workflows:
            return None

        task = self.active_workflows[task_id]

        if task.done():
            if task.cancelled():
                return "cancelled"
            elif task.exception():
                return "failed"
            else:
                return "completed"
        else:
            return "running"

    async def wait_for_task_completion(self, task_id: str, poll_interval: float = 1.0) -> Task:
        """
        Wait for a task to reach a terminal state (COMPLETED or FAILED).

        Args:
            task_id: Task ID (MongoDB _id)
            poll_interval: How often to poll the database (in seconds)

        Returns:
            Task: The completed task

        Raises:
            ValueError: If task is not found
        """
        logger.info(f"Waiting for task {task_id} to complete...")

        while True:
            # Get current task status from database
            task = await self.task_repo.get_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            # Check if task has reached a terminal state
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                logger.info(f"Task {task_id} reached terminal state: {task.status.value}")
                return task

            # Wait before polling again
            await asyncio.sleep(poll_interval)