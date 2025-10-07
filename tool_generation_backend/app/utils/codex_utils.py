"""
Codex utility functions for manual testing and integration.

This module provides wrapper functions for calling Codex CLI commands
with proper session management and error handling.
"""

import subprocess
import asyncio
import logging
import json
import shutil
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from app.config import get_settings
from app.models import ToolRequirement
from app.models.session import ParameterSpec, OutputSpec
from app.models.api_reference import ApiBrowseResult, ApiFunction, ApiExample

logger = logging.getLogger(__name__)
settings = get_settings()


def authenticate_codex(api_key: str) -> bool:
    """Authenticate Codex CLI with OpenAI API key."""
    try:
        # Check if codex is available
        which_result = subprocess.run(['which', 'codex'], capture_output=True, text=True)
        if which_result.returncode != 0:
            logging.error("❌ Codex CLI not found in PATH")
            return False

        codex_path = which_result.stdout.strip()
        logging.info(f"✅ Found Codex CLI at: {codex_path}")

        # Authenticate with API key (pipe it to stdin)
        logging.info("🔐 Authenticating Codex CLI with OpenAI API key...")
        auth_result = subprocess.run(
            [codex_path, 'login', '--with-api-key'],
            input=api_key,
            capture_output=True,
            text=True,
            timeout=30
        )

        if auth_result.returncode == 0:
            logging.info("✅ Codex CLI authenticated successfully")
            return True
        else:
            logging.error("❌ Codex authentication failed")
            if auth_result.stderr:
                logging.error(f"Error: {auth_result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logging.error("❌ Codex authentication timed out")
        return False
    except Exception as e:
        logging.error(f"❌ Codex authentication error: {e}")
        return False


async def execute_codex_implement(requirement: ToolRequirement) -> Dict[str, Any]:
    """
    Execute Codex to implement/generate code in tool_service directory.

    Args:
        requirement: requirement of the tool

    Returns:
        Dict with implementation result
    """
    tool_name = requirement.name

    try:
        # Get configurable paths from settings
        from app.config import get_settings
        settings = get_settings()

        # Get project root dynamically - go up 4 levels to reach agent-browser/
        tools_dir = Path(settings.tool_service_dir)

        # Ensure directories exist
        tools_dir.mkdir(parents=True, exist_ok=True)

        # Build the implementation prompt
        prompt = _build_implementation_prompt(requirement, settings)

        # Build command - change to tool_service directory first
        cmd = [
            "codex", "exec",
            "--model", "gpt-5",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "--cd", str(tools_dir),
            prompt
        ]

        result = await _run_codex_command(cmd, timeout=300)

        # Expected output file
        output_file = tools_dir / f"{tool_name}.py"

        if result["success"]:
            # Check if file was actually created
            if output_file.exists():
                logger.info(f"Tool generated successfully: {output_file}")
                return {
                    "success": True,
                    "tool_name": tool_name,
                    "output_file": str(output_file),
                }
            else:
                logger.warning(f"Codex completed but file not found: {output_file}")
                logger.warning(f"stdout: {result['stdout']}")
                logger.warning(f"stderr: {result['stderr']}")
                return {
                    "success": False,
                    "tool_name": tool_name,
                    "error": f"Generated file not found: {output_file}",
                }
        else:
            logger.error(f"Codex implementation failed for tool {tool_name}: {result['error']}")
            logger.error(f"stdout: {result['stdout']}")
            logger.error(f"stderr: {result['stderr']}")
            return {
                "success": False,
                "tool_name": tool_name,
                "error": result["error"],
                "stderr": result["stderr"]
            }

    except Exception as e:
        logger.error(f"Exception in Codex implementation for tool {tool_name}: {e}")
        return {
            "success": False,
            "tool_name": tool_name,
            "error": str(e)
        }


async def execute_codex_browse(
    library: str,
    queries: List[str]
):
    """
    Execute Codex to browse/search documentation and extract API references.

    Args:
        library: Library name (rdkit, ase, pymatgen, pyscf)
        queries: List of search queries for API documentation

    Returns:
        ApiBrowseResult with structured API function references
    """

    try:
        # Get repos path from settings
        repos_dir = Path(settings.repos_path)
        library_lower = library.lower()

        # Check if library directory exists
        library_dir = repos_dir / library_lower
        if not library_dir.exists():
            logger.error(f"Library directory not found: {library_dir}")
            return ApiBrowseResult(
                success=False,
                library=library,
                queries=queries,
                error=f"Library '{library}' not found in {repos_dir}. Available: {[d.name for d in repos_dir.iterdir() if d.is_dir()]}"
            )

        # Check if navigation guide exists
        nav_guide_path = repos_dir / f"{library_lower}.md"
        if not nav_guide_path.exists():
            logger.warning(f"Navigation guide not found: {nav_guide_path}")
            nav_guide_content = "No navigation guide available."
        else:
            with open(nav_guide_path, 'r') as f:
                nav_guide_content = f.read()
            logger.info(f"Loaded navigation guide from {nav_guide_path}")

        # Create output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{library_lower}_api_refs_{timestamp}.json"
        output_path = repos_dir / output_filename

        # Build the browsing prompt with structured output requirements
        queries_text = "\n".join([f"  - {q}" for q in queries])

        browse_prompt = f"""You are tasked with extracting API function references from the {library} library documentation.

<Navigation Guide>
{nav_guide_content}
</Navigation Guide>

<Repository Location>
{library_dir}
</Repository Location>

<Queries>
{queries_text}
</Queries>

Your task:
1. Search the repository's documentation for API functions related to each query
2. For each relevant function, extract:
   - Full function name (e.g., "rdkit.Chem.Descriptors.MolWt")
   - Description
   - Input parameters (name, type, description)
   - Output type and description
   - 2-3 simple usage examples with code and expected output

3. Output the results as a JSON array with this exact structure:
[
  {{
    "function_name": "module.submodule.function_name",
    "description": "What the function does",
    "input_schema": [
      {{
        "name": "param1",
        "type": "str",
        "description": "Parameter description"
      }}
    ],
    "output_schema": {{
      "type": "float",
      "description": "Output description"
    }},
    "examples": [
      {{
        "description": "Example description",
        "code": "from module import func\\nresult = func('value')",
        "expected_output": "Expected result description"
      }}
    ]
  }}
]

IMPORTANT:
- Save your output to: {output_path}
- Use valid JSON format
- Include complete function signatures with accurate types
- Provide working code examples
"""

        # Build command for browsing
        cmd = [
            "codex", "exec",
            "--model", "gpt-5",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "--cd", str(repos_dir),
            browse_prompt
        ]

        logger.info(f"Starting Codex browse for library '{library}' with {len(queries)} queries")
        result = await _run_codex_command(cmd, timeout=300)

        if not result["success"]:
            logger.error(f"Codex command failed: {result['error']}")
            return ApiBrowseResult(
                success=False,
                library=library,
                queries=queries,
                error=result["error"]
            )

        # Check if output file was created
        if not output_path.exists():
            logger.error(f"Output file not created: {output_path}")
            logger.error(f"Codex stdout: {result['stdout'][:500]}")
            return ApiBrowseResult(
                success=False,
                library=library,
                queries=queries,
                error=f"Output file not created by Codex: {output_path}"
            )

        # Parse the JSON output
        try:
            with open(output_path, 'r') as f:
                api_functions_data = json.load(f)

            # Validate and convert to Pydantic models
            api_functions = []
            for func_data in api_functions_data:
                try:
                    # Convert examples if present
                    examples = []
                    for ex in func_data.get('examples', []):
                        examples.append(ApiExample(**ex))

                    api_func = ApiFunction(
                        function_name=func_data['function_name'],
                        description=func_data['description'],
                        input_schema=[ParameterSpec(**p) for p in func_data.get('input_schema', [])],
                        output_schema=OutputSpec(**func_data['output_schema']),
                        examples=examples
                    )
                    api_functions.append(api_func)
                except Exception as e:
                    logger.warning(f"Failed to parse API function: {e}")
                    logger.warning(f"Data: {func_data}")
                    continue

            logger.info(f"Successfully extracted {len(api_functions)} API functions")
            return ApiBrowseResult(
                success=True,
                library=library,
                queries=queries,
                api_functions=api_functions,
                output_file=str(output_path)
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON output: {e}")
            with open(output_path, 'r') as f:
                content = f.read()
            logger.error(f"File content: {content[:500]}")
            return ApiBrowseResult(
                success=False,
                library=library,
                queries=queries,
                error=f"Invalid JSON in output file: {e}"
            )

    except Exception as e:
        logger.error(f"Exception in Codex browsing for library {library}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return ApiBrowseResult(
            success=False,
            library=library,
            queries=queries,
            error=str(e)
        )


async def _run_codex_command(cmd: List[str], timeout: int = 120) -> Dict[str, Any]:
    """
    Run a Codex CLI command with proper error handling.

    Args:
        cmd: Command to execute
        timeout: Command timeout in seconds

    Returns:
        Dict with command result
    """
    try:
        logger.debug(f"Running Codex command: {' '.join(cmd)}")

        # Check if codex executable exists
        codex_path = shutil.which('codex')
        if not codex_path:
            logger.error("❌ Codex executable not found in PATH")
            # Try common locations
            common_paths = ['/usr/local/bin/codex', '/usr/bin/codex', '/bin/codex']
            for path in common_paths:
                if os.path.exists(path):
                    codex_path = path
                    break
            else:
                return {
                    "success": False,
                    "error": "Codex executable not found in PATH or common locations",
                    "stdout": "",
                    "stderr": ""
                }

        # Set OPENAI_API_KEY environment variable if not set
        env = os.environ.copy()

        # Replace 'codex' with full path in command
        cmd_with_path = [codex_path] + cmd[1:] if cmd[0] == 'codex' else cmd

        process = await asyncio.create_subprocess_exec(
            *cmd_with_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.terminate()
            await process.wait()
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds",
                "stdout": "",
                "stderr": ""
            }

        stdout_str = stdout.decode('utf-8') if stdout else ""
        stderr_str = stderr.decode('utf-8') if stderr else ""

        if process.returncode == 0:
            logger.info("✅ Codex command completed successfully")
            return {
                "success": True,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "returncode": process.returncode
            }
        else:
            logger.error(f"❌ Codex command failed with return code {process.returncode}")
            if stderr_str:
                logger.error(f"Error: {stderr_str[:200]}...")
            return {
                "success": False,
                "error": f"Command failed with return code {process.returncode}",
                "stdout": stdout_str,
                "stderr": stderr_str,
                "returncode": process.returncode
            }

    except Exception as e:
        logger.error(f"❌ Exception running Codex command: {e}")
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": ""
        }


def _build_implementation_prompt(requirement: ToolRequirement, settings) -> str:
    """
    Build a detailed implementation prompt for Codex.

    Args:
        tool_name: Name of the tool to implement
        requirements: List of requirement specifications

    Returns:
        Formatted prompt string
    """
    # Start building the prompt
    tool_name = requirement.name
    prompt_parts = [
        f"Create a Python tool file named {settings.tools_dir}/{tool_name}.py with the following requirement:",
        "",
        "## Tool Requirement:",
        f"### Function: {requirement.name}",
        f"**Description:** {requirement.description}",
        "",
        "**Parameters:**"
    ]
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
        f"6. Check {settings.tools_dir}/template.txt for a template"
        "",
        "",
        "Generate the complete, production-ready tool implementation.",
        f"Save the file as {settings.tools_dir}/{tool_name}.py"
    ])

    return "\n".join(prompt_parts)
