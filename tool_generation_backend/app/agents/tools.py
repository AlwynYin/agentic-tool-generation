"""
Tool implementations for the chemistry pipeline agents.

These functions are called by agents when they need to perform specific actions
like implementing chemistry tools or updating existing ones.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from contextvars import ContextVar

from agents import function_tool

from app.utils.codex_utils import (
    execute_codex_implement,
    execute_codex_browse
)
from app.models.session import ToolRequirement, ImplementationPlan
from app.models.tool_generation import ToolGenerationResult

logger = logging.getLogger(__name__)

# Context variable for passing job_id through the agent execution
# This is set by the pipeline before running the agent
_job_id_context: ContextVar[Optional[str]] = ContextVar('job_id', default=None)


@function_tool
async def implement_tool(requirement: ToolRequirement, api_refs: Optional[List[str]] = None) -> str:
    """
    Implement a computation tool using Codex.

    Args:
        requirement (ToolRequirement): requirements of the tool function in a ToolRequirement Object, containing:
        - name: Function name
        - description: description of the function
        - input_format: a list of input specifications, in ParameterSpec Objects, containing:
            - name: parameter name
            - type: a string specifying the type
            - description: a string
        - output_format: a list of output specifications, in ParameterSpec Objects.
        api_refs (List[str]): List of API reference file paths to use for implementation (default: [])

    Returns:
        JSON string containing the result from codex
    """
    try:
        logger.info(f"Implementing chemistry tool: {requirement.name}")
        logger.debug(f"Received input: {requirement}")
        logger.debug(f"API references: {api_refs}")

        # Get job_id from context (set by pipeline)
        job_id = _job_id_context.get()
        if not job_id:
            raise ValueError("job_id not found in context. Pipeline must set job_id before running agent.")

        # Create implementation plan
        plan = ImplementationPlan(
            job_id=job_id,
            requirement=requirement,
            api_refs=api_refs or []
        )

        # Use existing codex implementation
        result = await execute_codex_implement(plan)

        if result["success"]:
            logger.info(f"Successfully implemented chemistry tool: {requirement.name}")

        return json.dumps({
            "success": True,
            "tool_name": requirement.name,
        })

    except Exception as e:
        logger.error(f"Error implementing chemistry tool {requirement.name}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "tool_name": requirement.name
        })


@function_tool
async def browse_documentation(library: str, query: str) -> str:
    """
    Browse chemistry library documentation to find API references and examples.

    Use this tool when you need to understand how to use specific functions from chemistry libraries
    before implementing a tool. This helps you find the correct API usage patterns.

    Args:
        library (str): Chemistry library name. Must be one of: rdkit, ase, pymatgen, pyscf
        query (str): Search query describing what functionality you're looking for.
                    Examples: "calculate molecular descriptors", "optimize geometry", "parse SMILES"

    Returns:
        JSON string containing the search results with API documentation and examples
    """
    try:
        logger.info(f"Browsing {library} documentation for: {query}")

        # Use existing codex browse functionality
        result = await execute_codex_browse(library, query)

        logger.info(f"Successfully browsed {library} documentation")

        return json.dumps({
            "success": True,
            "library": library,
            "query": query,
            "result": result
        })

    except Exception as e:
        logger.error(f"Error browsing {library} documentation: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "library": library,
            "query": query
        })


def _convert_input_spec_to_params(input_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert JSON schema input specification to parameter list format.

    Args:
        input_spec: JSON schema for inputs

    Returns:
        List of parameter specifications
    """
    params = []

    if not input_spec or "properties" not in input_spec:
        return params

    properties = input_spec.get("properties", {})
    required = input_spec.get("required", [])

    for param_name, param_info in properties.items():
        param = {
            "name": param_name,
            "type": param_info.get("type", "string"),
            "description": param_info.get("description", ""),
            "required": param_name in required
        }

        # Add additional constraints if present
        if "enum" in param_info:
            param["enum"] = param_info["enum"]
        if "default" in param_info:
            param["default"] = param_info["default"]

        params.append(param)

    return params


# Tool registry for the pipeline agents
PIPELINE_TOOLS = {
    "implement_chemistry_tool": implement_tool,
    "browse_chemistry_documentation": browse_documentation
}