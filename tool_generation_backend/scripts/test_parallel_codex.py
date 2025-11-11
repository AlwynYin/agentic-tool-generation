#!/usr/bin/env python3
"""
Test script to check if two Codex sessions can run in parallel.

This script runs two simple Codex queries concurrently and measures:
1. Total execution time
2. Individual execution times
3. Whether they ran in parallel (total time ~= max individual time)
   or sequentially (total time ~= sum of individual times)

Usage:
    python scripts/test_parallel_codex.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import time

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.codex_utils import run_codex_query
from app.config import get_settings


async def run_simple_query(query_id: int, duration_hint: str = "quick"):
    """
    Run a simple Codex query.

    Args:
        query_id: Identifier for this query (1 or 2)
        duration_hint: Hint about expected duration

    Returns:
        Dict with timing info and success status
    """
    prompt = f"""
Please create a simple Python file named test_query_{query_id}.py that:
1. Prints "Hello from query {query_id}"
2. Calculates the sum of numbers from 1 to 100
3. Prints the result

This is a {duration_hint} test query.
"""

    print(f"[Query {query_id}] Starting at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
    start_time = time.time()

    try:
        settings = get_settings()
        result = await run_codex_query(
            query=prompt,
            working_dir=settings.tools_service_path,
            timeout=60
        )

        end_time = time.time()
        elapsed = end_time - start_time

        print(f"[Query {query_id}] Completed at {datetime.now().strftime('%H:%M:%S.%f')[:-3]} "
              f"(took {elapsed:.2f}s)")

        return {
            "query_id": query_id,
            "success": result.get("success", False),
            "elapsed_time": elapsed,
            "start_time": start_time,
            "end_time": end_time,
            "error": result.get("error") if not result.get("success") else None
        }

    except Exception as e:
        end_time = time.time()
        elapsed = end_time - start_time

        print(f"[Query {query_id}] Failed at {datetime.now().strftime('%H:%M:%S.%f')[:-3]} "
              f"(took {elapsed:.2f}s)")
        print(f"[Query {query_id}] Error: {e}")

        return {
            "query_id": query_id,
            "success": False,
            "elapsed_time": elapsed,
            "start_time": start_time,
            "end_time": end_time,
            "error": str(e)
        }


async def test_parallel_execution():
    """Test if two Codex queries can run in parallel."""

    print("🚀 Testing Parallel Codex Execution")
    print("=" * 70)
    print(f"\nStarting two Codex queries concurrently...\n")

    # Start both queries at the same time
    overall_start = time.time()

    # Run both queries concurrently
    results = await asyncio.gather(
        run_simple_query(1),
        run_simple_query(2),
        return_exceptions=True
    )

    overall_end = time.time()
    overall_elapsed = overall_end - overall_start

    print(f"\n" + "=" * 70)
    print("📊 Results Summary")
    print("=" * 70)

    # Process results
    successful_results = [r for r in results if isinstance(r, dict)]

    if len(successful_results) < 2:
        print("❌ One or both queries failed to complete")
        for i, result in enumerate(results, 1):
            if isinstance(result, Exception):
                print(f"   Query {i}: Exception - {result}")
        return

    query1, query2 = successful_results

    # Print individual timings
    print(f"\n⏱️  Individual Timings:")
    print(f"   Query 1: {query1['elapsed_time']:.2f}s (Success: {query1['success']})")
    print(f"   Query 2: {query2['elapsed_time']:.2f}s (Success: {query2['success']})")

    # Calculate overlap
    max_individual = max(query1['elapsed_time'], query2['elapsed_time'])
    sum_individual = query1['elapsed_time'] + query2['elapsed_time']

    print(f"\n⏱️  Overall Timing:")
    print(f"   Total elapsed time: {overall_elapsed:.2f}s")
    print(f"   Max individual time: {max_individual:.2f}s")
    print(f"   Sum of individual times: {sum_individual:.2f}s")

    # Determine if parallel or sequential
    # If total time is close to max (within 20% overhead), it's parallel
    # If total time is close to sum, it's sequential
    parallel_threshold = max_individual * 1.2  # Allow 20% overhead
    sequential_threshold = sum_individual * 0.8  # Allow 20% speedup

    print(f"\n🔍 Analysis:")

    if overall_elapsed <= parallel_threshold:
        print(f"   ✅ PARALLEL EXECUTION DETECTED")
        print(f"      Total time ({overall_elapsed:.2f}s) is close to max individual time ({max_individual:.2f}s)")
        print(f"      The queries ran concurrently!")

        # Calculate time overlap
        start1, end1 = query1['start_time'], query1['end_time']
        start2, end2 = query2['start_time'], query2['end_time']

        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        overlap = max(0, overlap_end - overlap_start)

        print(f"      Time overlap: {overlap:.2f}s ({(overlap/max_individual)*100:.1f}% of max duration)")

    elif overall_elapsed >= sequential_threshold:
        print(f"   ❌ SEQUENTIAL EXECUTION DETECTED")
        print(f"      Total time ({overall_elapsed:.2f}s) is close to sum of individual times ({sum_individual:.2f}s)")
        print(f"      The queries ran one after another, not in parallel")

    else:
        print(f"   ⚠️  UNCLEAR - Partial parallelization or variable timing")
        print(f"      Total time ({overall_elapsed:.2f}s) is between max ({max_individual:.2f}s) and sum ({sum_individual:.2f}s)")
        print(f"      There may be some parallelization but with contention or variable performance")

    # Show errors if any
    errors = [r for r in successful_results if r['error']]
    if errors:
        print(f"\n⚠️  Errors encountered:")
        for result in errors:
            print(f"   Query {result['query_id']}: {result['error']}")

    print("\n" + "=" * 70)


async def check_backend():
    """Check if the LLM backend is configured for Codex."""
    settings = get_settings()
    backend = settings.llm_backend.lower()

    print(f"🔍 Checking configuration...\n")
    print(f"   LLM Backend: {backend}")
    print(f"   Tools Service Path: {settings.tools_service_path}")

    if backend != "codex":
        print(f"\n❌ Warning: LLM backend is set to '{backend}', not 'codex'")
        print(f"   This test is designed for Codex")
        print(f"   You can change it in your .env file: LLM_BACKEND=codex")
        return False

    # Check if API key is configured
    if not settings.openai_api_key:
        print(f"\n❌ Error: OpenAI API key not configured")
        print(f"   Set OPENAI_API_KEY in your .env file")
        return False

    print(f"   ✅ Configuration looks good\n")
    return True


if __name__ == "__main__":
    async def main():
        if await check_backend():
            await test_parallel_execution()
        else:
            print("\n💡 Please fix configuration issues before running this test")

    asyncio.run(main())