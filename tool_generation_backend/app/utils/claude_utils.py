"""
Claude Code CLI command execution utilities.

This module handles only Claude Code CLI command construction and execution.
All prompting logic is in llm_backend.py.
"""

import subprocess
import asyncio
import logging
import shutil
import os
from typing import Dict, Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


def authenticate_claude(api_key: Optional[str] = None) -> bool:
    """
    Authenticate Claude Code CLI with Anthropic API key (optional).

    Args:
        api_key: Anthropic API key (optional, uses claude login if not provided)

    Returns:
        bool: True if authentication successful, False otherwise
    """
    if api_key is None:
        return False
    logger.info(f"Claude API key is present")
    return True


async def run_claude_query(
    query: str,
    working_dir: str,
    timeout: int = 120
) -> Dict[str, Any]:
    """
    Run a Claude Code query (execute prompt) with proper error handling.

    Args:
        query: The prompt/query to execute
        working_dir: Working directory for command execution
        timeout: Command timeout in seconds

    Returns:
        Dict with command result containing:
            - success: bool
            - stdout: str
            - stderr: str
            - returncode: int (if success/failure)
            - error: str (if failure)
    """
    settings = get_settings()

    try:
        logger.debug(f"Running Claude Code query in {working_dir}")

        # Check if claude executable exists
        claude_path = shutil.which('claude')
        if not claude_path:
            logger.error("❌ Claude Code executable not found in PATH")
            # Try common locations
            common_paths = ['/usr/local/bin/claude', '/usr/bin/claude', '/bin/claude']
            for path in common_paths:
                if os.path.exists(path):
                    claude_path = path
                    break
            else:
                return {
                    "success": False,
                    "error": "Claude Code executable not found in PATH or common locations",
                    "stdout": "",
                    "stderr": ""
                }

        # Build Claude Code command
        cmd = [
            claude_path,
            "--dangerously-skip-permissions",
            "-p", query
        ]

        # Set ANTHROPIC_API_KEY environment variable if configured
        env = os.environ.copy()
        if settings.anthropic_api_key:
            env['ANTHROPIC_API_KEY'] = settings.anthropic_api_key

        # Execute command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,  # Close stdin to prevent hanging
            cwd=working_dir,
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
            logger.info("✅ Claude Code command completed successfully")
            return {
                "success": True,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "returncode": process.returncode
            }
        else:
            logger.error(f"❌ Claude Code command failed with return code {process.returncode}")
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
        logger.error(f"❌ Exception running Claude Code command: {e}")
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": ""
        }
