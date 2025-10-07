"""
Base repository providing generic CRUD operations for MongoDB collections.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection
import logging

from app.database import get_database
from app.models.base import DatabaseModel

# Type variable for model types
T = TypeVar('T', bound=DatabaseModel)

logger = logging.getLogger(__name__)


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository with common CRUD operations."""

    def __init__(self, model_class: Type[T], collection_name: str):
        """
        Initialize repository with model class and collection name.

        Args:
            model_class: Pydantic model class for this repository
            collection_name: MongoDB collection name
        """
        self.model_class = model_class
        self.collection_name = collection_name
        self._collection: Optional[AsyncIOMotorCollection] = None

    @property
    def collection(self) -> AsyncIOMotorCollection:
        """Get the MongoDB collection, initializing if needed."""
        if self._collection is None:
            database = get_database()
            self._collection = database[self.collection_name]
        return self._collection

    async def create(self, data: Dict[str, Any]) -> str:
        """
        Create a new document.

        Args:
            data: Document data as dictionary

        Returns:
            str: Created document ID
        """
        try:
            # Add timestamps
            now = datetime.now(timezone.utc)
            data.update({
                "created_at": now,
                "updated_at": now
            })

            # Insert document
            result = await self.collection.insert_one(data)
            document_id = str(result.inserted_id)

            logger.info(f"Created {self.collection_name} document: {document_id}")
            return document_id

        except Exception as e:
            logger.error(f"Failed to create {self.collection_name} document: {e}")
            raise

    async def get_by_id(self, document_id: str) -> Optional[T]:
        """
        Get document by ID.

        Args:
            document_id: Document ID

        Returns:
            Optional[T]: Document model instance or None if not found
        """
        try:
            # Convert string ID to ObjectId for MongoDB query
            object_id = ObjectId(document_id)
            document = await self.collection.find_one({"_id": object_id})

            if document is None:
                return None

            # Convert MongoDB document to model
            return self._document_to_model(document)

        except Exception as e:
            logger.error(f"Failed to get {self.collection_name} by ID {document_id}: {e}")
            return None

    async def update(self, document_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update document by ID.

        Args:
            document_id: Document ID
            update_data: Fields to update

        Returns:
            bool: True if document was updated, False otherwise
        """
        try:
            # Add updated timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)

            # Convert string ID to ObjectId
            object_id = ObjectId(document_id)

            # Update document
            result = await self.collection.update_one(
                {"_id": object_id},
                {"$set": update_data}
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Updated {self.collection_name} document: {document_id}")
            else:
                logger.warning(f"No {self.collection_name} document updated for ID: {document_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to update {self.collection_name} document {document_id}: {e}")
            return False

    async def delete(self, document_id: str) -> bool:
        """
        Delete document by ID.

        Args:
            document_id: Document ID

        Returns:
            bool: True if document was deleted, False otherwise
        """
        try:
            # Convert string ID to ObjectId
            object_id = ObjectId(document_id)

            # Delete document
            result = await self.collection.delete_one({"_id": object_id})

            success = result.deleted_count > 0
            if success:
                logger.info(f"Deleted {self.collection_name} document: {document_id}")
            else:
                logger.warning(f"No {self.collection_name} document deleted for ID: {document_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to delete {self.collection_name} document {document_id}: {e}")
            return False

    async def find_by_field(self, field_name: str, field_value: Any, limit: Optional[int] = None) -> List[T]:
        """
        Find documents by field value.

        Args:
            field_name: Field name to search by
            field_value: Field value to match
            limit: Maximum number of documents to return

        Returns:
            List[T]: List of matching document models
        """
        try:
            query = {field_name: field_value}
            cursor = self.collection.find(query)

            if limit is not None:
                cursor = cursor.limit(limit)

            documents = await cursor.to_list(length=None)
            return [self._document_to_model(doc) for doc in documents]

        except Exception as e:
            logger.error(f"Failed to find {self.collection_name} by {field_name}={field_value}: {e}")
            return []

    async def find_many(self, query: Dict[str, Any], limit: Optional[int] = None, sort_by: Optional[str] = None) -> List[T]:
        """
        Find multiple documents with custom query.

        Args:
            query: MongoDB query dictionary
            limit: Maximum number of documents to return
            sort_by: Field name to sort by (descending order)

        Returns:
            List[T]: List of matching document models
        """
        try:
            cursor = self.collection.find(query)

            if sort_by:
                cursor = cursor.sort(sort_by, -1)  # Descending order

            if limit is not None:
                cursor = cursor.limit(limit)

            documents = await cursor.to_list(length=None)
            return [self._document_to_model(doc) for doc in documents]

        except Exception as e:
            logger.error(f"Failed to find {self.collection_name} with query {query}: {e}")
            return []

    async def count(self, query: Optional[Dict[str, Any]] = None) -> int:
        """
        Count documents matching query.

        Args:
            query: MongoDB query dictionary (empty for all documents)

        Returns:
            int: Number of matching documents
        """
        try:
            if query is None:
                query = {}

            count = await self.collection.count_documents(query)
            return count

        except Exception as e:
            logger.error(f"Failed to count {self.collection_name} documents: {e}")
            return 0

    def _document_to_model(self, document: Dict[str, Any]) -> T:
        """
        Convert MongoDB document to Pydantic model.

        Args:
            document: MongoDB document dictionary

        Returns:
            T: Pydantic model instance
        """
        # Convert ObjectId to string for model
        if "_id" in document:
            document["id"] = str(document["_id"])
            del document["_id"]

        # Convert ObjectId arrays to string arrays (e.g., tool_ids)
        if "tool_ids" in document and document["tool_ids"]:
            document["tool_ids"] = [str(oid) for oid in document["tool_ids"]]

        # Create model instance
        return self.model_class(**document)

    async def ensure_indexes(self):
        """Ensure collection indexes are created. Override in subclasses."""
        pass