"""
Utility for parsing generated Python code to extract function signatures and docstrings.
"""

import ast
import logging
from typing import Optional, Tuple, List

from app.models.specs import ParameterSpec, OutputSpec
from app.utils.signature_parser import (
    parse_docstring_for_descriptions,
    parse_type_annotation
)

logger = logging.getLogger(__name__)


def extract_function_from_code(code: str) -> Optional[ast.FunctionDef]:
    """
    Extract the main function definition from generated code.

    Args:
        code: Python source code

    Returns:
        Optional[ast.FunctionDef]: The function AST node, or None if not found
    """
    try:
        tree = ast.parse(code)

        # Find all function definitions
        functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

        if not functions:
            logger.warning("No function definitions found in code")
            return None

        # Return the first non-private function (not starting with _)
        for func in functions:
            if not func.name.startswith('_'):
                return func

        # If all are private, return the first one
        return functions[0]

    except SyntaxError as e:
        logger.error(f"Syntax error parsing code: {e}")
        return None
    except Exception as e:
        logger.error(f"Error extracting function from code: {e}")
        return None


def ast_annotation_to_string(annotation) -> str:
    """
    Convert AST annotation node to string representation.

    Args:
        annotation: AST annotation node

    Returns:
        str: String representation of the type
    """
    if annotation is None:
        return "Any"

    try:
        # Handle simple names (str, int, float, etc.)
        if isinstance(annotation, ast.Name):
            return annotation.id

        # Handle subscripts (List[int], Dict[str, float], etc.)
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name):
                base_type = annotation.value.id

                # Handle the slice (the part in brackets)
                if isinstance(annotation.slice, ast.Name):
                    inner = annotation.slice.id
                    return f"{base_type}[{inner}]"
                elif isinstance(annotation.slice, ast.Tuple):
                    inners = [ast_annotation_to_string(elt) for elt in annotation.slice.elts]
                    return f"{base_type}[{', '.join(inners)}]"
                else:
                    inner = ast_annotation_to_string(annotation.slice)
                    return f"{base_type}[{inner}]"

        # Handle constants (for defaults)
        if isinstance(annotation, ast.Constant):
            return repr(annotation.value)

        # Fallback: try to unparse if available (Python 3.9+)
        if hasattr(ast, 'unparse'):
            return ast.unparse(annotation)

        return "Any"

    except Exception as e:
        logger.error(f"Error converting annotation to string: {e}")
        return "Any"


def parse_function_from_code(code: str) -> Tuple[List[ParameterSpec], OutputSpec, str]:
    """
    Parse function signature and docstring from generated code.

    Args:
        code: Python source code

    Returns:
        Tuple[List[ParameterSpec], OutputSpec, str]: (input_schema, output_schema, function_name)
    """
    try:
        func = extract_function_from_code(code)

        if not func:
            logger.warning("Could not extract function from code")
            return [], OutputSpec(type="Any", description=""), "unknown"

        function_name = func.name
        docstring = ast.get_docstring(func) or ""

        # Parse docstring for descriptions
        descriptions = parse_docstring_for_descriptions(docstring)

        # Parse parameters
        input_schema = []
        for arg in func.args.args:
            param_name = arg.arg

            # Get type annotation
            type_str = ast_annotation_to_string(arg.annotation) if arg.annotation else "Any"
            type_str = parse_type_annotation(type_str)

            # Get description from docstring
            description = descriptions.get(param_name, "")

            # Check if parameter has default value
            num_defaults = len(func.args.defaults)
            num_args = len(func.args.args)
            arg_index = func.args.args.index(arg)

            has_default = arg_index >= (num_args - num_defaults)

            if has_default:
                default_index = arg_index - (num_args - num_defaults)
                default_value = ast_annotation_to_string(func.args.defaults[default_index])
                description = f"[Optional] {description} (default: {default_value})".strip()

            param_spec = ParameterSpec(
                name=param_name,
                type=type_str,
                description=description
            )
            input_schema.append(param_spec)

        # Parse return type
        return_type = ast_annotation_to_string(func.returns) if func.returns else "Any"
        return_description = descriptions.get("return", "")

        output_schema = OutputSpec(
            type=return_type,
            description=return_description
        )

        return input_schema, output_schema, function_name

    except Exception as e:
        logger.error(f"Error parsing function from code: {e}")
        return [], OutputSpec(type="Any", description=""), "unknown"


def extract_description_from_code(code: str) -> str:
    """
    Extract the first line of the docstring as description.

    Args:
        code: Python source code

    Returns:
        str: First line of docstring, or empty string
    """
    try:
        func = extract_function_from_code(code)
        if not func:
            return ""

        docstring = ast.get_docstring(func)
        if not docstring:
            return ""

        # Return first non-empty line
        lines = docstring.split('\n')
        for line in lines:
            line = line.strip()
            if line:
                return line

        return ""

    except Exception as e:
        logger.error(f"Error extracting description from code: {e}")
        return ""
