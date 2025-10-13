"""
Tool implementations for the chemistry pipeline agents.

These functions are called by agents when they need to perform specific actions
like implementing chemistry tools or updating existing ones.
"""

import logging
import json
from typing import Dict, Any, List, Optional

from agents import function_tool

from app.utils.codex_utils import (
    execute_codex_implement,
    execute_codex_browse
)
from app.models.session import ToolRequirement
from app.models.tool_generation import ToolGenerationResult

logger = logging.getLogger(__name__)


@function_tool
async def implement_tool(requirement: ToolRequirement) -> str:
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

    Returns:
        JSON string containing the result from codex
    """
    try:
        logger.info(f"Implementing chemistry tool: {requirement.name}")
        logger.debug(f"Received input: {requirement}")

        # Use existing codex implementation
        result = await execute_codex_implement(requirement)

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


async def update_chemistry_tool(
    base_tool_name: str,
    base_tool_code: str,
    modification_description: str,
    updated_input_spec: Optional[Dict[str, Any]] = None,
    updated_output_spec: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Update an existing chemistry tool based on modification requirements.

    Args:
        base_tool_name: Name of the existing tool
        base_tool_code: Current code of the tool
        modification_description: Description of required changes
        updated_input_spec: New input specification (if changed)
        updated_output_spec: New output specification (if changed)

    Returns:
        Tool update result
    """
    try:
        logger.info(f"Updating chemistry tool: {base_tool_name}")

        # For now, treat updates as new implementations with modification context
        # In the future, this could be enhanced to do more intelligent code modification

        enhanced_description = f"""
Update the existing tool '{base_tool_name}' with the following changes:
{modification_description}

Current implementation:
```python
{base_tool_code}
```

Please implement the updated version incorporating these changes.
"""

        requirements = [{
            "name": f"{base_tool_name}_updated",
            "description": enhanced_description,
            "params": _convert_input_spec_to_params(updated_input_spec) if updated_input_spec else [],
            "returns": updated_output_spec or {}
        }]

        # Use codex to implement the updated tool
        result = await execute_codex_implement(f"{base_tool_name}_updated", requirements)

        if result["success"]:
            logger.info(f"Successfully updated chemistry tool: {base_tool_name}")

            # Create a ToolRequirement for the updated tool
            tool_requirement = ToolRequirement(
                name=f"{base_tool_name}_updated",
                description=enhanced_description,
                input_format=updated_input_spec or {},
                output_format=updated_output_spec or {},
                required_apis=[]
            )

            result.update({
                "tool_requirement": tool_requirement.model_dump(),
                "individual_tool": True,
                "is_update": True,
                "base_tool_name": base_tool_name
            })

        return result

    except Exception as e:
        logger.error(f"Error updating chemistry tool {base_tool_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "tool_name": base_tool_name,
            "is_update": True
        }


async def browse_chemistry_documentation(
    library: str,
    query: str
) -> Dict[str, Any]:
    """
    Browse chemistry library documentation.

    Args:
        library: Chemistry library name (rdkit, ase, pymatgen, pyscf)
        query: Search query for specific functionality

    Returns:
        Documentation search result
    """
    try:
        logger.info(f"Browsing {library} documentation for: {query}")

        # Use existing codex browse functionality
        result = await execute_codex_browse(library, query)

        logger.info(f"Successfully browsed {library} documentation")
        return result

    except Exception as e:
        logger.error(f"Error browsing {library} documentation: {e}")
        return {
            "success": False,
            "error": str(e),
            "library": library,
            "query": query
        }


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
    "update_chemistry_tool": update_chemistry_tool,
    "browse_chemistry_documentation": browse_chemistry_documentation
}