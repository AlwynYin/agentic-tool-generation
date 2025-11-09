#!/usr/bin/env python3
"""
Simple test script for requirement extraction + job submission API.

Usage:
    python scripts/test_extract_and_submit.py
"""

import asyncio
import aiohttp

BASE_URL = "http://127.0.0.1:8000"


async def test_extract_and_submit():
    """Test the extract and submit endpoint."""

    # Task description to extract requirements from
    task_description = """
For the three compounds listed below, perform a geometry optimization using the Hartree-Fock (HF) method and the def2-SVP basis set in the gas phase.
After optimization, generate a separate report for each molecule. Each report must contain:
Final Cartesian coordinates (in Å)
Total energy (in Hartrees)
Point group symmetry
Dipole moment (in Debye)
Molecular orbital analysis (including an MO energy table and the HOMO–LUMO gap)
Atomic charge analysis (Mulliken, Löwdin, and Hirshfeld)
Compounds:
caffeine: CN1C=NC2=C1C(=O)N(C(=O)N2C)C
theobromine: CN1C=NC2=C1C(=O)NC(=O)N2C
acetylsalicylic_acid: CC(=O)OC1=CC=CC=C1C(=O)O    """

    print("🚀 Testing Requirement Extraction + Job Submission")
    print("=" * 60)
    print(f"\n📝 Task Description:")
    print(f"   {task_description.strip()}")

    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Submit to extract-and-submit endpoint
            print(f"\n1️⃣ Calling /api/v1/extract-and-submit...")

            request_payload = {
                "task_description": task_description,
                "client_id": "test-extract-script"
            }

            async with session.post(
                f"{BASE_URL}/api/v1/extract-and-submit",
                json=request_payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    extract_response = await response.json()

                    print(f"   ✅ Requirements extracted and job submitted!")
                    print(f"   Job ID: {extract_response['job_id']}")
                    print(f"   Requirements extracted: {extract_response['requirements_count']}")
                    print(f"   Status: {extract_response['status']}")

                    job_id = extract_response['job_id']
                else:
                    error_text = await response.text()
                    print(f"   ❌ Failed: {response.status}")
                    print(f"   Error: {error_text}")
                    return

            # Step 2: Monitor job status
            print(f"\n2️⃣ Monitoring job {job_id}...")
            max_attempts = 30  # 10 minutes
            attempt = 0

            while attempt < max_attempts:
                attempt += 1

                async with session.get(f"{BASE_URL}/api/v1/jobs/{job_id}") as response:
                    if response.status == 200:
                        status_data = await response.json()
                        status = status_data["status"]
                        progress = status_data.get("progress", {})

                        print(f"   📊 Attempt {attempt}: Status = {status}, "
                              f"Progress = {progress.get('completed', 0)}/{progress.get('total', 0)}")

                        if status in ["completed", "failed"]:
                            break
                    else:
                        print(f"   ❌ Failed to get status: {response.status}")

                if attempt < max_attempts:
                    await asyncio.sleep(20)

            # Step 3: Get final results
            print(f"\n3️⃣ Getting final results...")

            async with session.get(f"{BASE_URL}/api/v1/jobs/{job_id}") as response:
                if response.status == 200:
                    final_status = await response.json()

                    print(f"   📋 Final status: {final_status['status']}")

                    # Show tools
                    tool_files = final_status.get('toolFiles', [])
                    if tool_files:
                        print(f"\n   🔧 Tools generated: {len(tool_files)}")
                        for tool in tool_files:
                            print(f"      - {tool['fileName']}")
                            print(f"        Description: {tool['description']}")
                            print(f"        Path: {tool['filePath']}")
                    else:
                        print(f"   ⚠️ No tools generated")

                    # Show failures
                    failures = final_status.get('failures', [])
                    if failures:
                        print(f"\n   ❌ Failures: {len(failures)}")
                        for failure in failures:
                            print(f"      - {failure['error']}")

                    # Show summary
                    summary = final_status.get('summary')
                    if summary:
                        print(f"\n   📊 Summary: {summary['successful']}/{summary['totalRequested']} successful")

                else:
                    print(f"   ❌ Failed to get final status: {response.status}")

        except aiohttp.ClientError as e:
            print(f"❌ Connection error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("🏁 Test completed!")


async def check_health():
    """Check if backend is running."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/api/v1/health") as response:
                if response.status == 200:
                    print("✅ Backend is healthy")
                    return True
                else:
                    print(f"❌ Backend health check failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("💡 Start the backend with: python -m app.main")
        return False


if __name__ == "__main__":
    async def main():
        print("🔍 Checking backend health...\n")
        if await check_health():
            print()
            await test_extract_and_submit()
        else:
            print("\n💡 Start the backend first:")
            print("   cd tool_generation_backend")
            print("   python -m app.main")

    asyncio.run(main())