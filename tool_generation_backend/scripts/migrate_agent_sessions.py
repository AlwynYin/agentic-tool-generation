#!/usr/bin/env python3
"""
Migration script to move agent_sessions collection from tool_generation_service
database to agent_browser database.

This script should be run after updating the code to use the consolidated database configuration.

Usage:
    python scripts/migrate_agent_sessions.py [--mongodb-url MONGODB_URL]
"""

import asyncio
import argparse
import logging
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def migrate_agent_sessions(mongodb_url: str, source_db: str = "tool_generation_service", target_db: str = "agent_browser"):
    """
    Migrate agent_sessions collection from source database to target database.

    Args:
        mongodb_url: MongoDB connection URL
        source_db: Source database name
        target_db: Target database name
    """
    client = None
    try:
        # Connect to MongoDB
        logger.info(f"Connecting to MongoDB at {mongodb_url}")
        client = AsyncIOMotorClient(mongodb_url)

        # Test connection
        await client.admin.command("ping")
        logger.info("✅ Connected to MongoDB")

        # Get source and target databases
        source_database = client[source_db]
        target_database = client[target_db]

        # Check if source collection exists
        source_collections = await source_database.list_collection_names()
        if "agent_sessions" not in source_collections:
            logger.info(f"ℹ️  No agent_sessions collection found in {source_db} database")
            logger.info("   Nothing to migrate.")
            return

        # Check if target collection already exists
        target_collections = await target_database.list_collection_names()
        if "agent_sessions" in target_collections:
            logger.warning(f"⚠️  agent_sessions collection already exists in {target_db} database")
            response = input("   Do you want to merge the collections? (yes/no): ")
            if response.lower() != "yes":
                logger.info("Migration cancelled")
                return

        # Count documents in source collection
        source_collection = source_database["agent_sessions"]
        doc_count = await source_collection.count_documents({})
        logger.info(f"📊 Found {doc_count} documents in {source_db}.agent_sessions")

        if doc_count == 0:
            logger.info("   No documents to migrate.")
            # Remove empty collection from source
            await source_database.drop_collection("agent_sessions")
            logger.info(f"✅ Dropped empty collection from {source_db}")
            return

        # Copy documents to target database
        logger.info(f"🔄 Copying documents from {source_db} to {target_db}...")
        target_collection = target_database["agent_sessions"]

        documents = []
        async for doc in source_collection.find():
            documents.append(doc)

        if documents:
            # Insert in batches
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                await target_collection.insert_many(batch, ordered=False)
                logger.info(f"   Copied {min(i + batch_size, len(documents))}/{len(documents)} documents")

        # Verify migration
        target_count = await target_collection.count_documents({})
        logger.info(f"📊 Target database now has {target_count} documents")

        if target_count == doc_count:
            logger.info("✅ Migration successful!")

            # Ask before deleting source collection
            response = input(f"\nDelete agent_sessions collection from {source_db}? (yes/no): ")
            if response.lower() == "yes":
                await source_database.drop_collection("agent_sessions")
                logger.info(f"✅ Deleted agent_sessions from {source_db}")
            else:
                logger.info(f"ℹ️  Kept agent_sessions in {source_db} (you can delete it manually later)")
        else:
            logger.error(f"❌ Migration verification failed!")
            logger.error(f"   Expected {doc_count} documents, found {target_count}")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise
    finally:
        if client:
            client.close()
            logger.info("Closed MongoDB connection")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate agent_sessions collection between databases"
    )
    parser.add_argument(
        "--mongodb-url",
        default="mongodb://localhost:27017",
        help="MongoDB connection URL (default: mongodb://localhost:27017)"
    )
    parser.add_argument(
        "--source-db",
        default="tool_generation_service",
        help="Source database name (default: tool_generation_service)"
    )
    parser.add_argument(
        "--target-db",
        default="agent_browser",
        help="Target database name (default: agent_browser)"
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Agent Sessions Collection Migration")
    logger.info("=" * 60)
    logger.info(f"Source: {args.source_db}.agent_sessions")
    logger.info(f"Target: {args.target_db}.agent_sessions")
    logger.info(f"MongoDB URL: {args.mongodb_url}")
    logger.info("=" * 60)

    asyncio.run(migrate_agent_sessions(
        args.mongodb_url,
        args.source_db,
        args.target_db
    ))


if __name__ == "__main__":
    main()
