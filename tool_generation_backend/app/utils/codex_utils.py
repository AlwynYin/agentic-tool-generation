"""
Codex CLI command execution utilities.

This module handles only Codex CLI command construction and execution.
All prompting logic is in llm_backend.py.
"""

import subprocess
import asyncio
import logging
import shutil
import os
from typing import Dict, Any

from app.config import get_settings

logger = logging.getLogger(__name__)


def authenticate_codex(api_key: str) -> bool:
    """
    Authenticate Codex CLI with OpenAI API key.

    Args:
        api_key: OpenAI API key

    Returns:
        bool: True if authentication successful, False otherwise
    """
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
            input=api_key,  # Pipe API key via stdin
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


async def run_codex_query(
    query: str,
    working_dir: str,
    timeout: int = 120
) -> Dict[str, Any]:
    """
    Run a Codex query (execute prompt) with proper error handling.

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
        logger.debug(f"Running Codex query in {working_dir}")

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

        # Build Codex command
        cmd = [
            codex_path,
            "exec",
            "--model", settings.openai_model,
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "--cd", working_dir,
            query
        ]

        # Set environment
        env = os.environ.copy()

        # Execute command
        process = await asyncio.create_subprocess_exec(
            *cmd,
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
