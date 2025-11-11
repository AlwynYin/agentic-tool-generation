"""
Utility for parsing function signatures and docstrings to extract schemas.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple

from app.models.specs import ParameterSpec, OutputSpec

logger = logging.getLogger(__name__)


def parse_type_annotation(type_str: str) -> str:
    """
    Parse Python type annotation to simplified string.

    Args:
        type_str: Type annotation string (e.g., "str", "List[float]", "Optional[Dict[str, Any]]")

    Returns:
        str: Simplified type string
    """
    # Remove Optional wrapper if present
    type_str = type_str.strip()

    # Handle Optional[X] -> X (we'll track optional separately)
    optional_match = re.match(r'Optional\[(.*)\]', type_str)
    if optional_match:
        type_str = optional_match.group(1).strip()

    # Handle Union types - take first type
    union_match = re.match(r'Union\[(.*?),', type_str)
    if union_match:
        type_str = union_match.group(1).strip()

    return type_str


def parse_function_signature(signature: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Parse function signature to extract parameters and return type.

    Args:
        signature: Function signature string (e.g., "def func(a: str, b: int = 5) -> float:")

    Returns:
        Tuple[List[Dict], str]: (parameters list, return type)
    """
    try:
        # Extract function name and parameters
        # Pattern: def function_name(params) -> return_type:
        pattern = r'def\s+\w+\s*\((.*?)\)\s*(?:->\s*(.+?))?\s*:'
        match = re.search(pattern, signature, re.DOTALL)

        if not match:
            logger.warning(f"Could not parse signature: {signature}")
            return [], "Any"

        params_str = match.group(1).strip()
        return_type = match.group(2).strip() if match.group(2) else "Any"

        # Parse parameters
        parameters = []

        if params_str:
            # Split by comma, but respect nested brackets
            param_parts = []
            current = ""
            depth = 0

            for char in params_str:
                if char in '[({':
                    depth += 1
                elif char in '])}':
                    depth -= 1
                elif char == ',' and depth == 0:
                    param_parts.append(current.strip())
                    current = ""
                    continue
                current += char

            if current.strip():
                param_parts.append(current.strip())

            # Parse each parameter
            for param_str in param_parts:
                param_info = parse_parameter(param_str)
                if param_info:
                    parameters.append(param_info)

        return parameters, return_type

    except Exception as e:
        logger.error(f"Error parsing signature: {e}")
        return [], "Any"


def parse_parameter(param_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single parameter string.

    Args:
        param_str: Parameter string (e.g., "name: str", "count: int = 5")

    Returns:
        Optional[Dict]: Parameter info or None if parsing fails
    """
    try:
        # Pattern: name: type or name: type = default
        has_default = '=' in param_str

        if has_default:
            # Split by '=' to separate type and default
            param_part, default_part = param_str.split('=', 1)
            default_value = default_part.strip()
        else:
            param_part = param_str
            default_value = None

        # Parse name and type
        if ':' in param_part:
            name, type_str = param_part.split(':', 1)
            name = name.strip()
            type_str = type_str.strip()
        else:
            # No type annotation
            name = param_part.strip()
            type_str = "Any"

        # Check if Optional
        is_optional = 'Optional' in type_str or default_value is not None

        # Parse type
        parsed_type = parse_type_annotation(type_str)

        return {
            "name": name,
            "type": parsed_type,
            "default": default_value,
            "required": not is_optional
        }

    except Exception as e:
        logger.error(f"Error parsing parameter '{param_str}': {e}")
        return None


def parse_docstring_for_descriptions(docstring: str) -> Dict[str, str]:
    """
    Parse docstring to extract parameter and return descriptions.

    Args:
        docstring: Function docstring

    Returns:
        Dict[str, str]: Mapping of parameter names to descriptions, plus "return" key
    """
    descriptions = {}

    try:
        # Extract Args section
        args_match = re.search(r'Args?:(.*?)(?=Returns?:|Raises?:|Examples?:|Notes?:|$)', docstring, re.DOTALL | re.IGNORECASE)
        if args_match:
            args_section = args_match.group(1)

            # Parse each parameter line: "    param_name: description"
            param_pattern = r'^\s*(\w+):\s*(.+?)(?=^\s*\w+:|$)'
            for match in re.finditer(param_pattern, args_section, re.MULTILINE | re.DOTALL):
                param_name = match.group(1).strip()
                description = match.group(2).strip()
                # Clean up description (remove extra whitespace)
                description = re.sub(r'\s+', ' ', description)
                descriptions[param_name] = description

        # Extract Returns section
        returns_match = re.search(r'Returns?:(.*?)(?=Raises?:|Examples?:|Notes?:|$)', docstring, re.DOTALL | re.IGNORECASE)
        if returns_match:
            returns_text = returns_match.group(1).strip()
            # Clean up
            returns_text = re.sub(r'\s+', ' ', returns_text)
            descriptions["return"] = returns_text

    except Exception as e:
        logger.error(f"Error parsing docstring: {e}")

    return descriptions


def signature_to_input_schema(signature: str, docstring: str) -> List[ParameterSpec]:
    """
    Convert function signature and docstring to input schema.

    Args:
        signature: Function signature
        docstring: Function docstring

    Returns:
        List[ParameterSpec]: Input schema
    """
    parameters, _ = parse_function_signature(signature)
    descriptions = parse_docstring_for_descriptions(docstring)

    input_schema = []
    for param in parameters:
        # Build description with additional info
        description = descriptions.get(param["name"], "")

        # Add default value info to description if present
        if param.get("default"):
            description = f"{description} (default: {param['default']})" if description else f"Default: {param['default']}"

        # Add optional/required info to description
        if not param.get("required", True):
            description = f"[Optional] {description}" if description else "[Optional]"

        param_spec = ParameterSpec(
            name=param["name"],
            type=param["type"],
            description=description.strip()
        )
        input_schema.append(param_spec)

    return input_schema


def signature_to_output_schema(signature: str, docstring: str) -> OutputSpec:
    """
    Convert function signature and docstring to output schema.

    Args:
        signature: Function signature
        docstring: Function docstring

    Returns:
        OutputSpec: Output schema
    """
    _, return_type = parse_function_signature(signature)
    descriptions = parse_docstring_for_descriptions(docstring)

    return_description = descriptions.get("return", "")

    # Note: OutputSpec model doesn't have units field, so we include it in description
    return OutputSpec(
        type=return_type,
        description=return_description
    )
