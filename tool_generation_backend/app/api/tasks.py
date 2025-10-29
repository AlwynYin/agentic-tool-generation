"""
Task management API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
import logging

from app.models.task import (
    TaskCreate, TaskUpdate, TaskResponse, Task,
    TaskStatus
)
from app.models.tool import Tool
from app.services.task_service import TaskService
from app.repositories.task_repository import TaskRepository
from app.repositories.tool_repository import ToolRepository
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


# Dependency injection
async def get_task_service() -> TaskService:
    """Get task service instance with agent workflow."""
    # Initialize repositories
    task_repo = TaskRepository()
    tool_repo = ToolRepository()

    # Create and return task service (OpenAI Agent SDK handled internally)
    return TaskService(
        task_repo=task_repo,
        tool_repo=tool_repo
    )

## TODO: task get methods here
