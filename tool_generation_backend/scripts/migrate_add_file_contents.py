#!/usr/bin/env python3
"""
Migration script to add file contents to existing Tool and ToolFailure documents.

This script:
1. Finds all Tool documents without the new file content fields
2. Reads files from disk for each tool
3. Updates the Tool document with file contents
4. Does the same for ToolFailure documents

Usage:
    python scripts/migrate_add_file_contents.py [--dry-run]
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def read_file_safe(file_path: Path) -> Optional[str]:
    """Safely read a file and return its contents."""
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
    return None


def read_task_files(tools_path: str, job_id: str, task_id: str, tool_name: str) -> Dict[str, Optional[str]]:
    """
    Read all generated files for a task.

    Args:
        tools_path: Base tools directory path
        job_id: Job ID
        task_id: Task ID
        tool_name: Tool name (without .py extension)

    Returns:
        Dict with file contents (None if file doesn't exist)
    """
    task_dir = Path(tools_path) / job_id / task_id

    files = {
        "code": None,
        "test_code": None,
        "implementation_plan": None,
        "function_spec": None,
        "contracts_plan": None,
        "validation_rules": None,
        "test_requirements": None,
        "search_results": None
    }

    if not task_dir.exists():
        logger.warning(f"Task directory not found: {task_dir}")
        return files

    # Read main tool code
    tool_file = task_dir / f"{tool_name}.py"
    files["code"] = read_file_safe(tool_file)

    # Read test file
    test_file = task_dir / "tests" / f"test_{tool_name}.py"
    files["test_code"] = read_file_safe(test_file)

    # Read plan files
    plan_dir = task_dir / "plan"
    plan_files_map = {
        "implementation_plan": "implementation_plan.txt",
        "function_spec": "function_spec.txt",
        "contracts_plan": "contracts.txt",
        "validation_rules": "validation_rules.txt",
        "test_requirements": "test_requirements.txt"
    }

    for key, filename in plan_files_map.items():
        file_path = plan_dir / filename
        files[key] = read_file_safe(file_path)

    # Read search results (find most recent api_refs file)
    searches_dir = task_dir / "searches"
    if searches_dir.exists():
        api_ref_files = list(searches_dir.glob("api_refs_*"))
        if api_ref_files:
            # Sort by modification time, get most recent
            latest_file = max(api_ref_files, key=lambda f: f.stat().st_mtime)
            files["search_results"] = read_file_safe(latest_file)

    return files


async def migrate_tools(db, tools_path: str, dry_run: bool = False):
    """Migrate Tool documents."""
    tools_collection = db["tools"]

    # Find tools that don't have the new fields (or have them as null)
    query = {
        "$or": [
            {"test_code": {"$exists": False}},
            {"test_code": None}
        ]
    }

    tools = await tools_collection.find(query).to_list(length=None)
    total = len(tools)

    logger.info(f"Found {total} tools to migrate")

    updated_count = 0
    skipped_count = 0

    for i, tool in enumerate(tools, 1):
        tool_id = str(tool["_id"])
        tool_name = tool.get("name", "unknown")
        task_id = tool.get("task_id")

        logger.info(f"[{i}/{total}] Processing tool: {tool_name} (ID: {tool_id})")

        if not task_id:
            logger.warning(f"  No task_id found, skipping")
            skipped_count += 1
            continue

        # Try to find the task to get job_id
        # Convert task_id string to ObjectId
        try:
            task_object_id = ObjectId(task_id)
        except Exception:
            logger.warning(f"  Invalid task_id format: {task_id}, skipping")
            skipped_count += 1
            continue

        tasks_collection = db["tasks"]
        task = await tasks_collection.find_one({"_id": task_object_id})

        if not task:
            logger.warning(f"  Task not found: {task_id}, skipping")
            skipped_count += 1
            continue

        job_id = task.get("job_id")
        task_id_short = task.get("task_id")

        if not job_id or not task_id_short:
            logger.warning(f"  Missing job_id or task_id, skipping")
            skipped_count += 1
            continue

        # Read files from disk
        files = read_task_files(tools_path, job_id, task_id_short, tool_name)

        # Count how many files were found
        found_files = sum(1 for v in files.values() if v is not None)
        logger.info(f"  Found {found_files}/8 files on disk")

        if found_files == 0:
            logger.warning(f"  No files found on disk, skipping")
            skipped_count += 1
            continue

        # Update the tool document
        if not dry_run:
            result = await tools_collection.update_one(
                {"_id": tool["_id"]},
                {"$set": files}
            )

            if result.modified_count > 0:
                logger.info(f"  ✓ Updated tool with {found_files} files")
                updated_count += 1
            else:
                logger.warning(f"  No changes made")
        else:
            logger.info(f"  [DRY RUN] Would update with {found_files} files")
            updated_count += 1

    logger.info(f"\nTools migration complete:")
    logger.info(f"  Updated: {updated_count}")
    logger.info(f"  Skipped: {skipped_count}")
    logger.info(f"  Total: {total}")


async def migrate_tool_failures(db, tools_path: str, dry_run: bool = False):
    """Migrate ToolFailure documents."""
    failures_collection = db["tool_failures"]

    # Find failures that don't have the new fields
    query = {
        "$or": [
            {"test_code": {"$exists": False}},
            {"test_code": None}
        ]
    }

    failures = await failures_collection.find(query).to_list(length=None)
    total = len(failures)

    logger.info(f"Found {total} tool failures to migrate")

    updated_count = 0
    skipped_count = 0

    for i, failure in enumerate(failures, 1):
        failure_id = str(failure["_id"])
        task_id = failure.get("task_id")

        logger.info(f"[{i}/{total}] Processing failure (ID: {failure_id})")

        if not task_id:
            logger.warning(f"  No task_id found, skipping")
            skipped_count += 1
            continue

        # Try to find the task to get job_id
        # Convert task_id string to ObjectId
        try:
            task_object_id = ObjectId(task_id)
        except Exception:
            logger.warning(f"  Invalid task_id format: {task_id}, skipping")
            skipped_count += 1
            continue

        tasks_collection = db["tasks"]
        task = await tasks_collection.find_one({"_id": task_object_id})

        if not task:
            logger.warning(f"  Task not found: {task_id}, skipping")
            skipped_count += 1
            continue

        job_id = task.get("job_id")
        task_id_short = task.get("task_id")

        if not job_id or not task_id_short:
            logger.warning(f"  Missing job_id or task_id, skipping")
            skipped_count += 1
            continue

        # Try to extract tool name from requirement
        user_req = failure.get("user_requirement", {})
        description = user_req.get("description", "unknown")
        tool_name = description.split()[0] if description else "unknown"
        tool_name = "".join(c for c in tool_name if c.isalnum() or c == "_").lower()

        # Read files from disk
        files = read_task_files(tools_path, job_id, task_id_short, tool_name)

        # Count how many files were found
        found_files = sum(1 for v in files.values() if v is not None)
        logger.info(f"  Found {found_files}/8 files on disk")

        if found_files == 0:
            logger.warning(f"  No files found on disk, skipping")
            skipped_count += 1
            continue

        # Update the failure document
        if not dry_run:
            result = await failures_collection.update_one(
                {"_id": failure["_id"]},
                {"$set": files}
            )

            if result.modified_count > 0:
                logger.info(f"  ✓ Updated failure with {found_files} files")
                updated_count += 1
            else:
                logger.warning(f"  No changes made")
        else:
            logger.info(f"  [DRY RUN] Would update with {found_files} files")
            updated_count += 1

    logger.info(f"\nTool failures migration complete:")
    logger.info(f"  Updated: {updated_count}")
    logger.info(f"  Skipped: {skipped_count}")
    logger.info(f"  Total: {total}")


async def main():
    """Main migration function."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate existing tools to add file contents")
    parser.add_argument("--dry-run", action="store_true", help="Run without making changes")
    args = parser.parse_args()

    settings = get_settings()

    logger.info("=" * 80)
    logger.info("Starting migration: Add file contents to existing tools")
    logger.info("=" * 80)
    logger.info(f"MongoDB URL: {settings.mongodb_url}")
    logger.info(f"Database: {settings.mongodb_db_name}")
    logger.info(f"Tools path: {settings.tools_path}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 80)

    if args.dry_run:
        logger.warning("DRY RUN MODE - No changes will be made")

    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.mongodb_db_name]

    try:
        # Test connection
        await db.command("ping")
        logger.info("✓ Connected to MongoDB")

        # Migrate tools
        logger.info("\n" + "=" * 80)
        logger.info("Migrating Tool documents")
        logger.info("=" * 80)
        await migrate_tools(db, settings.tools_path, args.dry_run)

        # Migrate tool failures
        logger.info("\n" + "=" * 80)
        logger.info("Migrating ToolFailure documents")
        logger.info("=" * 80)
        await migrate_tool_failures(db, settings.tools_path, args.dry_run)

        logger.info("\n" + "=" * 80)
        logger.info("Migration complete!")
        logger.info("=" * 80)

        if args.dry_run:
            logger.info("\nThis was a DRY RUN. Run without --dry-run to apply changes.")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
