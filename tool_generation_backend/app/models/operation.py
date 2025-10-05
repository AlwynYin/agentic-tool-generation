"""
Operation context models for agent pipeline.
"""

from typing import Union, Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field

from .job import UserToolRequirement


class ImplementRequirements(BaseModel):
    """Requirements for implement operation."""
    tools: List[UserToolRequirement] = Field(description="Tools to implement")


class UpdateRequirements(BaseModel):
    """Requirements for update operation."""
    base_job_id: str = Field(description="Job ID of tools to update")
    updates: List[UserToolRequirement] = Field(description="Update specifications")


class OperationContext(BaseModel):
    """
    Context for tool generation operations.
    Currently only supports 'implement' operations.
    """

    operation_type: Literal["implement"] = Field(
        default="implement",
        description="Type of operation to perform (currently only 'implement')"
    )

    requirements: ImplementRequirements = Field(
        description="Tool implementation requirements"
    )

    session_id: str = Field(description="Session identifier")

    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata for the operation"
    )

    @classmethod
    def create_implement_operation(
        cls,
        session_id: str,
        tools: List[UserToolRequirement],
        metadata: Optional[Dict[str, Any]] = None
    ) -> "OperationContext":
        """Create an implement operation context."""
        return cls(
            requirements=ImplementRequirements(tools=tools),
            session_id=session_id,
            metadata=metadata
        )