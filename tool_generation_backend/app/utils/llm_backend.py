"""
LLM Backend abstraction layer.

This module provides a unified interface for different LLM backends (Codex, Claude Code)
allowing seamless switching between them via configuration.
"""

import logging
from typing import Dict, Any, List, Optional

from app.config import get_settings
from app.models import ImplementationPlan
from app.models.api_reference import ApiBrowseResult
from app.utils.codex_utils import authenticate_codex, execute_codex_browse, execute_codex_implement
from app.utils.claude_utils import authenticate_claude, execute_claude_browse, execute_claude_implement

logger = logging.getLogger(__name__)


def authenticate_llm() -> bool:
    """
    Authenticate the configured LLM backend.

    Returns:
        bool: True if authentication successful, False otherwise
    """
    settings = get_settings()
    backend = settings.llm_backend.lower()

    if backend == "codex":
        return authenticate_codex(settings.openai_api_key)
    elif backend == "claude":
        api_key = settings.anthropic_api_key if settings.anthropic_api_key else None
        return authenticate_claude(api_key)
    else:
        logger.error(f"Unknown LLM backend: {backend}")
        return False


async def execute_llm_implement(plan: ImplementationPlan) -> Dict[str, Any]:
    """
    Execute LLM backend to implement/generate code.

    Args:
        plan: Implementation plan containing job_id, task_id, requirement, and api_refs

    Returns:
        Dict with implementation result
    """
    settings = get_settings()
    backend = settings.llm_backend.lower()

    logger.info(f"Using {backend.upper()} backend for implementation")

    if backend == "codex":
        return await execute_codex_implement(plan)
    elif backend == "claude":
        return await execute_claude_implement(plan)
    else:
        logger.error(f"Unknown LLM backend: {backend}")
        return {
            "success": False,
            "tool_name": plan.requirement.name,
            "error": f"Unknown LLM backend: {backend}"
        }


async def execute_llm_browse(
    library: str,
    queries: List[str],
    task_id: Optional[str] = None,
    job_id: Optional[str] = None
) -> ApiBrowseResult:
    """
    Execute LLM backend to browse/search documentation.

    Args:
        library: Library name (rdkit, ase, pymatgen, pyscf)
        queries: List of search queries for API documentation
        task_id: Optional task ID for V2 pipeline
        job_id: Optional job ID for V2 pipeline

    Returns:
        ApiBrowseResult with structured API function references
    """
    settings = get_settings()
    backend = settings.llm_backend.lower()

    logger.info(f"Using {backend.upper()} backend for browsing")

    if backend == "codex":
        return await execute_codex_browse(library, queries, task_id, job_id)
    elif backend == "claude":
        return await execute_claude_browse(library, queries, task_id, job_id)
    else:
        logger.error(f"Unknown LLM backend: {backend}")
        return ApiBrowseResult(
            success=False,
            library=library,
            queries=queries,
            error=f"Unknown LLM backend: {backend}"
        )
