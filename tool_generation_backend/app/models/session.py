"""
Session-related Pydantic models.
Translated from TypeScript schema interfaces.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Literal

from pydantic import Field, BaseModel

from .base import DatabaseModel, BaseModelConfig
from .job import UserToolRequirement



class SessionStatus(str, Enum):
    """Session workflow status enumeration."""
    PENDING = "pending"
    PLANNING = "planning"
    SEARCHING = "searching"
    IMPLEMENTING = "implementing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class ParameterSpec(BaseModel):
    """Specification of a parameter used by a function."""
    name: str
    type: str
    description: str


class OutputSpec(BaseModel):
    """Specification of a parameter used by a function."""
    type: str
    description: str


class ToolRequirement(BaseModelConfig):
    """Tool requirement specification from orchestrator agent."""

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    input_format: List[ParameterSpec] = Field(
        description="Schema of tool inputs"
    )
    output_format: OutputSpec = Field(
        description="Schema of tool outputs"
    )
    required_apis: List[str] = Field(
        default_factory=list,
        description="API functions needed for this tool"
    )


class ToolGenerationResult(BaseModel):
    """Tool generation result returned by implementation agent.
       it contains all the necessary field of a ToolSpec, except for code, status, registered
    """
    success: bool = Field(description="Tool generation")
    name: str = Field(description="Tool name")
    file_name: str = Field(description="Python file name")
    description: str = Field(description="Tool description")
    input_schema: List[ParameterSpec] = Field(
        default_factory=list,
        description="Input schema"
    )
    output_schema: OutputSpec = Field(
        default_factory=dict,
        description="Output schema"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Required Python packages"
    )


class Session(DatabaseModel):
    """Session for tool generation or update workflow."""

    job_id: str = Field(description="Associated job ID")
    user_id: str = Field(description="User identifier")
    operation_type: Literal["generate", "update"] = Field(
        default="generate",
        description="Type of operation: generate new tools or update existing"
    )

    # For generate operations
    tool_requirements: List[UserToolRequirement] = Field(
        default_factory=list,
        description="User tool requirements for generation"
    )

    # For update operations

    status: SessionStatus = Field(
        default=SessionStatus.PENDING,
        description="Current workflow status"
    )

    # Tool references (stored in separate tools collection)
    tool_ids: List[str] = Field(
        default_factory=list,
        description="IDs of tools in the tools collection"
    )

    error_message: Optional[str] = Field(
        default=None,
        description="Error message if session failed"
    )


# Request/Response models for API endpoints
class SessionCreate(BaseModelConfig):
    """Request model for creating a new session."""

    user_id: str = Field(description="User identifier")
    requirements: List[UserToolRequirement] = Field(description="User's input requirement")


class SessionUpdate(BaseModelConfig):
    """Request model for updating a session."""

    status: Optional[SessionStatus] = Field(
        default=None,
        description="New session status"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if applicable"
    )


class SessionResponse(BaseModelConfig):
    """Response model for session operations."""

    session_id: str = Field(description="Session ID")
    status: SessionStatus = Field(description="Current session status")
    created_at: datetime = Field(description="Session creation timestamp")
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last update timestamp"
    )