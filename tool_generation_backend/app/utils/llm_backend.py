"""
LLM Backend abstraction layer.

This module provides a unified interface for different LLM backends (Codex, Claude Code)
allowing seamless switching between them via configuration.

All prompting logic is centralized here. Backend-specific utils handle only CLI execution.
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import json

from app.config import get_settings
from app.models import ToolRequirement, ImplementationPlan
from app.models.api_reference import ApiBrowseResult
from app.utils.codex_utils import run_codex_query
from app.utils.claude_utils import run_claude_query

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
        from app.utils.codex_utils import authenticate_codex
        return authenticate_codex(settings.openai_api_key)
    elif backend == "claude":
        from app.utils.claude_utils import authenticate_claude
        api_key = settings.anthropic_api_key if settings.anthropic_api_key else None
        return authenticate_claude(api_key)
    else:
        logger.error(f"Unknown LLM backend: {backend}")
        return False


async def execute_llm_browse(
    libraries: List[str],
    questions: List[str],
    questions_file_path: str,
    task_id: Optional[str] = None,
    job_id: Optional[str] = None
) -> ApiBrowseResult:
    """
    Execute LLM backend to browse/search documentation across multiple libraries.

    Args:
        libraries: List of available library names (rdkit, ase, pymatgen, pyscf, orca)
        questions: List of open questions from Intake Agent
        questions_file_path: Path to file with questions
        task_id: Optional task ID for V2 pipeline
        job_id: Optional job ID for V2 pipeline

    Returns:
        ApiBrowseResult with structured API function references and question answers
    """
    settings = get_settings()
    backend = settings.llm_backend.lower()

    try:
        logger.info(f"Using {backend.upper()} backend for browsing across libraries: {', '.join(libraries)}")

        # Get repos path from settings
        repos_dir = Path(settings.repos_path)

        # Check which libraries exist
        available_libraries = []
        for lib in libraries:
            library_dir = repos_dir / lib.lower()
            if library_dir.exists():
                available_libraries.append(lib)
            else:
                logger.warning(f"Library directory not found: {library_dir}")

        if not available_libraries:
            return ApiBrowseResult(
                success=False,
                library="none",
                queries=questions,
                error=f"No library directories found in {repos_dir}. Requested: {libraries}"
            )

        logger.info(f"Available libraries: {', '.join(available_libraries)}")

        # Collect navigation guide filenames for all available libraries
        nav_guide_files = []
        for lib in available_libraries:
            nav_guide_path = repos_dir / f"{lib.lower()}.md"
            if nav_guide_path.exists():
                nav_guide_files.append(str(nav_guide_path))
                logger.info(f"Found navigation guide for {lib}: {nav_guide_path}")
            else:
                logger.warning(f"Navigation guide not found: {nav_guide_path}")

        # Create output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"api_refs_{timestamp}.json"

        # Determine output directory based on whether task_id/job_id are provided
        if task_id and job_id:
            # V2 pipeline: Save to task-specific searches directory
            output_dir = Path(settings.tools_path) / job_id / task_id / "searches"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / output_filename
            output_path_relative = f"{settings.tools_dir}/{job_id}/{task_id}/searches/{output_filename}"
            logger.info(f"Using V2 task-specific search directory: {output_path}")
        else:
            # V1 pipeline: Save to global searches directory
            output_dir = Path(settings.searches_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / output_filename
            output_path_relative = f"{settings.searchs_dir}/{output_filename}"
            logger.info(f"Using V1 global search directory: {output_path}")

        # Build the browsing prompt (shared across all backends)
        prompt = _build_browse_prompt(available_libraries, questions_file_path, nav_guide_files, settings, output_path_relative)
        logger.debug(f"Browse prompt length: {len(prompt)} characters")
        logger.debug(f"Browse prompt (first 500 chars): {prompt[:500]}")

        timeout_sec = 600
        # Execute backend-specific command
        logger.info(f"Executing {backend.upper()} browse command...")
        logger.info(f"Working directory: {settings.tools_service_path}")
        logger.info(f"Timeout: {timeout_sec} seconds")
        logger.info(f"Expected output file: {output_path}")

        if backend == "codex":
            result = await run_codex_query(
                query=prompt,
                working_dir=settings.tools_service_path,
                timeout=timeout_sec
            )
        elif backend == "claude":
            result = await run_claude_query(
                query=prompt,
                working_dir=settings.tools_service_path,
                timeout=timeout_sec
            )
        else:
            return ApiBrowseResult(
                success=False,
                library=",".join(libraries),
                queries=questions,
                error=f"Unknown LLM backend: {backend}"
            )

        logger.info(f"{backend.upper()} command completed with success={result['success']}")
        logger.debug(f"Result keys: {result.keys()}")

        if result.get("stdout"):
            logger.debug(f"Command stdout (first 1000 chars): {result['stdout'][:1000]}")
        if result.get("stderr"):
            logger.debug(f"Command stderr (first 1000 chars): {result['stderr'][:1000]}")

        if not result["success"]:
            logger.error(f"{backend.upper()} command failed: {result['error']}")
            logger.error(f"Full stdout: {result.get('stdout', 'N/A')}")
            logger.error(f"Full stderr: {result.get('stderr', 'N/A')}")
            return ApiBrowseResult(
                success=False,
                library=",".join(libraries),
                queries=questions,
                file_name='',
                error=result["error"]
            )

        # Check if output file was created
        if not output_path.exists():
            logger.error(f"Output file not created: {output_path}")
            logger.error(f"{backend.upper()} stdout: {result['stdout'][:500]}")
            return ApiBrowseResult(
                success=False,
                library=",".join(libraries),
                queries=questions,
                file_name=str(output_filename),
                error=f"Output file not created by {backend.upper()}: {output_path}"
            )

        # Read the JSON output as raw string
        try:
            with open(output_path, 'r') as f:
                search_results_content = f.read()

            # Validate it's valid JSON
            try:
                json.loads(search_results_content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in output file: {e}")
                return ApiBrowseResult(
                    success=False,
                    library=",".join(libraries),
                    queries=questions,
                    file_name=str(output_filename),
                    error=f"Invalid JSON in output file: {e}"
                )

            logger.info(f"Successfully retrieved search results from {output_path}")
            return ApiBrowseResult(
                success=True,
                library=",".join(libraries),
                queries=questions,
                file_name=str(output_filename),
                search_results=search_results_content,
                output_file=str(output_path)
            )

        except Exception as e:
            logger.error(f"Failed to read output file: {e}")
            return ApiBrowseResult(
                success=False,
                library=",".join(libraries),
                queries=questions,
                file_name=str(output_filename),
                error=f"Failed to read output file: {e}"
            )

    except Exception as e:
        logger.error(f"Exception in {backend.upper()} browsing for libraries {', '.join(libraries)}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return ApiBrowseResult(
            success=False,
            library=",".join(libraries),
            queries=questions,
            error=str(e)
        )


async def execute_llm_query(
    prompt: str,
    job_id: str,
    task_id: str,
    expected_file_name: str
) -> Dict[str, Any]:
    """
    Execute LLM backend with a custom prompt.

    Generic executor that allows agents to provide their own prompts.

    Args:
        prompt: Custom prompt to send to LLM
        job_id: Job identifier
        task_id: Task identifier
        expected_file_name: Name of the file expected to be created (e.g., "tool_name.py")

    Returns:
        Dict with execution result
    """
    settings = get_settings()
    backend = settings.llm_backend.lower()

    try:
        logger.info(f"Executing {backend.upper()} with custom prompt")
        logger.info(f"Job ID: {job_id}, Task ID: {task_id}")
        logger.info(f"Expected file: {expected_file_name}")
        logger.debug(f"Prompt length: {len(prompt)} characters")
        logger.debug(f"Prompt (first 500 chars): {prompt[:500]}")

        # Execute backend-specific command
        logger.info(f"Executing {backend.upper()} query command...")
        logger.info(f"Working directory: {settings.tools_service_path}")
        logger.info(f"Timeout: 300 seconds")

        if backend == "codex":
            result = await run_codex_query(
                query=prompt,
                working_dir=settings.tools_service_path,
                timeout=300
            )
        elif backend == "claude":
            result = await run_claude_query(
                query=prompt,
                working_dir=settings.tools_service_path,
                timeout=300
            )
        else:
            return {
                "success": False,
                "error": f"Unknown LLM backend: {backend}"
            }

        logger.info(f"{backend.upper()} query command completed with success={result['success']}")
        logger.debug(f"Result keys: {result.keys()}")

        if result.get("stdout"):
            logger.info(f"Command stdout (first 1000 chars): {result['stdout'][:1000]}")
        if result.get("stderr"):
            logger.warning(f"Command stderr (first 1000 chars): {result['stderr'][:1000]}")

        # Check if expected file was created
        tools_dir = Path(settings.tools_path) / job_id / task_id
        output_file = tools_dir / expected_file_name
        logger.info(f"Checking for output file: {output_file}")
        logger.info(f"File exists: {output_file.exists()}")

        if result["success"]:
            if output_file.exists():
                logger.info(f"File generated successfully: {output_file}")
                file_size = output_file.stat().st_size
                logger.info(f"File size: {file_size} bytes")
                return {
                    "success": True,
                    "output_file": str(output_file),
                }
            else:
                logger.error(f"{backend.upper()} completed but file not found: {output_file}")
                logger.error(f"Expected directory: {tools_dir}")
                logger.error(f"Directory exists: {tools_dir.exists()}")
                if tools_dir.exists():
                    files_in_dir = list(tools_dir.iterdir())
                    logger.error(f"Files in directory: {[f.name for f in files_in_dir]}")
                logger.error(f"Full stdout: {result.get('stdout', 'N/A')}")
                logger.error(f"Full stderr: {result.get('stderr', 'N/A')}")
                return {
                    "success": False,
                    "error": f"Expected file not created: {output_file}",
                    "stderr": result.get("stderr", "")
                }
        else:
            logger.error(f"{backend.upper()} execution failed: {result['error']}")
            logger.error(f"Full stdout: {result.get('stdout', 'N/A')}")
            logger.error(f"Full stderr: {result.get('stderr', 'N/A')}")
            return {
                "success": False,
                "error": result["error"],
                "stderr": result.get("stderr", "")
            }

    except Exception as e:
        logger.error(f"Exception in {backend.upper()} execution: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }


def _build_browse_prompt(
    libraries: List[str],
    questions_file_path: str,
    nav_guide_files: List[str],
    settings,
    output_path_relative: str
) -> str:
    """
    Build a documentation browsing prompt for LLM backend.

    Args:
        libraries: List of available library names
        questions_file_path: Path to file containing questions from Intake Agent
        nav_guide_files: List of navigation guide file paths
        settings: Application settings
        output_path_relative: Relative path for output file

    Returns:
        Formatted prompt string
    """
    library_dirs = "\n".join([f"  - {lib}: {settings.repos_dir}/{lib.lower()}" for lib in libraries])

    # Build navigation guide file references
    if nav_guide_files:
        nav_guides_text = "\n".join([f"  - {file}" for file in nav_guide_files])
        nav_guide_section = f"""<Navigation Guide Files>
Read these navigation guide files to understand how to navigate each library's documentation:
{nav_guides_text}
</Navigation Guide Files>"""
    else:
        nav_guide_section = "<Navigation Guide Files>\nNo navigation guides available.\n</Navigation Guide Files>"

    return f"""You are tasked with researching chemistry library documentation to answer questions and extract API references.
Questions are located in {questions_file_path}

{nav_guide_section}

<Available Libraries>
{library_dirs}
</Available Libraries>

Your task:
1. For EACH question above, determine which library (if any) is most relevant
2. Search the relevant library's documentation to answer the question
3. Extract relevant API functions that would be needed

Output your findings as JSON with this EXACT structure:
{{
  "question_answers": [
    {{
      "question": "Original question text",
      "type": "api_discovery|method_selection|parameter_tuning|format_handling|error_handling|units",
      "answer": "Detailed answer from documentation",
      "library": "rdkit|ase|pymatgen|pyscf|orca|null",
      "code_example": "Optional code snippet demonstrating the answer"
    }}
  ],
  "api_functions": [
    {{
      "function_name": "module.submodule.function_name",
      "description": "What the function does",
      "input_schema": [
        {{
          "name": "param1",
          "type": "str",
          "description": "Parameter description",
        }}
      ],
      "output_schema": {{
        "type": "float",
        "description": "Output description",
        "units": "Optional units (e.g., 'eV', 'Angstroms')"
      }},
      "examples": [
        {{
          "description": "Example description",
          "code": "from module import func\\nresult = func('value')",
          "source": "documentation"
        }}
      ]
    }}
  ]
}}

Guidelines:
- For API discovery questions: Extract the specific function(s) needed
- For other questions: Answer the question

IMPORTANT:
- Save your output to: {output_path_relative}
- Use valid JSON format
- Answer ALL questions, even if some require searching multiple libraries
- Include complete function signatures with accurate types
- Provide working code examples
"""
