"""
Agent tools for repository registration.

These functions are called by the RepositoryRegistrationAgent when it needs to:
1. Search for repository information
2. Download repositories
3. Generate navigation guides
"""

import asyncio
import logging
import json

from typing import List
from agents import function_tool

from app.utils.repository_utils import (
    git_clone,
    execute_codex_nav_guide,
    get_repo_path,
    get_guide_path
)

logger = logging.getLogger(__name__)


# Navigation guide generation prompt (hardcoded as requested)
NAVIGATION_GUIDE_PROMPT = """You are a documentation analyst. Your task is to create a comprehensive navigation guide for a software package's documentation.

Analyze the repository structure and create a navigation guide that includes:

1. **Doc Roots & Toolchain:**
   - Primary documentation directories
   - Documentation build toolchain (Sphinx, MkDocs, etc.)
   - Configuration files (conf.py, mkdocs.yml, etc.)
   - Entry point files (index.rst, README.md, etc.)
   - Build instructions and output location

2. **Start-Here Pages:**
   - Main entry points for users
   - Getting started guides
   - Installation instructions
   - Quick reference pages

3. **Navigation Map:**
   - Overall documentation structure
   - How different sections are organized
   - Table of contents structure
   - Cross-references between sections

4. **API Reference:**
   - Location of API documentation
   - Auto-generated docs (autodoc markers)
   - Source code fallback locations
   - Module/class/function organization

5. **Examples & Data:**
   - Example code locations
   - Jupyter notebooks
   - Tutorial files
   - Sample data files

6. **CLI Search Cheatsheet:**
   - Useful grep/rg commands for finding:
     - Table of contents (toctree)
     - API stubs (autoclass, autofunction, automodule)
     - Narrative content
     - Source code definitions
   - File patterns to include/exclude

7. **Versioning / Tags:**
   - Documentation versioning approach
   - Release notes location
   - Tag/branch structure
   - How to access different versions

Format the guide as a clean, readable Markdown document with clear sections and examples.
Focus on making it easy for someone to quickly find specific information in the documentation.
"""


@function_tool
async def git_clone_repository(
    package_name: str,
    repo_url: str,
    branch: str = "main"
) -> str:
    """
    Clone a git repository for a package. Notice that this function clones with depth=1 to save space

    Args:
        package_name (str): Package name (used for destination directory)
        repo_url (str): Git repository URL (e.g., https://github.com/rdkit/rdkit.git)
        branch (str, optional): Git branch to clone (default: "main")

    Returns:
        JSON string with clone result:
        {
            "success": bool,
            "repo_path": str (path to cloned repository),
            "error": str (error message if clone failed)
        }
    """
    try:
        logger.info(f"Cloning git repository for {package_name}")
        logger.info(f"URL: {repo_url}, Branch: {branch}")

        dest_path = get_repo_path(package_name)

        # Git clone with branch
        result = await git_clone(repo_url, branch, dest_path)

        if result["success"]:
            return json.dumps({
                "success": True,
                "repo_path": str(dest_path),
                "message": f"Successfully cloned repository to {dest_path}"
            })
        else:
            return json.dumps({
                "success": False,
                "error": result["error"]
            })

    except Exception as e:
        logger.error(f"Error cloning repository for {package_name}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })


@function_tool
async def wget_download_docs(
    package_name: str,
    wget_command: str
) -> str:
    """
    Download documentation using a custom wget command.

    The agent should construct the full wget command to download documentation.
    The destination will automatically be set to the package's repository directory.

    Args:
        package_name (str): Package name (used for destination directory)
        wget_command (str): Full wget command to execute (e.g., "wget -r -np -nH --cut-dirs=3 https://example.com/docs/")
                           Do NOT include the destination path (-P flag), it will be added automatically.

    Returns:
        JSON string with download result:
        {
            "success": bool,
            "repo_path": str (path to downloaded documentation),
            "error": str (error message if download failed)
        }

    Examples:
        - Simple download: "wget https://example.com/doc.tar.gz"
        - Recursive download: "wget -r -np -nH --cut-dirs=3 https://example.com/docs/"
        - Multiple files: "wget https://example.com/file1.txt https://example.com/file2.txt"
    """
    try:
        logger.info(f"Downloading documentation for {package_name} using wget")
        logger.info(f"Command: {wget_command}")

        dest_path = get_repo_path(package_name)

        # Ensure destination directory exists
        dest_path.mkdir(parents=True, exist_ok=True)

        # Parse wget command and add destination
        # Split command into parts
        cmd_parts = wget_command.split()

        if not cmd_parts or cmd_parts[0] != "wget":
            return json.dumps({
                "success": False,
                "error": "Command must start with 'wget'"
            })

        # Add -P flag for destination if not already present
        if "-P" not in cmd_parts:
            cmd_parts.insert(1, "-P")
            cmd_parts.insert(2, str(dest_path))

        logger.info(f"Executing: {' '.join(cmd_parts)}")

        # Execute wget command
        process = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"Successfully downloaded documentation to {dest_path}")
            return json.dumps({
                "success": True,
                "repo_path": str(dest_path),
                "message": f"Successfully downloaded documentation to {dest_path}"
            })
        else:
            error_msg = stderr.decode('utf-8') if stderr else "Unknown wget error"
            logger.error(f"Wget failed: {error_msg}")
            return json.dumps({
                "success": False,
                "error": f"Wget command failed: {error_msg}"
            })

    except Exception as e:
        logger.error(f"Error downloading documentation for {package_name}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })


@function_tool
async def generate_navigation_guide(package_name: str, repo_paths: List[str]) -> str:
    """
    Generate a navigation guide for a repository using Codex.

    Analyzes the repository structure and documentation, then creates a
    comprehensive navigation guide saved as <package_name>.md.

    Args:
        package_name (str): Package name (used for output filename)
        repo_paths (str): List of Path to the downloaded repositories of this package

    Returns:
        JSON string with generation result:
        {
            "success": bool,
            "guide_path": str (path to generated navigation guide),
            "error": str (error message if generation failed)
        }
    """
    try:
        logger.info(f"Generating navigation guide for {package_name}")
        logger.info(f"Repository path: {repo_paths}")

        # Use Codex to generate the navigation guide
        result = await execute_codex_nav_guide(
            package_name=package_name,
            repo_paths=repo_paths,
            prompt=NAVIGATION_GUIDE_PROMPT
        )

        if result["success"]:
            guide_path = get_guide_path(package_name)
            return json.dumps({
                "success": True,
                "guide_path": str(guide_path),
                "message": f"Successfully generated navigation guide at {guide_path}"
            })
        else:
            return json.dumps({
                "success": False,
                "error": result["error"]
            })

    except Exception as e:
        logger.error(f"Error generating navigation guide for {package_name}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })


# Tool registry for the repository registration agent
REPOSITORY_TOOLS = {
    "git_clone_repository": git_clone_repository,
    "wget_download_docs": wget_download_docs,
    "generate_navigation_guide": generate_navigation_guide
}
