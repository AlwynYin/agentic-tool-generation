"""
Shared specification models used across the application.
These models are intentionally separated to avoid circular imports.
"""

from pydantic import BaseModel, Field


class ParameterSpec(BaseModel):
    """Specification of a parameter used by a function."""
    name: str
    type: str
    description: str


class OutputSpec(BaseModel):
    """Specification of function output."""
    type: str
    description: str


class UserToolRequirement(BaseModel):
    """Tool requirement as specified by the user."""
    description: str = Field(..., description="Natural language description of the tool")
    input: str = Field(..., description="Natural language description of the input")
    output: str = Field(..., description="Natural language description of the output")