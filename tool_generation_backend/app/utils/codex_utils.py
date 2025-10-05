"""
Codex utility functions for manual testing and integration.

This module provides wrapper functions for calling Codex CLI commands
with proper session management and error handling.
"""

import subprocess
import asyncio
import logging
import json
import os
from typing import Dict, Any, Optional, List
from pathlib import Path

from app.models import ToolRequirement

logger = logging.getLogger(__name__)


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

        # Authenticate with API key
        logging.info("🔐 Authenticating Codex CLI with OpenAI API key...")
        auth_result = subprocess.run(
            [codex_path, 'login', '--api-key', api_key],
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
        project_root = Path(__file__).parent.parent.parent.parent  # Go up to agent-browser root
        tool_service_dir = project_root / settings.tool_service_dir
        tools_dir = tool_service_dir / settings.tools_dir

        # Ensure directories exist
        tools_dir.mkdir(parents=True, exist_ok=True)

        # Build the implementation prompt
        prompt = _build_implementation_prompt(requirement, settings)

        # Build command - change to tool_service directory first
        cmd = [
            "codex", "exec",
            "--model", "gpt-5",
            "--dangerously-bypass-approvals-and-sandbox",
            "--cd", str(tool_service_dir),
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
    query: str
) -> Dict[str, Any]:
    """
    Execute Codex to browse/search documentation.

    Args:
        library: Library name (rdkit, ase, pymatgen, pyscf)
        query: Search query for documentation

    Returns:
        Dict with browse result
    """
    try:
        # Map library to repository URL
        repo_urls = {
            "rdkit": "https://github.com/rdkit/rdkit",
            "ase": "https://github.com/rosswhitfield/ase",
            "pymatgen": "https://github.com/materialsproject/pymatgen",
            "pyscf": "https://github.com/pyscf/pyscf"
        }

        library_lower = library.lower()
        if library_lower not in repo_urls:
            return {
                "success": False,
                "error": f"Unknown library: {library}",
                "available_libraries": list(repo_urls.keys())
            }

        repo_url = repo_urls[library_lower]

        # Get project root and workspace path
        project_root = Path("/Users/alwyn/Developer/matterlab/agent-browser")
        workspaces_dir = project_root / "workspaces"

        # Create a browsing prompt
        browse_prompt = f"""
        You will be given a repository name, URL, and a search query. Your job is to clone the repository if not exist,
        and search its documentation for information about the query.

        <Repository>
        {library}
        </Repository>
        <url>{repo_url}</url>
        <query>
        {query}
        </query>

        Focus on:
        1. API documentation
        2. Code examples
        3. Function signatures
        4. Usage patterns

        Return the findings in a structured JSON format.
        """

        # Build command for browsing
        cmd = [
            "codex", "exec",
            "--model", "gpt-5",
            "--dangerously-bypass-approvals-and-sandbox",
            "--cd", str(workspaces_dir),
            browse_prompt
        ]

        result = await _run_codex_command(cmd, timeout=300)

        if result["success"]:
            logger.info(f"Documentation browsing completed for library {library}")
            return {
                "success": True,
                "library": library,
                "repo_url": repo_url,
                "query": query,
                "findings": result["stdout"],
                "message": "Browse operation completed"
            }
        else:
            logger.error(f"Codex browsing failed for library {library}: {result['error']}")
            return {
                "success": False,
                "library": library,
                "error": result["error"],
                "stderr": result["stderr"]
            }

    except Exception as e:
        logger.error(f"Exception in Codex browsing for library {library}: {e}")
        return {
            "success": False,
            "library": library,
            "error": str(e)
        }


async def _run_codex_command(cmd: List[str], timeout: int = 120) -> Dict[str, Any]:
    """
    Run a Codex CLI command with proper error handling.

    Args:
        cmd: Command to execute
        timeout: Command timeout in seconds

    Returns:
        Dict with command result
    """
    import os
    try:
        logger.debug(f"Running Codex command: {' '.join(cmd)}")

        # Check if codex executable exists
        import shutil
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


async def test_codex_implementation():
    """
    Test function for codex implementation.

    Creates a simple molecular weight calculator tool for testing.
    """
    print("Testing codex implementation...")

    # Define test requirements
    test_requirements = [
        {
            "name": "calculate_molecular_weight",
            "description": "Calculate molecular weight from SMILES string using RDKit",
            "params": [
                {
                    "name": "smiles",
                    "type": "str",
                    "description": "SMILES string representing the molecule"
                },
                {
                    "name": "precision",
                    "type": "int",
                    "description": "Number of decimal places for result (default: 2)"
                }
            ],
            "returns": {
                "type": "Dict[str, Any]",
                "description": "Dictionary containing molecular weight and metadata"
            }
        }
    ]

    # Test implementation
    try:
        result = await execute_codex_implement("test_molecular_tools", test_requirements)

        print(f"Implementation result: {result['success']}")
        if result["success"]:
            print(f"Tool created at: {result['output_file']}")
            print(f"Stdout: {result['stdout'][:200]}...")  # First 200 chars
        else:
            print(f"Error: {result['error']}")
            if "stderr" in result:
                print(f"Stderr: {result['stderr']}")

        return result

    except Exception as e:
        print(f"Exception during test: {e}")
        return {"success": False, "error": str(e)}


async def test_codex_browse():
    """
    Test function for codex browsing.

    Tests documentation browsing for RDKit molecular weight functions.
    """
    print("Testing codex browsing...")

    try:
        result = await execute_codex_browse("rdkit", "molecular weight calculation")

        print(f"Browse result: {result['success']}")
        if result["success"]:
            print(f"Library: {result['library']}")
            print(f"Query: {result['query']}")
            print(f"Findings: {result['findings'][:200]}...")  # First 200 chars
        else:
            print(f"Error: {result['error']}")

        return result

    except Exception as e:
        print(f"Exception during browse test: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import asyncio

    async def run_tests():
        """Run all codex tests."""
        print("=== Codex Utils Test Suite ===\n")

        # Test implementation
        print("2. Testing tool implementation:")
        impl_result = await test_codex_implementation()
        print()

        # Summary
        print("=== Test Summary ===")
        print(f"Implementation test: {'PASS' if impl_result['success'] else 'FAIL'}")

    # Run the tests
    asyncio.run(run_tests())