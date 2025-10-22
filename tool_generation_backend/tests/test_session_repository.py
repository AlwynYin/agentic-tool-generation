"""
Unit tests for SessionRepository.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
from datetime import datetime, timezone

from app.models.session import Session, SessionStatus
from app.repositories.session_repository import SessionRepository


@pytest.mark.asyncio
async def test_create_session(session_repository, sample_session_data, mock_object_id):
    """Test creating a new session."""
    # Given
    session_repository.collection.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id=mock_object_id)
    )

    # When
    session_id = await session_repository.create(sample_session_data)

    # Then
    assert session_id == str(mock_object_id)
    session_repository.collection.insert_one.assert_called_once()

    # Verify timestamps were added
    call_args = session_repository.collection.insert_one.call_args[0][0]
    assert "created_at" in call_args
    assert "updated_at" in call_args


@pytest.mark.asyncio
async def test_get_by_id(session_repository, sample_session_data, mock_object_id):
    """Test retrieving a session by ID."""
    # Given
    session_repository.collection.find_one = AsyncMock(
        return_value={**sample_session_data, "_id": mock_object_id}
    )

    # When
    session = await session_repository.get_by_id(str(mock_object_id))

    # Then
    assert session is not None
    assert session.job_id == sample_session_data["job_id"]
    session_repository.collection.find_one.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_id_not_found(session_repository):
    """Test retrieving a non-existent session."""
    # Given
    session_repository.collection.find_one = AsyncMock(return_value=None)

    # When
    session = await session_repository.get_by_id("nonexistent_id")

    # Then
    assert session is None


@pytest.mark.asyncio
async def test_update_status(session_repository, mock_object_id):
    """Test updating session status."""
    # Given
    session_id = str(mock_object_id)
    new_status = SessionStatus.COMPLETED

    # When
    success = await session_repository.update_status(session_id, new_status)

    # Then
    assert success is True
    session_repository.collection.update_one.assert_called_once()

    # Verify status was set correctly
    call_args = session_repository.collection.update_one.call_args[0]
    update_data = call_args[1]["$set"]
    assert update_data["status"] == SessionStatus.COMPLETED


@pytest.mark.asyncio
async def test_update_status_with_error(session_repository, mock_object_id):
    """Test updating session status with error message."""
    # Given
    session_id = str(mock_object_id)
    error_message = "Tool generation failed"

    # When
    success = await session_repository.update_status(
        session_id, SessionStatus.FAILED, error_message
    )

    # Then
    assert success is True
    call_args = session_repository.collection.update_one.call_args[0]
    update_data = call_args[1]["$set"]
    assert update_data["status"] == SessionStatus.FAILED
    assert update_data["error_message"] == error_message


@pytest.mark.asyncio
async def test_add_tool_id(session_repository, mock_object_id):
    """Test adding a tool ID to session."""
    # Given
    session_id = str(mock_object_id)
    tool_id = "tool_123"

    # When
    success = await session_repository.add_tool_id(session_id, tool_id)

    # Then
    assert success is True
    session_repository.collection.update_one.assert_called_once()

    # Verify $push operation
    call_args = session_repository.collection.update_one.call_args[0]
    assert call_args[1]["$push"]["tool_ids"] == tool_id


@pytest.mark.asyncio
async def test_add_tool_id_failure(session_repository, mock_object_id):
    """Test handling failure when adding tool ID."""
    # Given
    session_repository.collection.update_one = AsyncMock(
        return_value=MagicMock(modified_count=0)
    )

    # When
    success = await session_repository.add_tool_id("session_id", "tool_id")

    # Then
    assert success is False


@pytest.mark.asyncio
async def test_get_sessions_by_user(session_repository, sample_session_data):
    """Test retrieving sessions by user ID."""
    # Given
    user_id = "user_test"
    find_cursor = AsyncMock()
    find_cursor.sort = MagicMock(return_value=find_cursor)
    find_cursor.limit = MagicMock(return_value=find_cursor)
    find_cursor.to_list = AsyncMock(return_value=[sample_session_data])

    session_repository.collection.find = MagicMock(return_value=find_cursor)

    # When
    sessions = await session_repository.get_sessions_by_user(user_id, limit=50)

    # Then
    assert len(sessions) > 0
    session_repository.collection.find.assert_called_with({"user_id": user_id})


@pytest.mark.asyncio
async def test_get_sessions_by_status(session_repository, sample_session_data):
    """Test retrieving sessions by status."""
    # Given
    status = SessionStatus.COMPLETED
    find_cursor = AsyncMock()
    find_cursor.sort = MagicMock(return_value=find_cursor)
    find_cursor.limit = MagicMock(return_value=find_cursor)
    find_cursor.to_list = AsyncMock(return_value=[sample_session_data])

    session_repository.collection.find = MagicMock(return_value=find_cursor)

    # When
    sessions = await session_repository.get_sessions_by_status(status)

    # Then
    assert len(sessions) >= 0
    session_repository.collection.find.assert_called_with({"status": status.value})


@pytest.mark.asyncio
async def test_get_active_sessions(session_repository):
    """Test retrieving active (non-terminal) sessions."""
    # Given
    find_cursor = AsyncMock()
    find_cursor.sort = MagicMock(return_value=find_cursor)
    find_cursor.limit = MagicMock(return_value=find_cursor)
    find_cursor.to_list = AsyncMock(return_value=[])

    session_repository.collection.find = MagicMock(return_value=find_cursor)

    # When
    sessions = await session_repository.get_active_sessions()

    # Then
    # Verify query includes non-terminal statuses
    call_args = session_repository.collection.find.call_args[0][0]
    assert "$in" in call_args["status"]
    active_statuses = call_args["status"]["$in"]
    assert SessionStatus.PENDING.value in active_statuses
    assert SessionStatus.COMPLETED.value not in active_statuses
    assert SessionStatus.FAILED.value not in active_statuses


@pytest.mark.asyncio
async def test_ensure_indexes(session_repository):
    """Test index creation."""
    # When
    await session_repository.ensure_indexes()

    # Then
    # Verify multiple indexes were created
    assert session_repository.collection.create_index.call_count >= 4
