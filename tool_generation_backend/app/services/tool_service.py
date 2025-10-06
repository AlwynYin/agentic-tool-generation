"""
Tool service for tool management, generation, and registration.
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import logging
from datetime import datetime, timezone

from app.models.tool import (
    Tool, ToolGenerationRequest, ToolGenerationResponse,
    ToolRegistrationRequest, ToolRegistrationResponse,
    ToolExecutionRequest, ToolExecutionResponse
)
from app.repositories.tool_repository import ToolRepository

logger = logging.getLogger(__name__)


class ToolService:
    """This class is used for later tool running and testing"""

    def __init__(
        self,
        tool_repo: ToolRepository,
    ):
        """
        Initialize tool service.

        Args:
            tool_repo: Tool repository
        """
        self.tool_repo = tool_repo