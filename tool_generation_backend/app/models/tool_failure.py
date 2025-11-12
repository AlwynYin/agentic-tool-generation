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

    # Partial file contents from failed generation (if available)
    code: Optional[str] = Field(
        default=None,
        description="Main tool code (if generated before failure)"
    )
    test_code: Optional[str] = Field(
        default=None,
        description="Test file contents (if generated before failure)"
    )
    implementation_plan: Optional[str] = Field(
        default=None,
        description="Implementation plan file contents (if generated before failure)"
    )
    function_spec: Optional[str] = Field(
        default=None,
        description="Function specification file contents (if generated before failure)"
    )
    contracts_plan: Optional[str] = Field(
        default=None,
        description="Contracts file contents (if generated before failure)"
    )
    validation_rules: Optional[str] = Field(
        default=None,
        description="Validation rules file contents (if generated before failure)"
    )
    test_requirements: Optional[str] = Field(
        default=None,
        description="Test requirements file contents (if generated before failure)"
    )
    search_results: Optional[str] = Field(
        default=None,
        description="API exploration results (if generated before failure)"
    )
