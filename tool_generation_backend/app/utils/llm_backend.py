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
    tool_name = plan.requirement.name

    try:
        logger.info(f"Using {backend.upper()} backend for implementation")

        # Get the actual tools directory path with job_id and task_id subdirectories
        tools_dir = Path(settings.tools_path) / plan.job_id / plan.task_id
        tools_dir.mkdir(parents=True, exist_ok=True)

        # Build the implementation prompt (shared across all backends)
        prompt = _build_implementation_prompt(plan.requirement, plan.api_refs, plan.job_id, plan.task_id, settings)

        # Execute backend-specific command
        if backend == "codex":
            from app.utils.codex_utils import run_codex_query
            result = await run_codex_query(
                query=prompt,
                working_dir=settings.tools_service_path,
                timeout=300
            )
        elif backend == "claude":
            from app.utils.claude_utils import run_claude_query
            result = await run_claude_query(
                query=prompt,
                working_dir=settings.tools_service_path,
                timeout=300
            )
        else:
            return {
                "success": False,
                "tool_name": tool_name,
                "error": f"Unknown LLM backend: {backend}"
            }

        # Check if file was created
        output_file = tools_dir / f"{tool_name}.py"

        if result["success"]:
            if output_file.exists():
                logger.info(f"Tool generated successfully: {output_file}")
                return {
                    "success": True,
                    "tool_name": tool_name,
                    "output_file": str(output_file),
                }
            else:
                logger.warning(f"{backend.upper()} completed but file not found: {output_file}")
                logger.warning(f"stdout: {result['stdout']}")
                logger.warning(f"stderr: {result['stderr']}")
                return {
                    "success": False,
                    "tool_name": tool_name,
                    "error": f"Generated file not found: {output_file}",
                }
        else:
            logger.error(f"{backend.upper()} implementation failed for tool {tool_name}: {result['error']}")
            logger.error(f"stdout: {result['stdout']}")
            logger.error(f"stderr: {result['stderr']}")
            return {
                "success": False,
                "tool_name": tool_name,
                "error": result["error"],
                "stderr": result["stderr"]
            }

    except Exception as e:
        logger.error(f"Exception in {backend.upper()} implementation for tool {tool_name}: {e}")
        return {
            "success": False,
            "tool_name": tool_name,
            "error": str(e)
        }


async def execute_llm_browse(
    libraries: List[str],
    queries: List[str],
    task_id: Optional[str] = None,
    job_id: Optional[str] = None
) -> ApiBrowseResult:
    """
    Execute LLM backend to browse/search documentation across multiple libraries.

    Args:
        libraries: List of available library names (rdkit, ase, pymatgen, pyscf, orca)
        queries: List of search queries (open questions from Intake Agent)
        task_id: Optional task ID for V2 pipeline
        job_id: Optional job ID for V2 pipeline

    Returns:
        ApiBrowseResult with structured API function references and question answers
    """
    settings = get_settings()
    backend = settings.llm_backend.lower()

    # Ensure queries is a list
    if not isinstance(queries, list):
        queries = [queries]

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
                queries=queries,
                error=f"No library directories found in {repos_dir}. Requested: {libraries}"
            )

        logger.info(f"Available libraries: {', '.join(available_libraries)}")

        # Load navigation guides for all available libraries
        nav_guides = []
        for lib in available_libraries:
            nav_guide_path = repos_dir / f"{lib.lower()}.md"
            if nav_guide_path.exists():
                with open(nav_guide_path, 'r') as f:
                    nav_guides.append(f"## {lib.upper()} Navigation Guide\n{f.read()}")
                logger.info(f"Loaded navigation guide for {lib}")
            else:
                logger.warning(f"Navigation guide not found: {nav_guide_path}")

        nav_guide_content = "\n\n".join(nav_guides) if nav_guides else "No navigation guides available."

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
        prompt = _build_browse_prompt(available_libraries, queries, nav_guide_content, settings, output_path_relative)

        # Execute backend-specific command
        if backend == "codex":
            from app.utils.codex_utils import run_codex_query
            result = await run_codex_query(
                query=prompt,
                working_dir=settings.tools_service_path,
                timeout=300
            )
        elif backend == "claude":
            from app.utils.claude_utils import run_claude_query
            result = await run_claude_query(
                query=prompt,
                working_dir=settings.tools_service_path,
                timeout=300
            )
        else:
            return ApiBrowseResult(
                success=False,
                library=",".join(libraries),
                queries=queries,
                error=f"Unknown LLM backend: {backend}"
            )

        if not result["success"]:
            logger.error(f"{backend.upper()} command failed: {result['error']}")
            return ApiBrowseResult(
                success=False,
                library=",".join(libraries),
                queries=queries,
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
                queries=queries,
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
                    queries=queries,
                    file_name=str(output_filename),
                    error=f"Invalid JSON in output file: {e}"
                )

            logger.info(f"Successfully retrieved search results from {output_path}")
            return ApiBrowseResult(
                success=True,
                library=",".join(libraries),
                queries=queries,
                file_name=str(output_filename),
                search_results=search_results_content,
                output_file=str(output_path)
            )

        except Exception as e:
            logger.error(f"Failed to read output file: {e}")
            return ApiBrowseResult(
                success=False,
                library=",".join(libraries),
                queries=queries,
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
            queries=queries,
            error=str(e)
        )


def _build_implementation_prompt(
    requirement: ToolRequirement,
    api_refs: List[str],
    job_id: str,
    task_id: str,
    settings
) -> str:
    """
    Build a detailed implementation prompt for LLM backend.

    Args:
        requirement: Tool requirement specification
        api_refs: List of API reference file paths
        job_id: Job ID for organizing tool files
        task_id: Task ID for organizing tool files
        settings: Application settings

    Returns:
        Formatted prompt string
    """
    tool_name = requirement.name
    tools_dir_relative = f"{settings.tools_dir}/{job_id}/{task_id}"

    prompt_parts = [
        f"Create a Python tool file named {tools_dir_relative}/{tool_name}.py with the following requirement:",
        "",
    ]

    if api_refs:
        prompt_parts.extend([
            "## Api References:",
            "In this file are Api references that may be helpful, inspect this file before implementation",
            *api_refs
        ])

    prompt_parts.extend([
        "## Tool Requirement:",
        f"### Function: {requirement.name}",
        f"**Description:** {requirement.description}",
        "",
        "**Parameters:**"
    ])

    for input_spec in requirement.input_format:
        prompt_parts.extend([
            f"name: {input_spec.name}",
            f"type: {input_spec.type}",
            f"description: {input_spec.description}",
        ])

    # Add return specification
    output = requirement.output_format
    prompt_parts.extend([
        "",
        f"**Output:** {output.type} - {output.description}",
        ""
    ])

    # Add implementation requirements
    prompt_parts.extend([
        "## Implementation Requirements:",
        "1. Include proper type hints and docstrings",
        "2. Handle errors gracefully with try/catch blocks",
        "3. Return results in a structured format with success/error indicators",
        "4. Include chemistry-specific validation where appropriate",
        "5. Use appropriate chemistry libraries (rdkit, ase, pymatgen, pyscf) as needed",
        "6. Tools can read from the file system when parameters specify file paths",
        f"7. Check {settings.tools_dir}/template.txt for a template (if available)",
        "",
        "",
        "Generate the complete, production-ready tool implementation.",
        f"Save the file as {tools_dir_relative}/{tool_name}.py"
    ])

    return "\n".join(prompt_parts)


def _build_browse_prompt(
    libraries: List[str],
    queries: List[str],
    nav_guide_content: str,
    settings,
    output_path_relative: str
) -> str:
    """
    Build a documentation browsing prompt for LLM backend.

    Args:
        libraries: List of available library names
        queries: List of search queries (open questions)
        nav_guide_content: Navigation guide content
        settings: Application settings
        output_path_relative: Relative path for output file

    Returns:
        Formatted prompt string
    """
    queries_text = "\n".join([f"  {i+1}. {q}" for i, q in enumerate(queries)])
    library_dirs = "\n".join([f"  - {lib}: {settings.repos_dir}/{lib.lower()}" for lib in libraries])

    return f"""You are tasked with researching chemistry library documentation to answer questions and extract API references.

<Navigation Guide>
{nav_guide_content}
</Navigation Guide>

<Available Libraries>
{library_dirs}
</Available Libraries>

<Open Questions>
{queries_text}
</Open Questions>

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
          "required": true,
          "default": null
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
- For method selection questions: Compare options and recommend the best approach
- For parameter tuning questions: Provide reasonable default values with justification
- For format handling questions: Show how to parse/convert data formats
- For error handling questions: List common exceptions and how to handle them
- For units questions: Specify the units returned by functions

IMPORTANT:
- Save your output to: {output_path_relative}
- Use valid JSON format
- Answer ALL questions, even if some require searching multiple libraries
- Include complete function signatures with accurate types
- Provide working code examples
"""
