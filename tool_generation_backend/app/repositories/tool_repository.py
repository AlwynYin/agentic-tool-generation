"""
Tool repository for tool storage and metadata management.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import logging
import os

from .base import BaseRepository
from app.models.tool import Tool, ToolStatus
from app.models.tool_generation import ToolGenerationResult

logger = logging.getLogger(__name__)


class ToolRepository(BaseRepository[Tool]):
    """Repository for tool metadata and file management."""

    def __init__(self):
        super().__init__(Tool, "tools")

    async def get_by_name(self, name: str) -> Optional[Tool]:
        """
        Get tool by name for deduplication check.

        Args:
            name: Tool name

        Returns:
            Optional[Tool]: Tool if found, None otherwise
        """
        try:
            tools = await self.find_by_field("name", name, limit=1)
            return tools[0] if tools else None
        except Exception as e:
            logger.error(f"Failed to get tool by name {name}: {e}")
            return None

    def _serialize_tool_data(
        self,
        result: ToolGenerationResult,
        task_id: str,
        file_path: str,
        code: str,
        test_code: Optional[str] = None,
        implementation_plan: Optional[str] = None,
        function_spec: Optional[str] = None,
        contracts_plan: Optional[str] = None,
        validation_rules: Optional[str] = None,
        test_requirements: Optional[str] = None,
        search_results: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Serialize ToolGenerationResult to MongoDB-ready dictionary.

        Args:
            result: Tool generation result from agent
            task_id: Task ID that generated this tool
            file_path: Path where tool file is stored
            code: Python code implementation
            test_code: Test file contents (optional)
            implementation_plan: Implementation plan file contents (optional)
            function_spec: Function specification file contents (optional)
            contracts_plan: Contracts file contents (optional)
            validation_rules: Validation rules file contents (optional)
            test_requirements: Test requirements file contents (optional)
            search_results: API exploration results (optional)

        Returns:
            Dict ready for MongoDB insertion
        """
        data = {
            "name": result.name,
            "file_name": result.file_name,
            "file_path": file_path,
            "description": result.description,
            "code": code,
            "input_schema": {spec.name: spec.model_dump() for spec in result.input_schema},
            "output_schema": result.output_schema.model_dump(),
            "dependencies": result.dependencies,
            "test_cases": [],  # Will be added later if needed
            "status": ToolStatus.DRAFT.value,  # Serialize enum to string
            "task_id": task_id,
            # File contents
            "test_code": test_code,
            "implementation_plan": implementation_plan,
            "function_spec": function_spec,
            "contracts_plan": contracts_plan,
            "validation_rules": validation_rules,
            "test_requirements": test_requirements,
            "search_results": search_results
        }
        return data

    async def create_from_generation_result(
        self,
        result: ToolGenerationResult,
        task_id: str,
        file_path: str,
        code: str,
        test_code: Optional[str] = None,
        implementation_plan: Optional[str] = None,
        function_spec: Optional[str] = None,
        contracts_plan: Optional[str] = None,
        validation_rules: Optional[str] = None,
        test_requirements: Optional[str] = None,
        search_results: Optional[str] = None
    ) -> str:
        """
        Create a new tool from a generation result.

        Args:
            result: Tool generation result from agent
            task_id: Task ID that generated this tool
            file_path: Path where tool file is stored
            code: Python code implementation
            test_code: Test file contents (optional)
            implementation_plan: Implementation plan file contents (optional)
            function_spec: Function specification file contents (optional)
            contracts_plan: Contracts file contents (optional)
            validation_rules: Validation rules file contents (optional)
            test_requirements: Test requirements file contents (optional)
            search_results: API exploration results (optional)

        Returns:
            str: Created tool ID
        """
        try:
            tool_data = self._serialize_tool_data(
                result, task_id, file_path, code,
                test_code=test_code,
                implementation_plan=implementation_plan,
                function_spec=function_spec,
                contracts_plan=contracts_plan,
                validation_rules=validation_rules,
                test_requirements=test_requirements,
                search_results=search_results
            )
            tool_id = await self.create(tool_data)
            logger.info(f"Created tool {result.name} with ID {tool_id}")
            return tool_id

        except Exception as e:
            logger.error(f"Failed to create tool from generation result: {e}")
            raise

    async def get_by_ids(self, tool_ids: List[str]) -> List[Tool]:
        """
        Get multiple tools by their IDs.

        Args:
            tool_ids: List of tool IDs (as strings)

        Returns:
            List[Tool]: List of tools (may be shorter than input if some not found)
        """
        try:
            tools = []
            for tool_id in tool_ids:
                tool = await self.get_by_id(tool_id)
                if tool:
                    tools.append(tool)
            return tools
        except Exception as e:
            logger.error(f"Failed to get tools by IDs: {e}")
            return []


    async def update_status(self, tool_id: str, new_status: ToolStatus) -> bool:
        """
        Update tool status.

        Args:
            tool_id: Tool ID
            new_status: New ToolStatus enum value

        Returns:
            bool: True if updated successfully
        """
        update_data = {
            "status": new_status.value
        }

        return await self.update(tool_id, update_data)

    async def get_tools_by_task(self, task_id: str) -> List[Tool]:
        """
        Get all tools for a specific task.

        Args:
            task_id: Task ID

        Returns:
            List[Tool]: Tools created in the task
        """
        return await self.find_by_field("task_id", task_id)

    async def get_registered_tools(self, limit: Optional[int] = None) -> List[Tool]:
        """
        Get all registered tools.

        Args:
            limit: Maximum number of tools to return

        Returns:
            List[Tool]: Registered tools
        """
        return await self.find_by_field("status", ToolStatus.REGISTERED.value, limit)

    async def get_tools_by_status(self, status: ToolStatus, limit: Optional[int] = None) -> List[Tool]:
        """
        Get tools by status.

        Args:
            status: ToolStatus enum value
            limit: Maximum number of tools to return

        Returns:
            List[Tool]: Tools with specified status
        """
        return await self.find_by_field("status", status.value, limit)

    async def search_tools(self, search_term: str, limit: int = 20) -> List[Tool]:
        """
        Search tools by name or description.

        Args:
            search_term: Term to search for in name and description
            limit: Maximum number of tools to return

        Returns:
            List[Tool]: Matching tools
        """
        try:
            # Create text search query
            query = {
                "$or": [
                    {"name": {"$regex": search_term, "$options": "i"}},
                    {"description": {"$regex": search_term, "$options": "i"}}
                ]
            }

            return await self.find_many(query, limit=limit, sort_by="created_at")

        except Exception as e:
            logger.error(f"Failed to search tools with term '{search_term}': {e}")
            return []

    async def get_tool_usage_stats(self, tool_id: str) -> Dict[str, Any]:
        """
        Get usage statistics for a tool.

        Args:
            tool_id: Tool metadata ID

        Returns:
            Dict[str, Any]: Usage statistics
        """
        try:
            # Get tool metadata
            tool = await self.get_by_id(tool_id)
            if not tool:
                return {}

            # Count executions from execution results collection
            execution_collection = self.collection.database["execution_results"]
            total_executions = await execution_collection.count_documents({"tool_id": tool_id})

            # Count successful executions
            successful_executions = await execution_collection.count_documents({
                "tool_id": tool_id,
                "success": True
            })

            # Get recent executions
            recent_executions = await execution_collection.find(
                {"tool_id": tool_id}
            ).sort("created_at", -1).limit(10).to_list(length=10)

            return {
                "tool_id": tool_id,
                "tool_name": tool.name,
                "total_executions": total_executions,
                "successful_executions": successful_executions,
                "success_rate": successful_executions / total_executions if total_executions > 0 else 0,
                "recent_executions": [
                    {
                        "execution_id": str(exec_result["_id"]),
                        "success": exec_result.get("success", False),
                        "created_at": exec_result.get("created_at"),
                        "execution_time_ms": exec_result.get("execution_time_ms")
                    }
                    for exec_result in recent_executions
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get usage stats for tool {tool_id}: {e}")
            return {}

    async def mark_tool_deprecated(self, tool_id: str) -> bool:
        """
        Mark a tool as deprecated.

        Args:
            tool_id: Tool ID

        Returns:
            bool: True if updated successfully
        """
        return await self.update_status(tool_id, ToolStatus.DEPRECATED)

    async def ensure_indexes(self):
        """Create indexes for optimal query performance."""
        try:
            # Unique index for name (deduplication)
            await self.collection.create_index("name", unique=True)

            # Index for task queries
            await self.collection.create_index("task_id")

            # Index for status
            await self.collection.create_index("status")

            # Text index for search functionality
            await self.collection.create_index([
                ("name", "text"),
                ("description", "text")
            ])

            logger.info("Tool repository indexes created successfully")

        except Exception as e:
            logger.error(f"Failed to create tool repository indexes: {e}")
