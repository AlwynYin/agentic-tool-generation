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
    error_type: str = Field(
        default="unknown",
        description="One or two words explaining why generation failed"
    )

    class Config:
        populate_by_name = True  # Allow both field name and alias for input


class ToolGenerationOutput(BaseModel):
    """
    Output from tool generation pipeline V2.
    Represents the result of generating a SINGLE tool.

    The v2 pipeline processes one tool at a time, so this model
    is simplified to handle single-tool results rather than batches.
    """
    success: bool = Field(
        description="Whether tool generation succeeded"
    )
    result: ToolGenerationResult | None = Field(
        None,
        description="Generated tool (only present if success=True)"
    )
    failure: ToolGenerationFailure | None = Field(
        None,
        description="Failure details (only present if success=False)"
    )
