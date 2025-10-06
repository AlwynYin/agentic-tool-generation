"""
Session management API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
import logging

from app.models.session import (
    SessionCreate, SessionUpdate, SessionResponse, Session,
    SessionStatus
)
from app.models.tool import Tool
from app.services.session_service import SessionService
from app.repositories.session_repository import SessionRepository
from app.repositories.tool_repository import ToolRepository
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


# Dependency injection
async def get_session_service() -> SessionService:
    """Get session service instance with agent workflow."""
    # Initialize repositories
    session_repo = SessionRepository()
    tool_repo = ToolRepository()

    # Create and return session service (OpenAI Agent SDK handled internally)
    return SessionService(
        session_repo=session_repo,
        tool_repo=tool_repo
    )


# @router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    session_service: SessionService = Depends(get_session_service)
) -> SessionResponse:
    """
    Create a new computation session.

    Args:
        session_data: Session creation data
        session_service: Session service instance

    Returns:
        SessionResponse: Created session information
    """
    try:
        session_id = await session_service.create_session(session_data)

        # Get created session for response
        session = await session_service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created session"
            )

        return SessionResponse(
            session_id=session_id,
            status=session.status,
            created_at=session.created_at,
            updated_at=session.updated_at
        )

    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


# @router.get("/{session_id}", response_model=Session)
async def get_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service)
) -> Session:
    """
    Get session by ID.

    Args:
        session_id: Session ID
        session_service: Session service instance

    Returns:
        Session: Session data
    """
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    return session


# @router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    update_data: SessionUpdate,
    session_service: SessionService = Depends(get_session_service)
) -> SessionResponse:
    """
    Update session data.

    Args:
        session_id: Session ID
        update_data: Update data
        session_service: Session service instance

    Returns:
        SessionResponse: Updated session information
    """
    # Check if session exists
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    # Update session
    success = await session_service.update_session(session_id, update_data)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update session"
        )

    # Get updated session
    updated_session = await session_service.get_session(session_id)
    if not updated_session:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated session"
        )

    return SessionResponse(
        session_id=session_id,
        status=updated_session.status,
        created_at=updated_session.created_at,
        updated_at=updated_session.updated_at
    )


# @router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_session(
    session_id: str,
    reason: str = "User requested cancellation",
    session_service: SessionService = Depends(get_session_service)
):
    """
    Cancel an active session.

    Args:
        session_id: Session ID
        reason: Cancellation reason
        session_service: Session service instance
    """
    # Check if session exists
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    # Cancel session
    success = await session_service.cancel_session(session_id, reason)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel session"
        )


# @router.get("/user/{user_id}", response_model=List[Session])
async def get_user_sessions(
    user_id: str,
    limit: int = 50,
    session_service: SessionService = Depends(get_session_service)
) -> List[Session]:
    """
    Get sessions for a specific user.

    Args:
        user_id: User ID
        limit: Maximum number of sessions to return
        session_service: Session service instance

    Returns:
        List[Session]: User's sessions
    """
    try:
        sessions = await session_service.get_user_sessions(user_id, limit)
        return sessions

    except Exception as e:
        logger.error(f"Failed to get user sessions for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user sessions: {str(e)}"
        )


# @router.get("/status/{status_value}", response_model=List[Session])
async def get_sessions_by_status(
    status_value: str,
    limit: Optional[int] = None,
    session_service: SessionService = Depends(get_session_service)
) -> List[Session]:
    """
    Get sessions by status.

    Args:
        status_value: Session status
        limit: Maximum number of sessions to return
        session_service: Session service instance

    Returns:
        List[Session]: Sessions with specified status
    """
    try:
        # Validate status
        try:
            session_status = SessionStatus(status_value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid session status: {status_value}"
            )

        sessions = await session_service.session_repo.get_sessions_by_status(session_status, limit)
        return sessions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sessions by status {status_value}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sessions by status: {str(e)}"
        )


# @router.get("/", response_model=List[Session])
async def get_active_sessions(
    limit: Optional[int] = None,
    session_service: SessionService = Depends(get_session_service)
) -> List[Session]:
    """
    Get active sessions.

    Args:
        limit: Maximum number of sessions to return
        session_service: Session service instance

    Returns:
        List[Session]: Active sessions
    """
    try:
        sessions = await session_service.get_active_sessions(limit)
        return sessions

    except Exception as e:
        logger.error(f"Failed to get active sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active sessions: {str(e)}"
        )


# @router.get("/{session_id}/tools", response_model=List[Tool])
async def get_session_tools(
    session_id: str,
    session_service: SessionService = Depends(get_session_service)
) -> List[Tool]:
    """
    Get tools generated for a session.

    Args:
        session_id: Session ID
        session_service: Session service instance

    Returns:
        List[Tool]: Session tools
    """
    # Check if session exists
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    # Get tools from tools collection
    return await session_service.get_session_tools(session_id)


# @router.get("/{session_id}/status")
async def get_session_status(
    session_id: str,
    session_service: SessionService = Depends(get_session_service)
) -> dict:
    """
    Get detailed session status including workflow progress.

    Args:
        session_id: Session ID
        session_service: Session service instance

    Returns:
        dict: Detailed session status
    """
    # Check if session exists
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    # Get workflow status
    workflow_status = session_service.get_workflow_status(session_id)

    return {
        "session_id": session_id,
        "status": session.status.value,
        "workflow_status": workflow_status,
        "tools_count": len(session.tool_ids),
        "error_message": session.error_message,
        "created_at": session.created_at,
        "updated_at": session.updated_at
    }


# Health check endpoint for session service
# @router.get("/health/sessions")
async def session_service_health() -> dict:
    """
    Health check for session service.

    Returns:
        dict: Service health information
    """
    try:
        # Test database connection
        session_repo = SessionRepository()
        count = await session_repo.count()

        return {
            "status": "healthy",
            "service": "session-service",
            "total_sessions": count,
            "timestamp": "2024-01-01T00:00:00Z"  # Would use actual timestamp
        }

    except Exception as e:
        logger.error(f"Session service health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "session-service",
                "error": str(e),
                "timestamp": "2024-01-01T00:00:00Z"  # Would use actual timestamp
            }
        )