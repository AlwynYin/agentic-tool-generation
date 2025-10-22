"""
Unit tests for ToolRepository.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from app.models.tool import Tool, ToolStatus
from app.repositories.tool_repository import ToolRepository


@pytest.mark.asyncio
async def test_get_by_name_found(tool_repository, sample_tool):
    """Test finding a tool by name when it exists."""
    # Given
    find_cursor = AsyncMock()
    find_cursor.sort = MagicMock(return_value=find_cursor)
    find_cursor.limit = MagicMock(return_value=find_cursor)
    find_cursor.to_list = AsyncMock(return_value=[sample_tool.model_dump()])

    tool_repository.collection.find = MagicMock(return_value=find_cursor)

    # When
    tool = await tool_repository.get_by_name("calculate_molecular_weight")

    # Then
    assert tool is not None
    assert tool.name == "calculate_molecular_weight"


@pytest.mark.asyncio
async def test_get_by_name_not_found(tool_repository):
    """Test finding a tool by name when it doesn't exist."""
    # Given
    find_cursor = AsyncMock()
    find_cursor.sort = MagicMock(return_value=find_cursor)
    find_cursor.limit = MagicMock(return_value=find_cursor)
    find_cursor.to_list = AsyncMock(return_value=[])

    tool_repository.collection.find = MagicMock(return_value=find_cursor)

    # When
    tool = await tool_repository.get_by_name("nonexistent_tool")

    # Then
    assert tool is None


@pytest.mark.asyncio
async def test_serialize_tool_data(tool_repository, sample_tool_generation_result):
    """Test serializing ToolGenerationResult to MongoDB-ready dict."""
    # Given
    session_id = "session_123"
    file_path = "/path/to/tool.py"
    code = "def calculate(): pass"

    # When
    tool_data = tool_repository._serialize_tool_data(
        result=sample_tool_generation_result,
        session_id=session_id,
        file_path=file_path,
        code=code
    )

    # Then
    assert tool_data["name"] == sample_tool_generation_result.name
    assert tool_data["file_name"] == sample_tool_generation_result.file_name
    assert tool_data["file_path"] == file_path
    assert tool_data["code"] == code
    assert tool_data["session_id"] == session_id

    # Verify Pydantic models are serialized to dicts
    assert isinstance(tool_data["input_schema"], dict)
    assert isinstance(tool_data["output_schema"], dict)

    # Verify enum is converted to value
    assert tool_data["status"] == ToolStatus.DRAFT.value
    assert isinstance(tool_data["status"], str)


@pytest.mark.asyncio
async def test_create_from_generation_result(tool_repository, sample_tool_generation_result, mock_object_id):
    """Test creating a tool from ToolGenerationResult."""
    # Given
    session_id = "session_123"
    file_path = "/path/to/tool.py"
    code = "def calculate(): pass"

    tool_repository.collection.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id=mock_object_id)
    )

    # When
    tool_id = await tool_repository.create_from_generation_result(
        result=sample_tool_generation_result,
        session_id=session_id,
        file_path=file_path,
        code=code
    )

    # Then
    assert tool_id == str(mock_object_id)
    tool_repository.collection.insert_one.assert_called_once()

    # Verify serialization was correct
    call_args = tool_repository.collection.insert_one.call_args[0][0]
    assert call_args["name"] == sample_tool_generation_result.name
    assert call_args["status"] == ToolStatus.DRAFT.value


@pytest.mark.asyncio
async def test_get_by_ids(tool_repository, sample_tool, mock_object_id):
    """Test retrieving multiple tools by IDs."""
    # Given
    tool_ids = [str(mock_object_id), "tool_456"]

    tool_repository.collection.find_one = AsyncMock(
        side_effect=[
            {**sample_tool.model_dump(), "_id": mock_object_id},
            None  # Second tool not found
        ]
    )

    # When
    tools = await tool_repository.get_by_ids(tool_ids)

    # Then
    assert len(tools) == 1  # Only first tool found
    assert tools[0].name == sample_tool.name


@pytest.mark.asyncio
async def test_update_status(tool_repository, mock_object_id):
    """Test updating tool status."""
    # Given
    tool_id = str(mock_object_id)
    new_status = ToolStatus.REGISTERED

    tool_repository.collection.update_one = AsyncMock(
        return_value=MagicMock(modified_count=1)
    )

    # When
    success = await tool_repository.update_status(tool_id, new_status)

    # Then
    assert success is True
    call_args = tool_repository.collection.update_one.call_args[0]
    update_data = call_args[1]["$set"]
    assert update_data["status"] == ToolStatus.REGISTERED.value


@pytest.mark.asyncio
async def test_get_registered_tools(tool_repository, sample_tool):
    """Test retrieving registered tools."""
    # Given
    find_cursor = AsyncMock()
    find_cursor.sort = MagicMock(return_value=find_cursor)
    find_cursor.limit = MagicMock(return_value=find_cursor)
    find_cursor.to_list = AsyncMock(return_value=[sample_tool.model_dump()])

    tool_repository.collection.find = MagicMock(return_value=find_cursor)

    # When
    tools = await tool_repository.get_registered_tools(limit=10)

    # Then
    # Verify query uses correct status value
    call_args = tool_repository.collection.find.call_args[0][0]
    assert call_args["status"] == ToolStatus.REGISTERED.value


@pytest.mark.asyncio
async def test_get_tools_by_status(tool_repository):
    """Test retrieving tools by status."""
    # Given
    status = ToolStatus.DRAFT
    find_cursor = AsyncMock()
    find_cursor.sort = MagicMock(return_value=find_cursor)
    find_cursor.limit = MagicMock(return_value=find_cursor)
    find_cursor.to_list = AsyncMock(return_value=[])

    tool_repository.collection.find = MagicMock(return_value=find_cursor)

    # When
    tools = await tool_repository.get_tools_by_status(status)

    # Then
    call_args = tool_repository.collection.find.call_args[0][0]
    assert call_args["status"] == ToolStatus.DRAFT.value


@pytest.mark.asyncio
async def test_get_tools_by_session(tool_repository, sample_tool):
    """Test retrieving tools by session ID."""
    # Given
    session_id = "session_123"
    find_cursor = AsyncMock()
    find_cursor.sort = MagicMock(return_value=find_cursor)
    find_cursor.limit = MagicMock(return_value=find_cursor)
    find_cursor.to_list = AsyncMock(return_value=[sample_tool.model_dump()])

    tool_repository.collection.find = MagicMock(return_value=find_cursor)

    # When
    tools = await tool_repository.get_tools_by_session(session_id)

    # Then
    assert len(tools) > 0
    call_args = tool_repository.collection.find.call_args[0][0]
    assert call_args["session_id"] == session_id


@pytest.mark.asyncio
async def test_search_tools(tool_repository, sample_tool):
    """Test searching tools by name or description."""
    # Given
    search_term = "molecular"
    find_cursor = AsyncMock()
    find_cursor.sort = MagicMock(return_value=find_cursor)
    find_cursor.limit = MagicMock(return_value=find_cursor)
    find_cursor.to_list = AsyncMock(return_value=[sample_tool.model_dump()])

    tool_repository.collection.find = MagicMock(return_value=find_cursor)

    # When
    tools = await tool_repository.search_tools(search_term, limit=20)

    # Then
    assert len(tools) > 0
    # Verify regex search query
    call_args = tool_repository.collection.find.call_args[0][0]
    assert "$or" in call_args


@pytest.mark.asyncio
async def test_mark_tool_deprecated(tool_repository, mock_object_id):
    """Test marking a tool as deprecated."""
    # Given
    tool_id = str(mock_object_id)
    tool_repository.collection.update_one = AsyncMock(
        return_value=MagicMock(modified_count=1)
    )

    # When
    success = await tool_repository.mark_tool_deprecated(tool_id)

    # Then
    assert success is True
    call_args = tool_repository.collection.update_one.call_args[0]
    update_data = call_args[1]["$set"]
    assert update_data["status"] == ToolStatus.DEPRECATED.value


@pytest.mark.asyncio
async def test_ensure_indexes(tool_repository):
    """Test creating indexes including unique name constraint."""
    # When
    await tool_repository.ensure_indexes()

    # Then
    # Verify indexes were created
    assert tool_repository.collection.create_index.call_count >= 3

    # Verify unique index on name
    calls = tool_repository.collection.create_index.call_args_list
    unique_name_call = [call for call in calls if call[0][0] == "name" and call[1].get("unique")]
    assert len(unique_name_call) > 0
