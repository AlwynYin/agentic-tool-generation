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


class ApiBrowseResult(BaseModel):
    """Result from browsing API documentation."""

    success: bool = Field(description="Whether the browse operation succeeded")
    library: str = Field(description="Library name (e.g., 'rdkit')")
    queries: List[str] = Field(description="Queries that were searched")
    file_name: str = Field(default="", description="File name of the json file containing browse result")
    search_results: str = Field(
        default="",
        description="Raw JSON string content of the search results"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if operation failed"
    )
    output_file: Optional[str] = Field(
        default=None,
        description="Path to JSON output file from Codex"
    )
