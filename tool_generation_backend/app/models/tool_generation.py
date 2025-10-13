"""
Tool generation result models.

This module contains models for successful tool generation results
and tool generation failures.
"""

from typing import List
from pydantic import Field, BaseModel

from .base import BaseModelConfig
from .specs import ParameterSpec, OutputSpec, UserToolRequirement


class ToolGenerationResult(BaseModel):
    """Tool generation result returned by implementation agent.
       Contains all the necessary fields of a ToolSpec, except for code, status, registered
    """
    success: bool = Field(description="Tool generation success flag")
    name: str = Field(description="Tool name")
    file_name: str = Field(description="Python file name")
    description: str = Field(description="Tool description")
    input_schema: List[ParameterSpec] = Field(  # Use Any to avoid circular import, will be List[ParameterSpec] at runtime
        default_factory=list,
        description="Input schema (List of ParameterSpec)"
    )
    output_schema: OutputSpec = Field(  # Use Any to avoid circular import, will be OutputSpec at runtime
        default_factory=dict,
        description="Output schema (OutputSpec)"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Required Python packages"
    )


class ToolGenerationFailure(BaseModel):
    """Failed tool generation information."""
    toolRequirement: UserToolRequirement = Field(
        description="The requirement that failed",
        serialization_alias="toolRequirement"  # Serialize with field name, not alias
    )
    error: str = Field(description="Error message explaining why generation failed")

    class Config:
        populate_by_name = True  # Allow both field name and alias for input


class ToolGenerationOutput(BaseModel):
    """
    Output from tool generation pipeline.
    Contains both successful results and failures.
    """
    results: List[ToolGenerationResult] = Field(
        default_factory=list,
        description="Successfully generated tools"
    )
    failures: List[ToolGenerationFailure] = Field(
        default_factory=list,
        description="Failed tool generation attempts"
    )

    @property
    def total_count(self) -> int:
        """Total number of tool generation attempts."""
        return len(self.results) + len(self.failures)

    @property
    def success_count(self) -> int:
        """Number of successful generations."""
        return len(self.results)

    @property
    def failure_count(self) -> int:
        """Number of failed generations."""
        return len(self.failures)
