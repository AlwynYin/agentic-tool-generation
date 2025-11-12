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
from app.config import get_settings
from app.dependencies import get_task_service

logger = logging.getLogger(__name__)

router = APIRouter()


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
            "implementationPlan": None,
            "functionSpec": None,
            "contractsPlan": None,
            "validationRules": None,
            "testRequirements": None,
            "searchResults": None,
            "error": None
        }

        # If task completed successfully, get tool code
        if task.tool_id:
            tool = await task_service.tool_repo.get_by_id(task.tool_id)
            if tool:
                # Tool code and all files are stored in the database
                response["toolCode"] = tool.code
                response["toolFileName"] = tool.file_name
                response["testCode"] = tool.test_code
                response["implementationPlan"] = tool.implementation_plan
                response["functionSpec"] = tool.function_spec
                response["contractsPlan"] = tool.contracts_plan
                response["validationRules"] = tool.validation_rules
                response["testRequirements"] = tool.test_requirements
                response["searchResults"] = tool.search_results

                # Set test file name if test code exists
                if tool.test_code:
                    tool_name = Path(tool.file_name).stem
                    response["testFileName"] = f"test_{tool_name}.py"
                    logger.info(f"Retrieved test code from database")
            else:
                logger.warning(f"Tool not found for task {taskId}: {task.tool_id}")
                response["error"] = f"Tool not found: {task.tool_id}"

        elif task.status == TaskStatus.FAILED or task.tool_failure_id:
            # Task failed - get error message and partial files from database

            # First, get the error message
            error_msg = task.error_message or "Task failed"

            # If there's a tool_failure record, get more details and partial files
            if task.tool_failure_id:
                try:
                    failure = await task_service.tool_failure_repo.get_by_id(task.tool_failure_id)
                    if failure:
                        error_msg = failure.error_message or error_msg
                        # Get partial files from database
                        response["toolCode"] = failure.code
                        response["testCode"] = failure.test_code
                        response["implementationPlan"] = failure.implementation_plan
                        response["functionSpec"] = failure.function_spec
                        response["contractsPlan"] = failure.contracts_plan
                        response["validationRules"] = failure.validation_rules
                        response["testRequirements"] = failure.test_requirements
                        response["searchResults"] = failure.search_results

                        # Set file names if code exists
                        if failure.code:
                            # Try to extract tool name from requirement
                            tool_name = failure.user_requirement.description.split()[0] if failure.user_requirement.description else "tool"
                            tool_name = "".join(c for c in tool_name if c.isalnum() or c == "_").lower()
                            response["toolFileName"] = f"{tool_name}.py"

                        logger.info(f"Retrieved failure details and partial files for task {taskId}")
                except Exception as e:
                    logger.warning(f"Failed to get failure details: {e}")

            response["error"] = error_msg

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
