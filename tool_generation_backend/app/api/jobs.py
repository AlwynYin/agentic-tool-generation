"""
Job management API endpoints for tool generation requests.
"""

from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, status, Query
from datetime import datetime, timezone

import logging
import uuid
import re

from app.services.job_service import JobService
from app.models.job import *
from app.models.tool import ToolStatus
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


# Dependency injection
async def get_job_service() -> JobService:
    """Get job service instance."""
    return JobService()


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of jobs to return"),
    skip: int = Query(default=0, ge=0, description="Number of jobs to skip (pagination)"),
    job_service: JobService = Depends(get_job_service)
) -> List[JobResponse]:
    """
    List all jobs with pagination.

    Args:
        limit: Maximum number of jobs to return (default: 100, max: 500)
        skip: Number of jobs to skip for pagination (default: 0)
        job_service: Job service instance

    Returns:
        List[JobResponse]: List of jobs ordered by creation date (newest first)
    """
    try:
        logger.info(f"Listing jobs with limit={limit}, skip={skip}")

        # Get jobs from repository
        jobs = await job_service.job_repo.get_all_jobs(limit=limit, skip=skip)

        # Convert to response models
        job_responses = []
        for job in jobs:
            progress = JobProgress(
                total=job.total_tools,
                completed=job.tools_completed,
                failed=job.tools_failed,
                inProgress=job.tools_in_progress,
                currentTool=None if job.is_complete else "processing"
            )

            job_responses.append(JobResponse(
                jobId=job.job_id,
                status=job.status.value if isinstance(job.status, JobStatus) else job.status,
                createdAt=job.created_at.isoformat() if job.created_at else datetime.now(timezone.utc).isoformat(),
                updatedAt=job.updated_at.isoformat() if job.updated_at else datetime.now(timezone.utc).isoformat(),
                taskDescription=job.task_description,
                toolRequirements=job.tool_requirements,
                progress=progress
            ))

        logger.info(f"Retrieved {len(job_responses)} jobs")
        return job_responses

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list jobs: {str(e)}"
        )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def submit_tool_generation_job(
    request: ToolGenerationRequest,
    job_service: JobService = Depends(get_job_service)
) -> JobResponse:
    """
    Create a new tool generation job.
    This will spawn multiple sessions (one per tool requirement).

    Args:
        request: Tool generation request data
        job_service: Job service instance

    Returns:
        JobResponse: Job submission result
    """
    try:
        client_id = request.metadata.clientId if request.metadata else "unknown"

        logger.info(f"Received tool generation request from client {client_id}: {len(request.toolRequirements)} tools")

        # Create job (this spawns sessions asynchronously)
        job_db_id = await job_service.create_job(
            user_id=client_id,
            tool_requirements=request.toolRequirements
        )

        # Get the created job to get job_id_short
        job = await job_service.get_job_by_id(job_db_id)
        if not job:
            raise ValueError(f"Job {job_db_id} not found after creation")

        logger.info(f"Created job {job.job_id} (DB ID: {job_db_id}) with {len(request.toolRequirements)} tool requirements")

        # Create response
        progress = JobProgress(
            total=len(request.toolRequirements),
            completed=0,
            failed=0,
            inProgress=len(request.toolRequirements),
            currentTool="initializing"
        )

        return JobResponse(
            jobId=job.job_id,
            status=job.status.value if isinstance(job.status, JobStatus) else job.status,
            createdAt=job.created_at.isoformat() if job.created_at else datetime.now(timezone.utc).isoformat(),
            updatedAt=job.updated_at.isoformat() if job.updated_at else datetime.now(timezone.utc).isoformat(),
            taskDescription=job.task_description,
            progress=progress
        )

    except Exception as e:
        import traceback
        logger.error(f"Failed to submit tool generation job: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit job: {str(e)}"
        )


@router.get("/{jobId}", response_model=JobResponse)
async def get_job_status(
    jobId: str,
    job_service: JobService = Depends(get_job_service)
) -> JobResponse:
    """
    Get the status of a tool generation job.

    Args:
        jobId: Job ID (short identifier, e.g., job_abc123)
        job_service: Job service instance

    Returns:
        JobResponse with job status and progress
    """
    try:
        # Get job by job_id (short identifier)
        job = await job_service.get_job_by_job_id(jobId)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {jobId}"
            )

        logger.info(f"Retrieved job {jobId}")

        # Progress is tracked directly in job counters
        progress = JobProgress(
            total=job.total_tools,
            completed=job.tools_completed,
            failed=job.tools_failed,
            inProgress=job.tools_in_progress,
            currentTool=None if job.is_complete else "processing"
        )

        # Fetch actual tools from tools collection if completed
        tool_files_response = None
        if job.status == JobStatus.COMPLETED:
            tools_data = await job_service.get_job_tools(job.id)
            if tools_data:
                tool_files_response = [
                    ToolFile(
                        toolId=tool_dict["id"],
                        fileName=tool_dict["file_name"],
                        filePath=tool_dict["file_path"],
                        description=tool_dict["description"],
                        code=tool_dict["code"],
                        endpoint=None,  # No endpoints since we're not using SimpleTooling
                        registered=tool_dict["status"] == ToolStatus.REGISTERED.value,
                        createdAt=tool_dict["created_at"].isoformat() if isinstance(tool_dict.get("created_at"), datetime) else tool_dict.get("created_at", datetime.now(timezone.utc).isoformat())
                    )
                    for tool_dict in tools_data
                ]

        # Fetch failures from tool_failures collection if completed
        failures_response = None
        if job.status == JobStatus.COMPLETED:
            from app.models.tool_generation import ToolGenerationFailure
            failures_data = await job_service.get_job_failures(job.id)
            if failures_data:
                failures_response = [
                    ToolGenerationFailure(
                        toolRequirement=failure_dict["user_requirement"],
                        error=failure_dict["error_message"],
                        error_type=failure_dict.get("error_type", "unknown")
                    )
                    for failure_dict in failures_data
                ]

        return JobResponse(
            jobId=jobId,
            status=job.status.value if isinstance(job.status, JobStatus) else job.status,
            createdAt=job.created_at.isoformat() if job.created_at else datetime.now(timezone.utc).isoformat(),
            updatedAt=job.updated_at.isoformat() if job.updated_at else datetime.now(timezone.utc).isoformat(),
            taskDescription=job.task_description,
            toolRequirements=job.tool_requirements,
            progress=progress,
            toolFiles=tool_files_response,
            failures=failures_response,
            summary=GenerationSummary(
                totalRequested=job.total_tools,
                successful=job.tools_completed,
                failed=job.tools_failed
            ) if job.status == JobStatus.COMPLETED or job.status == "completed" else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {jobId}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}"
        )


@router.get("/{jobId}/tasks")
async def get_job_tasks(
    jobId: str,
    job_service: JobService = Depends(get_job_service)
) -> List[Dict[str, Any]]:
    """
    Get all tasks for a specific job.

    Args:
        jobId: Job ID (short identifier, e.g., job_abc123)
        job_service: Job service instance

    Returns:
        List of tasks with their details
    """
    try:
        # Get job by job_id to get the DB ID
        job = await job_service.get_job_by_job_id(jobId)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {jobId}"
            )

        logger.info(f"Getting tasks for job {jobId}")

        # Get all tasks for this job using the DB ID
        tasks = await job_service.get_job_tasks(job.id)

        logger.info(f"Retrieved {len(tasks)} tasks for job {jobId}")
        return tasks

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tasks for job {jobId}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tasks: {str(e)}"
        )


