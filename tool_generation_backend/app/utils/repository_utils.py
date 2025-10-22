"""
Utility functions for repository operations.

Handles git cloning, wget downloads, and Codex-based navigation guide generation.
"""

import asyncio
import logging
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def git_clone(url: str, branch: str, dest: Path) -> Dict[str, Any]:
    """
    Clone a git repository to destination path.

    Args:
        url: Git repository URL
        dest: Destination path for cloning

    Returns:
        Dict with success status and error message if failed
    """
    try:
        # Ensure parent directory exists
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing directory if present
        if dest.exists():
            logger.info(f"Removing existing directory: {dest}")
            shutil.rmtree(dest)

        logger.info(f"Cloning {url} to {dest}")

        # Run git clone
        process = await asyncio.create_subprocess_exec(
            "git", "clone", "-b", branch, "--depth", "1", url, str(dest),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"Successfully cloned repository to {dest}")
            return {
                "success": True,
                "path": str(dest),
                "stdout": stdout.decode('utf-8') if stdout else "",
                "stderr": stderr.decode('utf-8') if stderr else ""
            }
        else:
            error_msg = stderr.decode('utf-8') if stderr else "Unknown git error"
            logger.error(f"Git clone failed: {error_msg}")
            return {
                "success": False,
                "error": f"Git clone failed: {error_msg}",
                "stdout": stdout.decode('utf-8') if stdout else "",
                "stderr": error_msg
            }

    except Exception as e:
        logger.error(f"Exception during git clone: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def wget_download(base_url: str, dest: Path, files: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Download files from web using wget.

    Args:
        base_url: Base URL for downloads
        dest: Destination directory
        files: List of files to download (if None, downloads recursively)

    Returns:
        Dict with success status and error message if failed
    """
    try:
        # Ensure destination directory exists
        dest.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading from {base_url} to {dest}")

        if files:
            # Download specific files
            for file in files:
                url = f"{base_url.rstrip('/')}/{file}"
                logger.info(f"Downloading {url}")

                process = await asyncio.create_subprocess_exec(
                    "wget", "-P", str(dest), url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8') if stderr else "Unknown wget error"
                    logger.error(f"Wget failed for {file}: {error_msg}")
                    return {
                        "success": False,
                        "error": f"Wget failed for {file}: {error_msg}"
                    }
        else:
            # Recursive download
            process = await asyncio.create_subprocess_exec(
                "wget", "-r", "-np", "-nH", "--cut-dirs=3",
                "-P", str(dest), base_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown wget error"
                logger.error(f"Wget recursive download failed: {error_msg}")
                return {
                    "success": False,
                    "error": f"Wget failed: {error_msg}"
                }

        logger.info(f"Successfully downloaded to {dest}")
        return {
            "success": True,
            "path": str(dest)
        }

    except Exception as e:
        logger.error(f"Exception during wget download: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def execute_codex_nav_guide(
    package_name: str,
    repo_paths: List[str],
    prompt: str
) -> Dict[str, Any]:
    """
    Execute Codex to generate a navigation guide for a repository.

    Args:
        package_name: Name of the package
        repo_path: Path to the repository
        prompt: Codex prompt for navigation guide generation

    Returns:
        Dict with success status, guide path, and error if failed
    """
    try:
        from app.utils.codex_utils import _run_codex_command

        # Output file path
        output_file = Path(settings.repos_path) / f"{package_name}.md"

        # Build full prompt with file output instruction
        full_prompt = f"""{prompt}

You are generating a one-screen "navigation guide" for a scientific library repository Focus mainly on documentation. 

- Repository Location: {repo_paths}
- Package Name: {package_name}

IMPORTANT: Save the navigation guide to: {output_file}
IMPORTANT: This navigation guide is for agent who needs to use the repository as a package, YOU SHOULD NOT include any unuseful information, like downloading, contributing, etc.


## Goal
Produce a concise map that tells an agent:
1) where the docs live,
2) how they’re organized,
3) where API stubs are,
4) how to CLI-search them,
5) how to build/preview them,
6) how versions/tags relate to docs.
7) if available, where the docs live


## Heuristics (apply in this order)
- Detect doc roots: docs/, doc/, Docs/Book/, documentation/, guide/
- Detect toolchain:
  - Sphinx if conf.py + index.(rst|md)
  - MkDocs if mkdocs.yml
  - or other toolchains you found
- Identify “start-here” pages: index.(rst|md), overview*, install*, getting-started*, tutorial*, user_guide*, cookbook*, faq*, api*, reference/
- Navigation structure:
  - Sphinx: look for toctree files under docs/** (or Docs/Book/**)
  - MkDocs: analyze nav: in mkdocs.yml
  - or the structure you've found if other toolchain is used.
- API reference sources:
  - .rst/.md stubs under docs/**/api or reference/**, autodoc markers (automodule/autoclass/autofunction)
  - Point to source fallback: src/<pkg>/ or <pkg>/ (Python); note C/C++ dirs if present
- Examples/data/notebooks: examples/, docs/examples/, tutorials/, docs/**/data/
- Versioning/branches: infer typical patterns (vX.Y.Z, Release_YYYY_MM). If you see them in FILE_LIST, mention how to pick “stable” docs.
- Build/preview: minimal commands for the detected toolchain.

## Output Format (exactly this structure)
Doc Roots & Toolchain:
- Roots: <paths>
- Toolchain: <Sphinx or MkDocs>
- Entrypoints: <files>
- Build: <1–2 commands> → output: <dir>

Start-Here Pages:
- <list 4–8 likely entry pages>

Navigation Map:
- <1–3 bullets describing top sections / toctree or nav organization>

API Reference:
- Stubs: <paths> (autodoc markers: <yes/no>)
- Source fallback: <src/<pkg> or <pkg>/>

Examples & Data:
- <paths; note extra deps if any>

CLI Search Cheatsheet (replace TARGET):
- Toctrees: rg -n '^\.\. toctree::' <docroot>/** -C3
- API stubs: rg -n 'autoclass::.*TARGET|autofunction::.*TARGET|automodule::.*TARGET' <docroot>/**
- Narrative (exclude build/assets): rg -n 'TARGET' <docroot>/** -g '!**/_build/**' -g '!**/images/**' -g '!**/static/**' -g '!**/api/**'
- Source: rg -n 'def .*TARGET|class .*TARGET' src/** <pkg>/** -g '!**/build/**'


## Constraints
- Keep total length to about one screen (tight bullets).
- Do not describe non-docs areas except when pointing to source fallback.
- Prefer ripgrep (rg) in cheatsheet; do not include emojis.

"""

        # Build Codex command
        cmd = [
            "codex", "exec",
            "--model", "gpt-5",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "--cd", str(settings.tools_service_path),
            full_prompt
        ]

        logger.info(f"Generating navigation guide for {package_name}")
        result = await _run_codex_command(cmd, timeout=300)

        if not result["success"]:
            logger.error(f"Codex command failed: {result['error']}")
            return {
                "success": False,
                "error": result["error"]
            }

        # Check if output file was created
        if not output_file.exists():
            logger.error(f"Navigation guide not created: {output_file}")
            return {
                "success": False,
                "error": f"Navigation guide file not created: {output_file}"
            }

        logger.info(f"Successfully generated navigation guide: {output_file}")
        return {
            "success": True,
            "guide_path": str(output_file)
        }

    except Exception as e:
        logger.error(f"Exception generating navigation guide: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def check_nav_guide_exists(package_name: str) -> bool:
    """
    Check if a navigation guide exists for a package.

    Args:
        package_name: Package name

    Returns:
        True if navigation guide exists, False otherwise
    """
    guide_path = Path(settings.repos_path) / f"{package_name}.md"
    return guide_path.exists()


def check_repo_exists(package_name: str) -> bool:
    """
    Check if a repository directory exists for a package.

    Args:
        package_name: Package name

    Returns:
        True if repository directory exists, False otherwise
    """
    repo_path = Path(settings.repos_path) / package_name
    return repo_path.exists() and repo_path.is_dir()


def get_repo_path(package_name: str) -> Path:
    """
    Get the repository path for a package.

    Args:
        package_name: Package name

    Returns:
        Path to repository directory
    """
    return Path(settings.repos_path) / package_name


def get_guide_path(package_name: str) -> Path:
    """
    Get the navigation guide path for a package.

    Args:
        package_name: Package name

    Returns:
        Path to navigation guide file
    """
    return Path(settings.repos_path) / f"{package_name}.md"
