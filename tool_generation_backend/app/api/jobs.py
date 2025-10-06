"""
Job management API endpoints for tool generation requests.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime, timezone

import logging
import uuid
import re

from app.services.session_service import SessionService
from app.repositories.session_repository import SessionRepository
from app.repositories.tool_repository import ToolRepository
from app.models.job import *
from app.models.session import SessionStatus
from app.models.tool import ToolStatus
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


# Dependency injection
async def get_session_service() -> SessionService:
    """Get session service instance."""
    session_repo = SessionRepository()
    tool_repo = ToolRepository()
    return SessionService(
        session_repo=session_repo,
        tool_repo=tool_repo
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def submit_tool_generation_job(
    request: ToolGenerationRequest,
    session_service: SessionService = Depends(get_session_service)
) -> JobResponse:
    """
    Create a new tool generation job.

    Args:
        request: Tool generation request data
        session_service: Session service instance

    Returns:
        JobResponse: Job submission result
    """
    try:
        # Generate job ID
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        client_id = request.metadata.clientId if request.metadata else "unknown"
        # session_id_meta = request.metadata.sessionId if request.metadata else None

        logger.info(f"Received tool generation job {job_id} from client {client_id}: {len(request.toolRequirements)} tools")

        session_id = await session_service.create_session(
            job_id=job_id,
            user_id=client_id,
            tool_requirements=request.toolRequirements,
            operation_type="generate"
        )
        logger.info(f"Created session {session_id} for job {job_id}")

        # The workflow will handle tool generation asynchronously
        # No need to await here - let the background task handle it

        # Create response
        now = datetime.now(timezone.utc)
        progress = JobProgress(
            total=len(request.toolRequirements),
            completed=0,
            failed=0,
            inProgress=len(request.toolRequirements),
            currentTool="initializing"
        )

        return JobResponse(
            jobId=job_id,
            status=SessionStatus.PENDING.value,
            createdAt=now.isoformat(),
            updatedAt=now.isoformat(),
            progress=progress
        )

    except Exception as e:
        logger.error(f"Failed to submit tool generation job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit job: {str(e)}"
        )


@router.get("/{jobId}", response_model=JobResponse)
async def get_job_status(
    jobId: str,
    session_service: SessionService = Depends(get_session_service)
) -> JobResponse:
    """
    Get the status of a tool generation job.

    Args:
        jobId: Job ID (same as session ID)
        session_service: Session service instance

    Returns:
        Dict with job status information
    """
    try:
        # Get session by job ID (search in requirement field)
        session = await session_service.get_session_by_job_id(jobId)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {jobId}"
            )

        logger.info(f"Retrieved session {session.id} for job {jobId}")

        # Get detailed workflow status
        # workflow_status = session_service.get_workflow_status(session.id)

        # Get total tool count from session requirements
        total_tools = len(session.tool_requirements) if session.tool_requirements else 1

        # Get tools from tools collection using tool_ids
        tool_count = len(session.tool_ids) if session.tool_ids else 0

        # Check if session is in terminal state
        is_terminal = session.status in [SessionStatus.COMPLETED, SessionStatus.FAILED]

        progress = JobProgress(
            total=total_tools,
            completed=tool_count,
            failed=0,
            inProgress=0 if is_terminal else (total_tools - tool_count),
            currentTool=None if is_terminal else "processing"
        )

        # Fetch actual tools from tools collection if completed
        tool_files_response = None
        if session.status == SessionStatus.COMPLETED and session.tool_ids:
            tools = await session_service.get_session_tools(session.id)
            tool_files_response = [
                ToolFile(
                    toolId=tool.id,
                    fileName=tool.file_name,
                    filePath=tool.file_path,
                    description=tool.description,
                    code=tool.code,
                    endpoint=None,  # No endpoints since we're not using SimpleTooling
                    registered=tool.status == ToolStatus.REGISTERED,
                    createdAt=session.created_at.isoformat() if session.created_at else datetime.now(timezone.utc).isoformat()
                )
                for tool in tools
            ]

        return JobResponse(
            jobId=jobId,
            status=session.status,  # Convert enum to string for API response
            createdAt=session.created_at.isoformat() if session.created_at else datetime.now(timezone.utc).isoformat(),
            updatedAt=session.updated_at.isoformat() if session.updated_at else datetime.now(timezone.utc).isoformat(),
            progress=progress,
            toolFiles=tool_files_response,
            failures=None,
            summary=GenerationSummary(
                totalRequested=tool_count,
                successful=tool_count,
                failed=0
            ) if session.status == SessionStatus.COMPLETED else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {jobId}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}"
        )


