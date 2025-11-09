#!/usr/bin/env python3
"""
Mini-pipeline for testing requirement extraction and job submission.

This script:
1. Takes a string description of a task
2. Uses RequirementExtractionAgent to generate List[UserToolRequirement]
3. Submits the requirements as a job
4. Prints job status

Usage:
    python scripts/test_mini_pipeline.py "I need tools to calculate molecular properties from SMILES"
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.requirement_extraction_agent import RequirementExtractionAgent
from app.services.job_service import JobService
from app.config import get_settings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_mini_pipeline(task_description: str, user_id: str = "test_user"):
    """
    Run the mini-pipeline: extract requirements and submit as job.

    Args:
        task_description: Natural language description of what to build
        user_id: User identifier (defaults to "test_user")

    Returns:
        str: Job ID if successful, None otherwise
    """
    try:
        logger.info("=" * 80)
        logger.info("MINI-PIPELINE TEST")
        logger.info("=" * 80)
        logger.info(f"Task Description: {task_description}")
        logger.info("")

        # Step 1: Extract requirements using agent
        logger.info("Step 1: Extracting tool requirements...")
        extraction_agent = RequirementExtractionAgent()
        requirements = await extraction_agent.extract_requirements(task_description)

        if not requirements:
            logger.error("No requirements extracted. Cannot proceed.")
            return None

        logger.info(f"Extracted {len(requirements)} requirement(s):")
        for i, req in enumerate(requirements, 1):
            logger.info(f"  {i}. {req.description}")
            logger.info(f"     Input: {req.input}")
            logger.info(f"     Output: {req.output}")
        logger.info("")

        # Step 2: Submit requirements as a job
        logger.info("Step 2: Submitting job...")
        job_service = JobService()
        job_id = await job_service.create_job(
            user_id=user_id,
            tool_requirements=requirements
        )

        logger.info(f"Job created successfully!")
        logger.info(f"Job ID: {job_id}")
        logger.info("")

        # Step 3: Fetch and display job status
        logger.info("Step 3: Fetching job status...")
        job = await job_service.get_job_by_id(job_id)

        if job:
            logger.info(f"Job Status: {job.status}")
            logger.info(f"Tools Completed: {job.tools_completed}")
            logger.info(f"Tools Failed: {job.tools_failed}")
            logger.info(f"Tools In Progress: {job.tools_in_progress}")
            logger.info(f"Total Requirements: {len(requirements)}")
        else:
            logger.warning("Could not fetch job status")

        logger.info("")
        logger.info("=" * 80)
        logger.info("MINI-PIPELINE COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Job ID: {job_id}")
        logger.info(f"You can monitor progress by querying the job status")
        logger.info("")

        return job_id

    except Exception as e:
        logger.error(f"Mini-pipeline failed: {e}", exc_info=True)
        return None


async def main():
    """Main entry point for the mini-pipeline test script."""
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_mini_pipeline.py <task_description>")
        print("")
        print("Examples:")
        print('  python scripts/test_mini_pipeline.py "Calculate molecular properties from SMILES"')
        print('  python scripts/test_mini_pipeline.py "Optimize molecular geometry using force fields"')
        print('  python scripts/test_mini_pipeline.py "Tools for quantum chemistry calculations"')
        sys.exit(1)

    task_description = sys.argv[1]
    user_id = sys.argv[2] if len(sys.argv) > 2 else "test_user"

    # Run the mini-pipeline
    job_id = await run_mini_pipeline(task_description, user_id)

    if job_id:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
