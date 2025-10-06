"""
MongoDB database connection and setup using Motor (async driver).
Handles connection initialization, database setup, and index creation.
"""

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError


# Global database client and database instances
_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None


async def init_database(mongodb_url: str, database_name: str = "agent_browser") -> None:
    """
    Initialize MongoDB connection and setup database.

    Args:
        mongodb_url: MongoDB connection URL
        database_name: Name of the database to use

    Raises:
        ConnectionFailure: If unable to connect to MongoDB
    """
    global _client, _database

    try:
        # Create MongoDB client
        _client = AsyncIOMotorClient(
            mongodb_url,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            maxPoolSize=10,
            minPoolSize=1
        )

        # Test the connection
        await _client.admin.command("ping")
        logging.info(f"✅ Connected to MongoDB at {mongodb_url}")

        # Get database instance
        _database = _client[database_name]
        logging.info(f"✅ Using database: {database_name}")

        # Create indexes for performance
        await _create_indexes()
        logging.info("✅ Database indexes created")

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logging.error(f"❌ Failed to connect to MongoDB: {e}")
        raise ConnectionFailure(f"Unable to connect to MongoDB at {mongodb_url}: {e}")
    except Exception as e:
        logging.error(f"❌ Unexpected error during database initialization: {e}")
        raise


async def _create_indexes() -> None:
    """Create database indexes for optimal performance."""
    if _database is None:
        return

    try:
        # Import repositories here to avoid circular imports
        from app.repositories.session_repository import SessionRepository
        from app.repositories.tool_repository import ToolRepository

        # Create repository instances
        session_repo = SessionRepository()
        tool_repo = ToolRepository()

        # Ensure indexes for each collection
        await session_repo.ensure_indexes()
        await tool_repo.ensure_indexes()

        logging.info("✅ All database indexes created successfully")

    except Exception as e:
        logging.warning(f"⚠️  Warning: Could not create some indexes: {e}")


def get_database() -> AsyncIOMotorDatabase:
    """
    Get the database instance.

    Returns:
        The MongoDB database instance

    Raises:
        RuntimeError: If database is not initialized
    """
    if _database is None:
        raise RuntimeError(
            "Database not initialized. Call init_database() first."
        )
    return _database


def get_client() -> AsyncIOMotorClient:
    """
    Get the MongoDB client instance.

    Returns:
        The MongoDB client instance

    Raises:
        RuntimeError: If client is not initialized
    """
    if _client is None:
        raise RuntimeError(
            "Database client not initialized. Call init_database() first."
        )
    return _client


async def close_database_connection() -> None:
    """Close the database connection."""
    global _client
    if _client:
        _client.close()
        logging.info("✅ Database connection closed")


async def ping_database() -> bool:
    """
    Ping the database to check connectivity.

    Returns:
        True if database is reachable, False otherwise
    """
    try:
        if _client:
            await _client.admin.command("ping")
            return True
    except Exception as e:
        logging.error(f"Database ping failed: {e}")
    return False


async def get_database_stats() -> dict:
    """
    Get database statistics.

    Returns:
        Dictionary containing database statistics
    """
    if _database is None:
        return {"error": "Database not initialized"}

    try:
        stats = await _database.command("dbStats")
        return {
            "database": stats.get("db"),
            "collections": stats.get("collections", 0),
            "dataSize": stats.get("dataSize", 0),
            "storageSize": stats.get("storageSize", 0),
            "indexes": stats.get("indexes", 0),
            "indexSize": stats.get("indexSize", 0)
        }
    except Exception as e:
        logging.error(f"Failed to get database stats: {e}")
        return {"error": str(e)}