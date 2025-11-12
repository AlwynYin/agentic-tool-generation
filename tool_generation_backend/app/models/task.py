"""
Task-related Pydantic models.
A Task represents a single tool generation task within a Job.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Literal

from pydantic import Field, BaseModel

from .base import DatabaseModel, BaseModelConfig
from .specs import UserToolRequirement, ParameterSpec, OutputSpec
from .tool_generation import ToolGenerationResult



class TaskStatus(str, Enum):
    """Task workflow status enumeration."""
    PENDING = "pending"
    PLANNING = "planning"
    SEARCHING = "searching"
    IMPLEMENTING = "implementing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


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

class Task(DatabaseModel):
    """Task for single tool generation.

    A Task represents the generation of ONE tool within a Job.
    Each Job spawns multiple Tasks (one per tool requirement).
    """

    task_id: str = Field(description="Unique task identifier")
    job_id: str = Field(description="Parent job ID")
    user_id: str = Field(description="User identifier")

    # Single tool requirement (not a list!)
    tool_requirement: UserToolRequirement = Field(
        description="User tool requirement for this task"
    )

    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        description="Current workflow status"
    )

    # Single tool result (either success OR failure)
    tool_id: Optional[str] = Field(
        default=None,
        description="ID of successfully generated tool in the tools collection"
    )

    tool_failure_id: Optional[str] = Field(
        default=None,
        description="ID of failed tool generation in the tool_failures collection"
    )

    error_message: Optional[str] = Field(
        default=None,
        description="Error message if task failed"
    )


# Request/Response models for API endpoints
class TaskCreate(BaseModelConfig):
    """Request model for creating a new task."""

    job_id: str = Field(description="Parent job ID")
    user_id: str = Field(description="User identifier")
    requirement: UserToolRequirement = Field(description="User's tool requirement")


class TaskUpdate(BaseModelConfig):
    """Request model for updating a task."""

    status: Optional[TaskStatus] = Field(
        default=None,
        description="New task status"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if applicable"
    )
    tool_id: Optional[str] = Field(
        default=None,
        description="Generated tool ID"
    )
    tool_failure_id: Optional[str] = Field(
        default=None,
        description="Tool failure ID"
    )


class TaskResponse(BaseModelConfig):
    """Response model for task operations."""

    task_id: str = Field(description="Task ID")
    job_id: str = Field(description="Parent job ID")
    status: TaskStatus = Field(description="Current task status")
    tool_requirement: UserToolRequirement = Field(description="Tool requirement")
    created_at: str = Field(description="Task creation timestamp (ISO format)")
    updated_at: Optional[str] = Field(
        default=None,
        description="Last update timestamp (ISO format)"
    )