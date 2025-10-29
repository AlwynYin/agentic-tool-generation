"""
Tool failure model for storing failed tool generation attempts.
"""

from typing import Optional
from pydantic import Field

from .base import DatabaseModel
from .specs import UserToolRequirement


class ToolFailure(DatabaseModel):
    """
    Record of a failed tool generation attempt.
    Stored in separate collection from successful tools.
    """
    task_id: str = Field(description="Task that attempted to generate this tool")
    user_requirement: UserToolRequirement = Field(
        description="Original user requirement that failed"
    )
    error_message: str = Field(
        description="Error message explaining why generation failed"
    )
    error_type: Optional[str] = Field(
        default=None,
        description="Category of failure (malformed, too_broad, not_chemistry, etc.)"
    )
