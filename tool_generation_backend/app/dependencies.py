"""
Centralized dependency injection for FastAPI with singleton pattern.

All services and repositories are instantiated as singletons using @lru_cache().
This ensures:
- Single instance per application lifecycle
- Proper state management (e.g., TaskService.active_workflows)
- Reduced object creation overhead
- Test-friendly dependency injection
"""

from functools import lru_cache
from typing import Optional

from fastapi import Request

from app.repositories.task_repository import TaskRepository
from app.repositories.job_repository import JobRepository
from app.repositories.tool_repository import ToolRepository
from app.repositories.tool_failure_repository import ToolFailureRepository
from app.services.task_service import TaskService
from app.services.job_service import JobService
from app.services.repository_service import RepositoryService
from app.websocket.manager import WebSocketManager


# Module-level WebSocket manager reference (set during startup)
_websocket_manager: Optional[WebSocketManager] = None


def set_websocket_manager(manager: WebSocketManager) -> None:
    """Set the WebSocket manager singleton.

    Called once during application startup in main.py.

    Args:
        manager: WebSocket manager instance
    """
    global _websocket_manager
    _websocket_manager = manager


def get_websocket_manager_direct() -> Optional[WebSocketManager]:
    """Get WebSocket manager without requiring Request object.

    Returns None if not yet initialized (during early startup).

    Returns:
        WebSocketManager instance or None
    """
    return _websocket_manager


# Repository Singletons
@lru_cache()
def get_task_repository() -> TaskRepository:
    """Get singleton TaskRepository instance."""
    return TaskRepository()


@lru_cache()
def get_job_repository() -> JobRepository:
    """Get singleton JobRepository instance."""
    return JobRepository()


@lru_cache()
def get_tool_repository() -> ToolRepository:
    """Get singleton ToolRepository instance."""
    return ToolRepository()


@lru_cache()
def get_tool_failure_repository() -> ToolFailureRepository:
    """Get singleton ToolFailureRepository instance."""
    return ToolFailureRepository()


# Service Singletons
@lru_cache()
def get_task_service() -> TaskService:
    """Get singleton TaskService instance.

    This ensures active_workflows state persists across requests.
    """
    return TaskService(
        task_repo=get_task_repository(),
        tool_repo=get_tool_repository(),
        tool_failure_repo=get_tool_failure_repository()
    )


@lru_cache()
def get_job_service() -> JobService:
    """Get singleton JobService instance."""
    return JobService(
        job_repo=get_job_repository(),
        task_repo=get_task_repository(),
        tool_repo=get_tool_repository(),
        tool_failure_repo=get_tool_failure_repository(),
        task_service=get_task_service()
    )


@lru_cache()
def get_repository_service() -> RepositoryService:
    """Get singleton RepositoryService instance.

    This ensures package config cache persists across requests.
    """
    return RepositoryService()


def get_websocket_manager(request: Request) -> WebSocketManager:
    """Get WebSocket manager from app state.

    The WebSocket manager is initialized once at startup in main.py
    and stored in app.state for the application lifetime.

    Args:
        request: FastAPI request object

    Returns:
        WebSocketManager instance from app state
    """
    return request.app.state.websocket_manager
