"""
Task management API endpoints for individual tool generation tasks.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime, timezone
from pathlib import Path

import logging

from app.services.task_service import TaskService
from app.models.task import Task, TaskStatus, TaskResponse
from app.models.tool import Tool
from app.repositories.task_repository import TaskRepository
from app.repositories.tool_repository import ToolRepository
from app.repositories.tool_failure_repository import ToolFailureRepository
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


# Dependency injection
async def get_task_service() -> TaskService:
    """Get task service instance."""
    task_repo = TaskRepository()
    tool_repo = ToolRepository()
    tool_failure_repo = ToolFailureRepository()
    return TaskService(
        task_repo=task_repo,
        tool_repo=tool_repo,
        tool_failure_repo=tool_failure_repo
    )


@router.get("/{taskId}", response_model=TaskResponse)
async def get_task(
    taskId: str,
    task_service: TaskService = Depends(get_task_service)
) -> TaskResponse:
    """
    Get detailed information about a specific task.

    Args:
        taskId: Task ID (short identifier, e.g., task_abc123)
        task_service: Task service instance

    Returns:
        TaskResponse with task details
    """
    try:
        logger.info(f"Getting task: {taskId}")

        # Get task from repository
        task = await task_service.task_repo.get_by_task_id(taskId)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {taskId}"
            )

        logger.info(f"Retrieved task {taskId} with status {task.status}")

        return TaskResponse(
            task_id=task.task_id,
            job_id=task.job_id,
            status=task.status,
            tool_requirement=task.tool_requirement,
            created_at=task.created_at.isoformat() if task.created_at else datetime.now(timezone.utc).isoformat(),
            updated_at=task.updated_at.isoformat() if task.updated_at else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task {taskId}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task: {str(e)}"
        )


@router.get("/{taskId}/files")
async def get_task_files(
    taskId: str,
    task_service: TaskService = Depends(get_task_service)
) -> Dict[str, Any]:
    """
    Get tool code and test code for a task.

    Args:
        taskId: Task ID (short identifier, e.g., task_abc123)
        task_service: Task service instance

    Returns:
        Dict with tool_code and test_code strings
    """
    try:
        logger.info(f"Getting files for task: {taskId}")

        # Get task from repository
        task = await task_service.task_repo.get_by_task_id(taskId)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {taskId}"
            )

        settings = get_settings()

        # Determine file paths based on task structure
        # V2 pipeline structure: tools/{job_id}/{task_id}/
        task_dir = Path(settings.tools_path) / task.job_id / task.task_id

        # Initialize response
        response = {
            "taskId": taskId,
            "status": task.status.value if isinstance(task.status, TaskStatus) else task.status,
            "toolCode": None,
            "testCode": None,
            "toolFileName": None,
            "testFileName": None,
            "error": None
        }

        # If task completed successfully, get tool code
        if task.tool_id:
            tool = await task_service.tool_repo.get_by_id(task.tool_id)
            if tool:
                # Tool code is stored in the database
                response["toolCode"] = tool.code
                response["toolFileName"] = tool.file_name

                # Try to find test file in tests/ subdirectory
                # Test files are typically in tests/test_{tool_name}.py
                tool_name = Path(tool.file_name).stem  # Remove .py extension
                test_file_name = f"test_{tool_name}.py"

                # Check in tests/ subdirectory
                test_file_path = task_dir / "tests" / test_file_name
                if not test_file_path.exists():
                    # Fallback: check directly in task directory
                    test_file_path = task_dir / test_file_name

                if test_file_path.exists():
                    try:
                        response["testCode"] = test_file_path.read_text(encoding="utf-8")
                        response["testFileName"] = test_file_name
                        logger.info(f"Found test file: {test_file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to read test file {test_file_path}: {e}")
                        response["error"] = f"Failed to read test file: {str(e)}"
                else:
                    logger.warning(f"Test file not found: {test_file_path}")
                    response["error"] = f"Test file not found: {test_file_name}"
            else:
                logger.warning(f"Tool not found for task {taskId}: {task.tool_id}")
                response["error"] = f"Tool not found: {task.tool_id}"

        elif task.status == TaskStatus.FAILED or task.tool_failure_id:
            # Task failed - get error message and try to find any generated files

            # First, get the error message
            error_msg = task.error_message or "Task failed"

            # If there's a tool_failure record, get more details
            if task.tool_failure_id:
                try:
                    failure = await task_service.tool_failure_repo.get_by_id(task.tool_failure_id)
                    if failure:
                        error_msg = failure.error_message or error_msg
                        logger.info(f"Retrieved failure details for task {taskId}")
                except Exception as e:
                    logger.warning(f"Failed to get failure details: {e}")

            response["error"] = error_msg

            # Try to find any generated files in the task directory (partial work)
            if task_dir.exists():
                # Look for Python files (excluding test files)
                tool_files = [f for f in task_dir.glob("*.py") if not f.name.startswith("test_")]

                # Also check tests/ subdirectory
                tests_dir = task_dir / "tests"
                test_files = []
                if tests_dir.exists():
                    test_files = list(tests_dir.glob("test_*.py"))
                else:
                    test_files = [f for f in task_dir.glob("test_*.py")]

                if tool_files:
                    try:
                        response["toolCode"] = tool_files[0].read_text(encoding="utf-8")
                        response["toolFileName"] = tool_files[0].name
                        logger.info(f"Found partial tool file: {tool_files[0]}")
                    except Exception as e:
                        logger.warning(f"Failed to read tool file {tool_files[0]}: {e}")

                if test_files:
                    try:
                        response["testCode"] = test_files[0].read_text(encoding="utf-8")
                        response["testFileName"] = test_files[0].name
                        logger.info(f"Found partial test file: {test_files[0]}")
                    except Exception as e:
                        logger.warning(f"Failed to read test file {test_files[0]}: {e}")

        else:
            # Task is still in progress or pending
            response["error"] = "Task not yet completed"

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task files for {taskId}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task files: {str(e)}"
        )
