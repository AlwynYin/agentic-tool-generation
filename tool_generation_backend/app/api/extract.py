"""
Simple API endpoint for requirement extraction + job submission.
For testing purposes only - not production ready.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import logging

from app.agents.requirement_extraction_agent import RequirementExtractionAgent
from app.services.job_service import JobService

logger = logging.getLogger(__name__)

router = APIRouter()


class ExtractionRequest(BaseModel):
    """Request to extract requirements from a task description."""
    task_description: str = Field(..., description="Natural language description of tools to build")
    client_id: str = Field(default="extract-api", description="Client identifier")


class ExtractionResponse(BaseModel):
    """Response with extracted requirements and created job."""
    job_id: str = Field(..., description="ID of created job")
    requirements_count: int = Field(..., description="Number of requirements extracted")
    status: str = Field(..., description="Job status")


@router.post("/extract-and-submit", response_model=ExtractionResponse)
async def extract_and_submit(request: ExtractionRequest) -> ExtractionResponse:
    """
    Extract tool requirements from description and submit job.

    This is a simple endpoint for testing:
    1. Extracts requirements using RequirementExtractionAgent
    2. Submits them to the job service
    3. Returns the job ID

    Args:
        request: Task description to extract requirements from

    Returns:
        ExtractionResponse with job ID and requirement count
    """
    try:
        logger.info(f"Extracting requirements from: {request.task_description[:100]}...")

        # Extract requirements
        agent = RequirementExtractionAgent()
        requirements = await agent.extract_requirements(request.task_description)

        if not requirements:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid requirements extracted from description"
            )

        logger.info(f"Extracted {len(requirements)} requirements")

        # Submit job with task description
        job_service = JobService()
        job_id = await job_service.create_job(
            user_id=request.client_id,
            tool_requirements=requirements,
            task_description=request.task_description
        )

        # Get job to get short ID
        job = await job_service.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found after creation")

        logger.info(f"Created job {job.job_id} with {len(requirements)} requirements")

        return ExtractionResponse(
            job_id=job.job_id,
            requirements_count=len(requirements),
            status=job.status.value
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to extract and submit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract and submit: {str(e)}"
        )