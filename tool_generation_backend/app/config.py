"""
Configuration management for agent-browser backend.
Loads and validates environment variables using Pydantic Settings.
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    mongodb_url: str = Field(
        default="mongodb://localhost:27017",
        env="MONGODB_URL",
        description="MongoDB connection URL (without database name)"
    )

    mongodb_db_name: str = Field(
        default="tool_generation_backend",
        env="MONGODB_DB_NAME",
        description="MongoDB database name"
    )

    # AI Services
    llm_backend: str = Field(
        default="codex",
        env="LLM_BACKEND",
        description="LLM backend to use: 'codex' or 'claude'"
    )
    openai_api_key: str = Field(
        ...,
        env="OPENAI_API_KEY",
        description="OpenAI API key for LLM services"
    )
    openai_model: str = Field(
        default="gpt-5",
        env="OPENAI_MODEL",
        description="OpenAI model to use"
    )
    anthropic_api_key: str = Field(
        default="",
        env="ANTHROPIC_API_KEY",
        description="Anthropic API key for Claude Code (optional, uses claude login if not provided)"
    )

    # Server Configuration
    host: str = Field(
        default="0.0.0.0",
        env="HOST",
        description="Server host address"
    )

    port: int = Field(
        default=8000,
        env="PORT",
        description="Server port number"
    )
    cors_origins: str = Field(
        default="http://localhost:3000",
        env="CORS_ORIGINS",
        description="Allowed CORS origins (comma-separated)"
    )

    def get_cors_origins_list(self) -> List[str]:
        """Parse CORS origins string into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # Environment
    environment: str = Field(
        default="development",
        env="ENVIRONMENT",
        description="Application environment: development, production, test"
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        env="LOG_LEVEL",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )

    # Tool Generation Paths
    tool_service_dir: str = Field(
        default="tool_service",
        env="TOOL_SERVICE_DIR",
        description="Directory for tool service files"
    )

    tools_dir: str = Field(
        default="tools",
        env="TOOLS_DIR",
        description="Directory name for generated tools (relative to tool_service_dir)"
    )

    repos_dir: str = Field(
        default="repos",
        env="REPOS_DIR",
        description="Directory name for repositories (relative to tool_service_dir)"
    )

    searchs_dir: str = Field(
        default="searches",
        env="SEARCHES_DIR",
        description="Directory for search results (relative to tool_service_dir)"
    )

    # Pipeline V2 Configuration
    pipeline_version: str = Field(
        default="v2",
        env="PIPELINE_VERSION",
        description="Pipeline version to use: v1 or v2"
    )

    max_refinement_iterations: int = Field(
        default=3,
        env="MAX_REFINEMENT_ITERATIONS",
        description="Maximum iterations for tool refinement in V2 pipeline"
    )

    enable_property_tests: bool = Field(
        default=False,
        env="ENABLE_PROPERTY_TESTS",
        description="Generate property-based tests in V2 pipeline"
    )

    enable_golden_tests: bool = Field(
        default=True,
        env="ENABLE_GOLDEN_TESTS",
        description="Generate golden output tests in V2 pipeline"
    )

    pytest_timeout: int = Field(
        default=60,
        env="PYTEST_TIMEOUT",
        description="Timeout for pytest execution in seconds"
    )

    @property
    def tools_service_path(self) -> str:
        """Get the full tools directory path."""
        return f"{self.tool_service_dir}"

    @property
    def tools_path(self) -> str:
        """Get the full tools directory path."""
        return f"{self.tool_service_dir}/{self.tools_dir}"

    @property
    def repos_path(self) -> str:
        """Get the repos directory path for library documentation."""
        return f"{self.tool_service_dir}/{self.repos_dir}"

    @property
    def searches_path(self) -> str:
        """Get the repos directory path for library documentation."""
        return f"{self.tool_service_dir}/{self.searchs_dir}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def validate_configuration(self) -> None:
        """Validate required configuration settings."""
        errors = []

        # Validate LLM backend selection
        valid_backends = {"codex", "claude"}
        if self.llm_backend not in valid_backends:
            errors.append(
                f"LLM_BACKEND must be one of {valid_backends}, "
                f"got: {self.llm_backend}"
            )

        # Validate backend-specific API keys
        if self.llm_backend == "codex" and not self.openai_api_key:
            errors.append("OPENAI_API_KEY environment variable is required when using Codex backend")

        if not self.mongodb_url:
            errors.append("MONGODB_URL environment variable is required")

        # Validate environment values
        valid_environments = {"development", "production", "test"}
        if self.environment not in valid_environments:
            errors.append(
                f"ENVIRONMENT must be one of {valid_environments}, "
                f"got: {self.environment}"
            )

        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_log_levels:
            errors.append(
                f"LOG_LEVEL must be one of {valid_log_levels}, "
                f"got: {self.log_level}"
            )

        if errors:
            raise ValueError(
                "Configuration validation failed:\n" +
                "\n".join(f"  - {error}" for error in errors)
            )


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)."""
    settings = Settings()
    settings.validate_configuration()
    return settings