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

        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY environment variable is required")

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