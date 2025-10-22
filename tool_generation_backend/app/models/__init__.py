# Pydantic models for agent-browser backend

from .base import BaseModelConfig, TimestampedModel, DatabaseModel
from .specs import ParameterSpec, OutputSpec, UserToolRequirement
from .session import (
    SessionStatus,
    ToolRequirement,
    ImplementationPlan,
    Session,
    SessionCreate,
    SessionUpdate,
    SessionResponse,
)
# Agent models removed - using OpenAI Agent SDK
from .tool import (
    Tool,
    ToolStatus,
    ToolExecutionRequest,
    ToolExecutionResponse,
    ToolGenerationRequest,
    ToolGenerationResponse,
    ToolRegistrationRequest,
    ToolRegistrationResponse,
    ToolListRequest,
    ToolListResponse,
)
from .api_reference import (
    ApiQuery,
    ApiExample,
    ApiBrowseResult,
)
from .tool_generation import (
    ToolGenerationResult,
    ToolGenerationFailure,
    ToolGenerationOutput,
)
from .tool_failure import ToolFailure
from .repository import (
    PackageConfig,
    RepositoryInfo,
    RepositoryRegistrationRequest,
    RepositoryRegistrationResult,
    RepositoryRegistrationResponse,
    RepositoryRegistrationOutput,
)

__all__ = [
    # Base models
    "BaseModelConfig",
    "TimestampedModel",
    "DatabaseModel",
    # Spec models
    "ParameterSpec",
    "OutputSpec",
    "UserToolRequirement",
    # Session models
    "SessionStatus",
    "ToolRequirement",
    "ImplementationPlan",
    "Session",
    "SessionCreate",
    "SessionUpdate",
    "SessionResponse",
    # Agent models removed - using OpenAI Agent SDK
    # Tool models
    "Tool",
    "ToolStatus",
    "ToolExecutionRequest",
    "ToolExecutionResponse",
    "ToolGenerationRequest",
    "ToolGenerationResponse",
    "ToolRegistrationRequest",
    "ToolRegistrationResponse",
    "ToolListRequest",
    "ToolListResponse",
    # API Reference models
    "ApiQuery",
    "ApiExample",
    "ApiBrowseResult",
    # Tool Generation models
    "ToolGenerationResult",
    "ToolGenerationFailure",
    "ToolGenerationOutput",
    # Tool Failure models
    "ToolFailure",
    # Repository models
    "PackageConfig",
    "RepositoryInfo",
    "RepositoryRegistrationRequest",
    "RepositoryRegistrationResult",
    "RepositoryRegistrationResponse",
    "RepositoryRegistrationOutput",
]