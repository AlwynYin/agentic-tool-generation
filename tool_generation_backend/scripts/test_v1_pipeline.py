#!/usr/bin/env python3
"""
Test script for the complete tool generation pipeline.

This script demonstrates the end-to-end flow:
1. Submit job via POST /api/v1/jobs
2. Monitor job status
3. Retrieve generated tool results

Usage:
    python test_v1_pipeline.py
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any

# BASE_URL = "https://tool-generation-service.up.railway.app"
BASE_URL = "http://127.0.0.1:8000"
# BASE_URL = "http://100.116.240.11:8000"
# BASE_URL = "https://agent-browser-staging.up.railway.app"

async def test_tool_generation_pipeline():
    """Test the complete tool generation pipeline."""

    # Test job request with one reasonable and one unreasonable requirement
    job_request = {
        "toolRequirements": [
            {
                "description": "I need a tool that calculates the molecular weight of a chemical compound. Please use RDKit if available.",
                "input": "SMILES string of the molecule",
                "output": "molecular weight"
            },
            {
                "description": "I need a tool that creates an HTTP web server to handle REST API requests and serve static files.",
                "input": "port number and configuration settings",
                "output": "running web server instance"
            }
        ],
        "metadata": {
            "sessionId": "session_123",
            "clientId": "test-pipeline"
        }
    }

    print("🚀 Testing Tool Generation Pipeline")
    print("=" * 50)

    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Submit job
            print("\n1️⃣ Submitting tool generation job...")
            print(f"   Tool Requirements: {len(job_request['toolRequirements'])}")
            print(f"   Client ID: {job_request['metadata']['clientId']}")

            async with session.post(
                f"{BASE_URL}/api/v1/jobs",
                json=job_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 201:
                    job_response = await response.json()
                    job_id = job_response["jobId"]

                    print(f"   ✅ Job submitted successfully!")
                    print(f"   Job ID: {job_id}")
                    print(f"   Status: {job_response['status']}")
                else:
                    error_text = await response.text()
                    print(f"   ❌ Failed to submit job: {response.status}")
                    print(f"   Error: {error_text}")
                    return

            # Step 2: Monitor job status
            print("\n2️⃣ Monitoring job status...")
            max_attempts = 30  # 10 minutes with 20s intervals
            attempt = 0

            while attempt < max_attempts:
                attempt += 1

                async with session.get(f"{BASE_URL}/api/v1/jobs/{job_id}") as response:
                    if response.status == 200:
                        status_data = await response.json()
                        status = status_data["status"]
                        progress = status_data.get("progress", {})

                        print(f"   📊 Attempt {attempt}: Status = {status}, Progress = {progress.get('completed', 0)}/{progress.get('total', 0)}")

                        if status in ["completed", "failed"]:
                            break
                        elif status == "cancelled":
                            print("   ⚠️ Job was cancelled")
                            return
                    else:
                        print(f"   ❌ Failed to get status: {response.status}")

                # Wait before next check
                if attempt < max_attempts:
                    await asyncio.sleep(20)

            # Step 3: Get final results (check final job status for toolFiles)
            print("\n3️⃣ Retrieving final job status...")

            async with session.get(f"{BASE_URL}/api/v1/jobs/{job_id}") as response:
                if response.status == 200:
                    final_status = await response.json()

                    print(f"   📋 Job completed with status: {final_status['status']}")

                    # Check for toolFiles in the completed job response
                    tool_files = final_status.get('toolFiles', [])
                    if tool_files:
                        print(f"   🔧 Tools generated: {len(tool_files)}")
                        for tool_file in tool_files:
                            print(f"      - {tool_file['fileName']}: {tool_file['description']}")
                            print(f"        File: {tool_file['filePath']}")
                            print(f"        Registered: {tool_file['registered']}")
                            print(f"        Code length: {len(tool_file['code'])} characters")
                    else:
                        print(f"   ⚠️ No tool files found in completed job")

                    # Check for failures
                    failures = final_status.get('failures', [])
                    if failures:
                        print(f"   ❌ Failed generations: {len(failures)}")
                        for failure in failures:
                            print(f"      - Error: {failure['error']}")

                    # Show summary
                    summary = final_status.get('summary')
                    if summary:
                        print(f"   📊 Summary: {summary['successful']}/{summary['totalRequested']} successful")

                else:
                    error_text = await response.text()
                    print(f"   ❌ Failed to get final status: {response.status}")
                    print(f"   Error: {error_text}")

        except aiohttp.ClientError as e:
            print(f"❌ Connection error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

    print("\n" + "=" * 50)
    print("🏁 Pipeline test completed!")


async def test_health_check():
    """Test if the backend is running."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/api/v1/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    print(f"✅ Backend is healthy: {health_data}")
                    return True
                else:
                    print(f"❌ Backend health check failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("💡 Make sure the backend is running with: uvicorn app.main:app --reload")
        return False


if __name__ == "__main__":
    async def main():
        print("🔍 Checking backend health...")
        if await test_health_check():
            print()
            await test_tool_generation_pipeline()
        else:
            print("\n💡 Start the backend first:")
            print("   cd tool_generation_backend")
            print("   uvicorn app.main:app --reload")

    asyncio.run(main())