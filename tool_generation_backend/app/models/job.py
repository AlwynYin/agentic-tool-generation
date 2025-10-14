from pydantic import BaseModel, Field
from typing import Optional, List

from .tool_generation import ToolGenerationFailure
from .specs import UserToolRequirement


class RequestMetadata(BaseModel):
    """Optional request metadata."""
    sessionId: Optional[str] = Field(None, description="Optional session tracking")
    clientId: Optional[str] = Field(None, description="Client identifier")


class ToolGenerationRequest(BaseModel):
    """Request model matching design spec."""
    toolRequirements: List[UserToolRequirement]
    metadata: Optional[RequestMetadata] = None


class JobProgress(BaseModel):
    """Job progress information."""
    total: int = Field(..., description="Total tools to generate")
    completed: int = Field(..., description="Successfully generated")
    failed: int = Field(..., description="Failed generations")
    inProgress: int = Field(..., description="Currently being generated")
    currentTool: Optional[str] = Field(None, description="Name of tool currently being generated")


class ToolFile(BaseModel):
    """Generated tool file information."""
    toolId: str = Field(..., description="Unique tool identifier")
    fileName: str = Field(..., description="e.g., 'calculate_molecular_weight.py'")
    filePath: str = Field(..., description="Full path to the file")
    description: str = Field(..., description="Tool description from requirement")
    code: str = Field(..., description="Generated Python code content")
    endpoint: Optional[str] = Field(None, description="SimpleTooling HTTP endpoint URL")
    registered: bool = Field(..., description="Whether registered with SimpleTooling")
    createdAt: str = Field(..., description="ISO timestamp")


class GenerationSummary(BaseModel):
    """Job completion summary."""
    totalRequested: int
    successful: int
    failed: int


class JobResponse(BaseModel):
    """Response model matching design spec."""
    jobId: str
    status: str  # 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
    createdAt: str  # ISO timestamp
    updatedAt: str  # ISO timestamp
    progress: JobProgress
    toolFiles: Optional[List[ToolFile]] = Field(None, description="Generated tool files (only when completed)")
    failures: Optional[List[ToolGenerationFailure]] = Field(None, description="Failed tool generations")
    summary: Optional[GenerationSummary] = Field(None, description="Job summary (only when completed)")
