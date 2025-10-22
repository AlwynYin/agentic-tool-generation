"""
Unit tests for ToolService.
"""

import pytest
from unittest.mock import AsyncMock

from app.services.tool_service import ToolService


@pytest.mark.asyncio
async def test_get_tool_metadata(tool_service, sample_tool):
    """Test retrieving tool metadata by ID."""
    # Given
    tool_id = "tool_123"
    tool_service.tool_repo.get_by_id = AsyncMock(return_value=sample_tool)

    # When
    tool = await tool_service.get_tool_metadata(tool_id)

    # Then
    assert tool is not None
    assert tool.name == sample_tool.name
    tool_service.tool_repo.get_by_id.assert_called_once_with(tool_id)


@pytest.mark.asyncio
async def test_get_tool_metadata_not_found(tool_service):
    """Test retrieving non-existent tool."""
    # Given
    tool_service.tool_repo.get_by_id = AsyncMock(return_value=None)

    # When
    tool = await tool_service.get_tool_metadata("nonexistent_id")

    # Then
    assert tool is None


@pytest.mark.asyncio
async def test_search_tools(tool_service, sample_tool):
    """Test searching for tools."""
    # Given
    search_term = "molecular"
    tool_service.tool_repo.search_tools = AsyncMock(return_value=[sample_tool])

    # When
    tools = await tool_service.search_tools(search_term, limit=20)

    # Then
    assert len(tools) == 1
    assert tools[0].name == sample_tool.name
    tool_service.tool_repo.search_tools.assert_called_once_with(search_term, 20)


@pytest.mark.asyncio
async def test_search_tools_no_results(tool_service):
    """Test searching with no matching tools."""
    # Given
    tool_service.tool_repo.search_tools = AsyncMock(return_value=[])

    # When
    tools = await tool_service.search_tools("nonexistent_term")

    # Then
    assert len(tools) == 0
