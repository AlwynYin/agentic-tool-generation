"""
MongoDB-based session implementation for OpenAI Agents SDK.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from agents.memory.session import SessionABC
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)


class MongoSession(SessionABC):
    """
    MongoDB-based session storage for agent conversations.

    Implements the SessionABC interface to store conversation history
    in MongoDB for persistence across agent interactions.
    """

    def __init__(self, session_id: str, mongo_url: Optional[str] = None):
        """
        Initialize MongoDB session.

        Args:
            session_id: Unique session identifier
            mongo_url: MongoDB connection URL (defaults to config)
        """
        self.session_id = session_id

        # Use config if mongo_url not provided
        if mongo_url is None:
            from app.config import get_settings
            mongo_url = get_settings().mongodb_url

        self.client = AsyncIOMotorClient(mongo_url)
        self.collection = self.client.tool_generation_service.agent_sessions

    async def get_items(self) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history from MongoDB.

        Returns:
            List of conversation items in chronological order
        """
        try:
            doc = await self.collection.find_one({"session_id": self.session_id})
            items = doc.get("conversation_items", []) if doc else []

            logger.debug(f"Retrieved {len(items)} conversation items for session {self.session_id}")
            return items

        except Exception as e:
            logger.error(f"Error retrieving conversation items for session {self.session_id}: {e}")
            return []

    async def add_items(self, items: List[Dict[str, Any]]) -> None:
        """
        Add conversation items to MongoDB.

        Args:
            items: List of conversation items to add
        """
        if not items:
            return

        try:
            # Add timestamp to each item
            timestamped_items = []
            for item in items:
                item_with_timestamp = {
                    **item,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                timestamped_items.append(item_with_timestamp)

            await self.collection.update_one(
                {"session_id": self.session_id},
                {
                    "$push": {"conversation_items": {"$each": timestamped_items}},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                },
                upsert=True
            )

            logger.debug(f"Added {len(items)} conversation items to session {self.session_id}")

        except Exception as e:
            logger.error(f"Error adding conversation items to session {self.session_id}: {e}")
            raise

    async def pop_item(self) -> Optional[Dict[str, Any]]:
        """
        Remove and return the most recent conversation item.

        Returns:
            Most recent conversation item or None if empty
        """
        try:
            # Get the most recent item first
            doc = await self.collection.find_one({"session_id": self.session_id})
            if not doc or not doc.get("conversation_items"):
                return None

            items = doc["conversation_items"]
            if not items:
                return None

            most_recent = items[-1]

            # Remove the most recent item
            await self.collection.update_one(
                {"session_id": self.session_id},
                {
                    "$pop": {"conversation_items": 1},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )

            logger.debug(f"Popped conversation item from session {self.session_id}")
            return most_recent

        except Exception as e:
            logger.error(f"Error popping conversation item from session {self.session_id}: {e}")
            return None

    async def clear_session(self) -> None:
        """
        Clear all conversation history for the session.
        """
        try:
            await self.collection.update_one(
                {"session_id": self.session_id},
                {
                    "$set": {
                        "conversation_items": [],
                        "updated_at": datetime.now(timezone.utc),
                        "cleared_at": datetime.now(timezone.utc)
                    }
                }
            )

            logger.info(f"Cleared conversation history for session {self.session_id}")

        except Exception as e:
            logger.error(f"Error clearing session {self.session_id}: {e}")
            raise

    async def get_session_info(self) -> Dict[str, Any]:
        """
        Get session metadata and statistics.

        Returns:
            Dictionary with session information
        """
        try:
            doc = await self.collection.find_one({"session_id": self.session_id})
            if not doc:
                return {
                    "session_id": self.session_id,
                    "exists": False,
                    "item_count": 0
                }

            items = doc.get("conversation_items", [])
            return {
                "session_id": self.session_id,
                "exists": True,
                "item_count": len(items),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "cleared_at": doc.get("cleared_at")
            }

        except Exception as e:
            logger.error(f"Error getting session info for {self.session_id}: {e}")
            return {
                "session_id": self.session_id,
                "exists": False,
                "error": str(e)
            }

    async def close(self) -> None:
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()