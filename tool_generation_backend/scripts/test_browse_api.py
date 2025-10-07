#!/usr/bin/env python3
"""
Test script for the refactored execute_codex_browse function.

Tests API reference extraction from rdkit documentation.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.codex_utils import execute_codex_browse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


async def main():
    """Test the execute_codex_browse function."""
    print("=" * 60)
    print("Testing execute_codex_browse with RDKit")
    print("=" * 60)

    # Define test queries
    queries = [
        "molecular weight calculation",
        "SMILES to molecular structure conversion",
        "molecule descriptors"
    ]

    print(f"\nQueries: {queries}")
    print("\nExecuting Codex browse...\n")

    # Execute browse
    result = await execute_codex_browse("rdkit", queries)

    # Display results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    print(f"\nSuccess: {result.success}")
    print(f"Library: {result.library}")
    print(f"Queries: {result.queries}")

    if result.success:
        print(f"\n✓ Found {len(result.api_functions)} API functions")
        print(f"✓ Output file: {result.output_file}")

        # Display each API function
        for i, func in enumerate(result.api_functions, 1):
            print(f"\n{i}. {func.function_name}")
            print(f"   Description: {func.description[:100]}...")
            print(f"   Parameters: {len(func.input_schema)}")
            if func.input_schema:
                for param in func.input_schema:
                    print(f"     - {param.name}: {param.type} - {param.description[:50]}...")
            print(f"   Output: {func.output_schema.type} - {func.output_schema.description[:50]}...")
            print(f"   Examples: {len(func.examples)}")
            if func.examples:
                ex = func.examples[0]
                print(f"     Example: {ex.description}")
                print(f"     Code:\n       {ex.code[:100]}...")
    else:
        print(f"\n✗ Error: {result.error}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
