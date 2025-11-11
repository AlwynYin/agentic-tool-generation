"""
Pydantic models for repository management and registration.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator


class PackageConfig(BaseModel):
    """
    Package configuration with minimal required fields.

    Only requires: description
    All other fields are auto-populated with defaults.
    """

    # Minimal required field
    description: str = Field(description="Package description")

    # Auto-populated fields (all have defaults)
    package_name: Optional[str] = Field(
        default=None,
        description="Package name (defaults to dict key)"
    )
    import_names: List[str] = Field(
        default_factory=list,
        description="Python import names (defaults to [package_name])"
    )
    version_constraint: str = Field(
        default="",
        description="Version constraint (e.g., '>=2023.3.1', empty if unknown)"
    )
    size_mb: int = Field(
        default=0,
        description="Approximate package size in MB (0 if unknown)"
    )
    essential: bool = Field(
        default=False,
        description="Whether package is essential for core functionality"
    )
    repo_url: Optional[str] = Field(
        default=None,
        description="Repository URL (git clone URL or web base URL)"
    )
    repo_type: str = Field(
        default="unknown",
        description="Repository type: 'git', 'web', or 'unknown' (agent will determine)"
    )
    docs_in_repo: bool = Field(
        default=True,
        description="Whether documentation is in the repository"
    )
    docs_url: Optional[str] = Field(
        default=None,
        description="External documentation URL (if docs_in_repo=False)"
    )
    docs_path: str = Field(
        default="",
        description="Relative path to docs in repository"
    )

    @model_validator(mode='after')
    def validate_repo_config(self):
        """Validate repository configuration consistency."""
        # Auto-populate import_names if empty
        if not self.import_names and self.package_name:
            self.import_names = [self.package_name]

        # If docs not in repo, must provide docs_url
        if not self.docs_in_repo and not self.docs_url:
            raise ValueError(
                f"{self.package_name}: docs_url is required when docs_in_repo=False"
            )

        # Validate repo_type
        if self.repo_type not in ["git", "web", "unknown"]:
            raise ValueError(
                f"{self.package_name}: repo_type must be 'git', 'web', or 'unknown', got '{self.repo_type}'"
            )

        return self


class RepositoryInfo(BaseModel):
    """Runtime information about a repository's status."""

    package_name: str = Field(description="Package name")
    has_navigation_guide: bool = Field(description="Whether navigation guide (.md) exists")
    repo_exists: bool = Field(description="Whether repository directory exists")
    repo_path: Optional[str] = Field(default=None, description="Path to repository")
    guide_path: Optional[str] = Field(default=None, description="Path to navigation guide")
    config: PackageConfig = Field(description="Package configuration")


class RepositoryRegistrationRequest(BaseModel):
    """Request to register one or more packages."""

    package_names: List[str] = Field(
        description="List of package names to register"
    )


class RepositoryRegistrationResult(BaseModel):
    """Result of registering a single repository."""

    success: bool = Field(description="Whether registration succeeded")
    package_name: str = Field(description="Package name")
    repo_path: Optional[str] = Field(default=None, description="Path to downloaded repository")
    guide_path: Optional[str] = Field(default=None, description="Path to generated navigation guide")
    error: Optional[str] = Field(default=None, description="Error message if registration failed")
    steps_completed: List[str] = Field(
        default_factory=list,
        description="List of completed steps (e.g., 'search', 'download', 'generate_guide')"
    )


class RepositoryRegistrationResponse(BaseModel):
    """Response from batch repository registration."""

    total: int = Field(description="Total number of packages processed")
    successful: int = Field(description="Number of successful registrations")
    failed: int = Field(description="Number of failed registrations")
    results: List[RepositoryRegistrationResult] = Field(
        description="Individual results for each package"
    )


class RepositoryRegistrationOutput(BaseModel):
    """
    Structured output from RepositoryRegistrationAgent.

    This is the output_type for the OpenAI agent.
    """

    success: bool = Field(description="Overall success status")
    package_name: str = Field(description="Package name that was registered")
    repo_url: Optional[str] = Field(default=None, description="Repository URL used")
    repo_type: str = Field(description="Repository type used (git/web)")
    download_path: Optional[str] = Field(default=None, description="Where repository was downloaded")
    guide_generated: bool = Field(description="Whether navigation guide was generated")
    guide_path: Optional[str] = Field(default=None, description="Path to navigation guide")
    error: Optional[str] = Field(default=None, description="Error message if failed")