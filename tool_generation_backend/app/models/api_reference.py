"""
API Reference models for documentation browsing and extraction.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from .session import ParameterSpec, OutputSpec


class ApiQuery(BaseModel):
    """Query for API documentation search."""

    query: str = Field(
        description="Search query for API documentation (e.g., 'molecular weight calculation')"
    )


class ApiExample(BaseModel):
    """Example usage of an API function."""

    description: str = Field(description="Description of what the example does")
    code: str = Field(description="Example code snippet")
    expected_output: Optional[str] = Field(
        default=None,
        description="Expected output or result description"
    )


class ApiFunction(BaseModel):
    """API function reference with complete signature and examples."""

    function_name: str = Field(description="Full function name (e.g., 'rdkit.Chem.Descriptors.MolWt')")
    description: str = Field(description="Function description")
    input_schema: List[ParameterSpec] = Field(
        description="List of input parameters with types and descriptions"
    )
    output_schema: OutputSpec = Field(
        description="Output type and description"
    )
    examples: List[ApiExample] = Field(
        default_factory=list,
        description="List of usage examples"
    )


class ApiBrowseResult(BaseModel):
    """Result from browsing API documentation."""

    success: bool = Field(description="Whether the browse operation succeeded")
    library: str = Field(description="Library name (e.g., 'rdkit')")
    queries: List[str] = Field(description="Queries that were searched")
    api_functions: List[ApiFunction] = Field(
        default_factory=list,
        description="List of API functions found"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if operation failed"
    )
    output_file: Optional[str] = Field(
        default=None,
        description="Path to JSON output file from Codex"
    )
