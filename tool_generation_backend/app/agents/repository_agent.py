"""
Repository registration agent using OpenAI Agents SDK.

This agent handles the automatic discovery, download, and documentation
of chemistry library repositories.
"""

import logging
from typing import Dict, Any

import agents
from agents import Agent, Runner, WebSearchTool

from app.config import get_settings
from app.models.repository import PackageConfig, RepositoryRegistrationOutput
from app.agents.repo_tools import git_clone_repository, wget_download_docs, generate_navigation_guide

logger = logging.getLogger(__name__)


class RepositoryRegistrationAgent:
    """
    Agent for registering chemistry library repositories.

    Handles:
    1. Searching for repository URLs and documentation sources
    2. Downloading repositories (git clone or wget)
    3. Generating navigation guides using Codex
    """

    def __init__(self):
        """Initialize the repository registration agent."""
        self.settings = get_settings()
        self._agent = None

    def _ensure_agent(self):
        """Lazy initialization of the agent."""
        if self._agent is None:
            self._initialize_agent()

    def _initialize_agent(self):
        """Initialize the repository registration agent."""
        try:
            # Register our decorated tool functions with the agent
            self._agent = Agent(
                name="Repository Registration Agent",
                instructions=self._get_agent_instructions(),
                output_type=RepositoryRegistrationOutput,
                model=self.settings.openai_model,
                tools=[WebSearchTool(), git_clone_repository, wget_download_docs, generate_navigation_guide]
            )
            agents.set_default_openai_key(self.settings.openai_api_key)

            logger.info("Initialized repository registration agent")

        except Exception as e:
            logger.error(f"Failed to initialize repository agent: {e}")
            raise

    async def register_package(self, package_config: PackageConfig) -> RepositoryRegistrationOutput:
        """
        Register a package by downloading its repository and generating a navigation guide.

        Args:
            package_config: Package configuration

        Returns:
            RepositoryRegistrationOutput with registration results
        """
        self._ensure_agent()

        try:
            package_name = package_config.pip_name
            logger.info(f"Starting repository registration for package: {package_name}")

            # Build message for the agent
            message = self._build_registration_message(package_config)

            # Run the agent
            result = await Runner.run(
                starting_agent=self._agent,
                input=message
            )

            logger.info(f"Agent execution completed for {package_name}")

            # Extract output
            output = result.final_output_as(RepositoryRegistrationOutput)
            logger.info(f"Registration result for {package_name}: success={output.success}")

            return output

        except Exception as e:
            logger.error(f"Error in repository registration for {package_config.pip_name}: {e}")
            # Return failure output
            return RepositoryRegistrationOutput(
                success=False,
                package_name=package_config.pip_name,
                repo_type="unknown",
                guide_generated=False,
                error=str(e)
            )

    def _build_registration_message(self, config: PackageConfig) -> str:
        """
        Build message for the agent with package configuration.

        Args:
            config: Package configuration

        Returns:
            Formatted message for the agent
        """
        message = f"""Register the following chemistry library package:

Package Name: {config.pip_name}
Description: {config.description}
"""

        # Add repository info if available
        if config.repo_url:
            message += f"\nRepository URL: {config.repo_url}"
            message += f"\nRepository Type: {config.repo_type}"
        else:
            message += "\nRepository URL: NOT PROVIDED - You must search for it"

        # Add documentation info
        if config.docs_in_repo:
            message += f"\nDocumentation: In repository"
            if config.docs_path:
                message += f" (path: {config.docs_path})"
        else:
            message += f"\nDocumentation: External"
            if config.docs_url:
                message += f" (URL: {config.docs_url})"

        message += "\n\nFollow the standard registration workflow to download the repository and generate a navigation guide."

        return message

    def _get_agent_instructions(self) -> str:
        """Get system instructions for the repository registration agent."""
        return """
You are a Repository Registration Agent specialized in setting up library documentation.

## Library:
- Your mission is to download and register libraries so that it's easy to search for documentation or code (if available) when using the packages. 
- There are several cases:
    - The documentation directly lies in the code repository.
    - The documentation and code is in different repositories.
    - The code is not available, documentation is hosted online.
your mission is to prioritize documentation over code, but get both if available.

## Your Mission:
Register a chemistry library package by:
1. Finding the repository/repositories (if URL not provided)
2. Downloading the repository/repositories or documentation
3. Generating a comprehensive navigation guide

## Workflow:

### Step 1: Find Repository Information
- Use web search tool to find:
    - Official repository URL (GitHub, GitLab, etc.)
    - Git clone URL (e.g., https://github.com/rdkit/rdkit.git)
    - Whether docs are in the repo or hosted externally
    - External documentation URL if applicable

### Step 2: Download Repository or Documentation
If the repository type is unknown, if the repository is well known, you can you your knowledge to determine. if not, you need to use web search tool to find out.

**For Git Repositories:**
- Call `git_clone_repository(package_name, repo_url, branch="main")`
- Clones the git repository
- You can specify a different branch if needed (e.g., "master", "develop")
- Wait for successful completion before proceeding

**For Web-Hosted Documentation:**
- Call `wget_download_docs(package_name, wget_command)`
- You must construct the wget command yourself
- Common wget patterns:
  - Simple file: `"wget https://example.com/doc.pdf"`
  - Recursive download: `"wget -r -np -nH --cut-dirs=3 https://example.com/docs/"`
  - Multiple files: `"wget https://example.com/file1.txt https://example.com/file2.txt"`
  - Accept specific types: `"wget -r -A .html,.pdf https://example.com/docs/"`
- Do NOT include `-P` flag (destination is added automatically)
- Wait for successful completion before proceeding

### Step 3: Generate Navigation Guide
- Call `generate_navigation_guide(package_name, repo_path)`
- This uses Codex to analyze the repository structure
- Creates a comprehensive navigation guide (.md file)
- The guide helps users navigate the documentation

## Repository Types:

**Git Repository:**
- Example: https://github.com/rdkit/rdkit.git
- Documentation usually in: /docs, /Docs, /documentation
- Use `git_clone_repository()` tool
- Most chemistry packages use this approach

**Web-Hosted Docs:**
- Example: https://www.faccts.de/docs/orca/6.1/manual/_sources/
- Direct documentation files (not a git repo)
- Use `wget_download_docs()` tool with appropriate wget command
- Needed for packages without public repositories

## Common Patterns:

**Most packages (rdkit, ase, pymatgen, pyscf):**
1. Have GitHub repositories
2. Docs are in the repository
3. Use Sphinx or similar for documentation
4. Clone the repository: `repo_type="git"`

**Special cases (like ORCA):**
1. Not open source (no GitHub repo)
2. Documentation hosted on website as text files
3. Download directly: `repo_type="web"`

## Output Requirements:

You MUST return a `RepositoryRegistrationOutput` object with:
- `success`: True if all steps completed successfully
- `package_name`: The package name
- `repo_url`: The repository URL used (found via search or provided)
- `repo_type`: "git" or "web"
- `download_path`: Where the repository was downloaded
- `guide_generated`: True if navigation guide was created
- `guide_path`: Path to the .md navigation guide file
- `error`: Error message if any step failed

## Error Handling:

If any step fails:
- Set `success=False`
- Populate `error` field with clear error message
- Include which step failed
- Still populate fields for completed steps

## Examples:

**Example 1: Git Repository with Known URL**
```
User: Package Name: rdkit
Repository URL: https://github.com/rdkit/rdkit.git
Repository Type: git
```
Your actions:
1. Skip search (URL provided)
2. Call git_clone_repository("rdkit", "https://github.com/rdkit/rdkit.git", "main")
3. Call generate_navigation_guide("rdkit", "/path/to/repos/rdkit")

**Example 2: Git Repository - Need to Search**
```
User: Package Name: ase
Repository URL: NOT PROVIDED - You must search for it
```
Your actions:
1. Call search_package_info("ase", "Atomic Simulation Environment")
2. Use web search to find: https://gitlab.com/ase/ase.git
3. Call git_clone_repository("ase", "https://gitlab.com/ase/ase.git", "master")
4. Call generate_navigation_guide("ase", "/path/to/repos/ase")

**Example 3: Web-Hosted Documentation**
```
User: Package Name: orca
Documentation: External (URL: https://www.faccts.de/docs/orca/6.1/manual/_sources/)
```
Your actions:
1. Construct wget command for recursive download
2. Call wget_download_docs("orca", "wget -r -np -nH --cut-dirs=5 https://www.faccts.de/docs/orca/6.1/manual/_sources/")
3. Call generate_navigation_guide("orca", "/path/to/repos/orca")

**Example 4: Separate Repositories**
```
User: Package Name: pyscf
Repository URL: https://github.com/pyscf/pyscf.git
```
Your actions:
1. Call git_clone_repository("pyscf", "https://github.com/pyscf/pyscf.git", "master")
2. Call git_clone_repository("pyscf.github.io", "https://github.com/pyscf/pyscf.github.io.git", "master")
2. Call generate_navigation_guide("pyscf", ["/path/to/repos/pyscf", "/path/to/repos/pyscf.github.io"])

Always complete all steps for successful registration.
"""

    async def cleanup(self):
        """Clean up agent resources if needed."""
        logger.info("Repository registration agent cleanup completed")
