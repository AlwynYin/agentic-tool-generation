"""
Unit tests for SessionService.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from bson import ObjectId

from app.models.session import SessionStatus
from app.models.tool import Tool, ToolStatus
from app.services.session_service import SessionService


@pytest.mark.asyncio
async def test_create_session(session_service, sample_user_tool_requirement, mock_object_id):
    """Test creating a new session."""
    # Given
    job_id = "job_test123"
    user_id = "user_test"
    tool_requirements = [sample_user_tool_requirement]

    session_service.session_repo.create = AsyncMock(return_value=str(mock_object_id))

    # When
    session_id = await session_service.create_session(
        job_id=job_id,
        user_id=user_id,
        tool_requirements=tool_requirements,
        operation_type="generate"
    )

    # Then
    assert session_id == str(mock_object_id)
    session_service.session_repo.create.assert_called_once()

    # Verify session data structure
    call_args = session_service.session_repo.create.call_args[0][0]
    assert call_args["job_id"] == job_id
    assert call_args["user_id"] == user_id
    assert call_args["status"] == SessionStatus.PENDING


@pytest.mark.asyncio
async def test_get_session(session_service, sample_session, mock_object_id):
    """Test retrieving a session."""
    # Given
    session_service.session_repo.get_by_id = AsyncMock(return_value=sample_session)

    # When
    session = await session_service.get_session(str(mock_object_id))

    # Then
    assert session is not None
    assert session.job_id == sample_session.job_id


@pytest.mark.asyncio
async def test_get_session_tools(session_service, sample_session, sample_tool):
    """Test fetching tools from tools collection via tool_ids."""
    # Given
    tool_id = "tool_123"

    session_service.session_repo.get_by_id = AsyncMock(
        return_value=sample_session
    )
    session_service.tool_repo.get_by_ids = AsyncMock(return_value=[sample_tool])
    sample_session.tool_ids = [tool_id]

    # When
    tools = await session_service.get_session_tools("session_123")

    # Then
    assert len(tools) == 1
    assert tools[0].name == sample_tool.name
    session_service.tool_repo.get_by_ids.assert_called_once_with([tool_id])


@pytest.mark.asyncio
async def test_get_session_tools_empty(session_service, sample_session):
    """Test fetching tools when session has no tool_ids."""
    # Given
    sample_session.tool_ids = []
    session_service.session_repo.get_by_id = AsyncMock(return_value=sample_session)

    # When
    tools = await session_service.get_session_tools("session_123")

    # Then
    assert len(tools) == 0
    session_service.tool_repo.get_by_ids.assert_not_called()


@pytest.mark.asyncio
async def test_store_tool_specs_new_tool(session_service, sample_tool_generation_result):
    """Test storing tool specs when tool doesn't exist (creates new)."""
    # Given
    session_id = "session_123"
    tool_results = [sample_tool_generation_result]

    # Mock: Tool doesn't exist
    session_service.tool_repo.get_by_name = AsyncMock(return_value=None)
    session_service.tool_repo.create_from_generation_result = AsyncMock(return_value="tool_new_id")
    session_service.session_repo.add_tool_id = AsyncMock(return_value=True)

    # Mock file reading
    mock_file_content = "def calculate_mw(): pass"
    with patch("builtins.open", mock_open(read_data=mock_file_content)):
        # When
        await session_service._store_tool_specs(session_id, tool_results)

    # Then
    # Should create new tool
    session_service.tool_repo.create_from_generation_result.assert_called_once()
    call_args = session_service.tool_repo.create_from_generation_result.call_args[1]
    assert call_args["result"] == sample_tool_generation_result
    assert call_args["session_id"] == session_id
    assert call_args["code"] == mock_file_content

    # Should add tool_id to session
    session_service.session_repo.add_tool_id.assert_called_once_with(session_id, "tool_new_id")


@pytest.mark.asyncio
async def test_store_tool_specs_existing_tool(session_service, sample_tool_generation_result, sample_tool):
    """Test storing tool specs when tool exists (reuses and updates session_id)."""
    # Given
    session_id = "new_session_456"
    tool_results = [sample_tool_generation_result]

    # Mock: Tool already exists
    existing_tool = sample_tool
    existing_tool.id = "tool_existing_id"
    existing_tool.session_id = "old_session_123"

    session_service.tool_repo.get_by_name = AsyncMock(return_value=existing_tool)
    session_service.tool_repo.update = AsyncMock(return_value=True)
    session_service.session_repo.add_tool_id = AsyncMock(return_value=True)

    # Mock file reading
    with patch("builtins.open", mock_open(read_data="code")):
        # When
        await session_service._store_tool_specs(session_id, tool_results)

    # Then
    # Should NOT create new tool
    session_service.tool_repo.create_from_generation_result.assert_not_called()

    # Should update existing tool's session_id
    session_service.tool_repo.update.assert_called_once_with(
        existing_tool.id,
        {"session_id": session_id}
    )

    # Should add existing tool_id to session
    session_service.session_repo.add_tool_id.assert_called_once_with(session_id, existing_tool.id)


@pytest.mark.asyncio
async def test_cancel_session(session_service, sample_session):
    """Test canceling a session."""
    # Given
    session_id = "session_123"
    reason = "User requested cancellation"

    session_service.session_repo.get_by_id = AsyncMock(return_value=sample_session)
    session_service.session_repo.update_status = AsyncMock(return_value=True)

    # When
    success = await session_service.cancel_session(session_id, reason)

    # Then
    assert success is True
    session_service.session_repo.update_status.assert_called_once()


@pytest.mark.asyncio
async def test_get_workflow_status_running(session_service):
    """Test getting workflow status for running task."""
    # Given
    session_id = "session_123"
    mock_task = AsyncMock()
    mock_task.done = MagicMock(return_value=False)

    session_service.active_workflows[session_id] = mock_task

    # When
    status = session_service.get_workflow_status(session_id)

    # Then
    assert status == "running"


@pytest.mark.asyncio
async def test_get_workflow_status_completed(session_service):
    """Test getting workflow status for completed task."""
    # Given
    session_id = "session_123"
    mock_task = AsyncMock()
    mock_task.done = MagicMock(return_value=True)
    mock_task.cancelled = MagicMock(return_value=False)
    mock_task.exception = MagicMock(return_value=None)

    session_service.active_workflows[session_id] = mock_task

    # When
    status = session_service.get_workflow_status(session_id)

    # Then
    assert status == "completed"


@pytest.mark.asyncio
async def test_get_workflow_status_failed(session_service):
    """Test getting workflow status for failed task."""
    # Given
    session_id = "session_123"
    mock_task = AsyncMock()
    mock_task.done = MagicMock(return_value=True)
    mock_task.cancelled = MagicMock(return_value=False)
    mock_task.exception = MagicMock(return_value=Exception("Task failed"))

    session_service.active_workflows[session_id] = mock_task

    # When
    status = session_service.get_workflow_status(session_id)

    # Then
    assert status == "failed"


@pytest.mark.asyncio
async def test_get_workflow_status_not_found(session_service):
    """Test getting workflow status when session not in active workflows."""
    # When
    status = session_service.get_workflow_status("nonexistent_session")

    # Then
    assert status is None
