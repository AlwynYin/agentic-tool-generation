"""
Pytest fixtures and configuration for unit tests.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from bson import ObjectId

from app.models.session import (
    Session, SessionStatus, UserToolRequirement,
    ToolGenerationResult, ParameterSpec, OutputSpec
)
from app.models.tool import Tool, ToolStatus
from app.repositories.session_repository import SessionRepository
from app.repositories.tool_repository import ToolRepository
from app.services.session_service import SessionService
from app.services.tool_service import ToolService


@pytest.fixture
def mock_object_id():
    """Generate a mock ObjectId."""
    return ObjectId()


@pytest.fixture
def mock_collection():
    """Mock MongoDB collection with common operations."""
    collection = AsyncMock()

    # Mock insert_one
    collection.insert_one = AsyncMock(return_value=MagicMock(
        inserted_id=ObjectId(),
        acknowledged=True
    ))

    # Mock find_one
    collection.find_one = AsyncMock(return_value=None)

    # Mock update_one
    collection.update_one = AsyncMock(return_value=MagicMock(
        modified_count=1,
        matched_count=1
    ))

    # Mock delete_one
    collection.delete_one = AsyncMock(return_value=MagicMock(
        deleted_count=1
    ))

    # Mock find
    find_cursor = AsyncMock()
    find_cursor.sort = MagicMock(return_value=find_cursor)
    find_cursor.limit = MagicMock(return_value=find_cursor)
    find_cursor.to_list = AsyncMock(return_value=[])
    collection.find = MagicMock(return_value=find_cursor)

    # Mock count_documents
    collection.count_documents = AsyncMock(return_value=0)

    # Mock create_index
    collection.create_index = AsyncMock(return_value="index_name")

    return collection


@pytest.fixture
def mock_database(mock_collection):
    """Mock MongoDB database."""
    database = MagicMock()
    database.__getitem__ = MagicMock(return_value=mock_collection)
    return database


@pytest.fixture
def sample_user_tool_requirement():
    """Sample UserToolRequirement for testing."""
    return UserToolRequirement(
        description="Calculate molecular weight from SMILES using RDKit",
        input="SMILES string of the molecule",
        output="molecular weight in g/mol"
    )


@pytest.fixture
def sample_tool_generation_result():
    """Sample ToolGenerationResult for testing."""
    return ToolGenerationResult(
        success=True,
        name="calculate_molecular_weight",
        file_name="calculate_molecular_weight.py",
        description="Calculate molecular weight from SMILES using RDKit",
        input_schema=[
            ParameterSpec(
                name="smiles",
                type="str",
                description="SMILES string"
            )
        ],
        output_schema=OutputSpec(
            type="float",
            description="Molecular weight in g/mol"
        ),
        dependencies=["rdkit"]
    )


@pytest.fixture
def sample_session_data():
    """Sample session data for testing."""
    return {
        "job_id": "job_test123",
        "user_id": "user_test",
        "operation_type": "generate",
        "status": SessionStatus.PENDING.value,
        "tool_requirements": [
            {
                "description": "Calculate molecular weight",
                "input": "SMILES",
                "output": "molecular weight"
            }
        ],
        "tool_ids": []
    }


@pytest.fixture
def sample_tool():
    """Sample Tool model for testing."""
    return Tool(
        id="tool_123",
        name="calculate_molecular_weight",
        file_name="calculate_molecular_weight.py",
        file_path="/path/to/tool.py",
        description="Calculate molecular weight",
        code="def calculate_mw(smiles): pass",
        input_schema={
            "smiles": ParameterSpec(
                name="smiles",
                type="str",
                description="SMILES string"
            ).model_dump()
        },
        output_schema=OutputSpec(
            type="float",
            description="Molecular weight"
        ).model_dump(),
        dependencies=["rdkit"],
        test_cases=[],
        status=ToolStatus.DRAFT,
        session_id="session_123",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_session(sample_user_tool_requirement):
    """Sample Session model for testing."""
    return Session(
        id="session_123",
        job_id="job_test123",
        user_id="user_test",
        operation_type="generate",
        status=SessionStatus.PENDING,
        tool_requirements=[sample_user_tool_requirement],
        tool_ids=[],  # Empty by default
        error_message=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def session_repository(mock_collection):
    """SessionRepository with mocked collection."""
    repo = SessionRepository()
    repo._collection = mock_collection  # Set private attribute directly
    return repo


@pytest.fixture
def tool_repository(mock_collection):
    """ToolRepository with mocked collection."""
    repo = ToolRepository()
    repo._collection = mock_collection  # Set private attribute directly
    return repo


@pytest.fixture
def session_service(session_repository, tool_repository):
    """SessionService with mocked repositories."""
    service = SessionService(
        session_repo=session_repository,
        tool_repo=tool_repository
    )
    # Mock the pipeline to avoid OpenAI calls
    service.pipeline = AsyncMock()
    return service


@pytest.fixture
def tool_service(tool_repository):
    """ToolService with mocked repository."""
    return ToolService(tool_repo=tool_repository)
