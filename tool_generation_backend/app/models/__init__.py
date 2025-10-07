# Pydantic models for agent-browser backend

from .base import BaseModelConfig, TimestampedModel, DatabaseModel
from .session import (
    SessionStatus,
    ToolRequirement,
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
    ApiFunction,
    ApiExample,
    ApiBrowseResult,
)

__all__ = [
    # Base models
    "BaseModelConfig",
    "TimestampedModel",
    "DatabaseModel",
    # Session models
    "SessionStatus",
    "ToolRequirement",
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
    "ApiFunction",
    "ApiExample",
    "ApiBrowseResult",
]