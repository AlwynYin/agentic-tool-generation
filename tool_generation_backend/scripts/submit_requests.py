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
# BASE_URL = "https://tool-generation-service-staging.up.railway.app"

async def test_tool_generation_pipeline():
    """Test the complete tool generation pipeline."""

    # Test job request with one reasonable and one unreasonable requirement
    job_request = {
        "toolRequirements": [
                # {
                #     "description": "Generate a 3D starting geometry from a SMILES string using RDKit (ETKDG + MMFF minimization).",
                #     "input": "SMILES string",
                #     "output": "Initial 3D XYZ geometry in Å as a string"
                # },
                # {
                #     "description": "Validate and normalize an XYZ block (atom symbols, units = Å, no duplicates, sensible bond lengths).",
                #     "input": "XYZ geometry in Å as a string",
                #     "output": "Validated XYZ geometry in Å as a string"
                # },
                # {
                #     "description": "Run HF/def2-SVP gas-phase geometry optimization and return the optimized structure and final SCF energy.",
                #     "input": "XYZ geometry in Å as a string",
                #     "output": "Optimized XYZ geometry in Å as a string and total electronic energy in Hartree"
                # },
                {
                    "description": "Detect the molecular point group from Cartesian coordinates.",
                    "input": "XYZ geometry in Å as a string",
                    "output": "Point group label (e.g., C2v, D3h)"
                },
                # {
                #     "description": "Compute the permanent dipole moment (vector and magnitude) via single-point HF/def2-SVP on the provided geometry.",
                #     "input": "XYZ geometry in Å as a string",
                #     "output": "Dipole vector (Dx, Dy, Dz) in Debye and magnitude in Debye"
                # },
                # {
                #     "description": "Compute molecular orbital energies and occupations via single-point HF/def2-SVP; build a sorted MO table.",
                #     "input": "XYZ geometry in Å as a string",
                #     "output": "MO energy table (index, occupation, energy in eV and Hartree), HOMO index, LUMO index, HOMO–LUMO gap (eV and Hartree)"
                # },
                # {
                #     "description": "Compute Mulliken atomic charges from an HF/def2-SVP single-point population analysis.",
                #     "input": "XYZ geometry in Å as a string",
                #     "output": "Per-atom Mulliken charges (list aligned to atom order)"
                # },
                # {
                #     "description": "Compute Löwdin atomic charges from an HF/def2-SVP single-point population analysis.",
                #     "input": "XYZ geometry in Å as a string",
                #     "output": "Per-atom Löwdin charges (list aligned to atom order)"
                # },
                # {
                #     "description": "Compute Hirshfeld (stockholder) atomic charges using a promolecular-density-based analysis if available (e.g., Psi4/HORTON/pyhif).",
                #     "input": "XYZ geometry in Å as a string",
                #     "output": "Per-atom Hirshfeld charges (list aligned to atom order)"
                # },
                # {
                #     "description": "Format Cartesian coordinates in a clean, reproducible XYZ block with fixed precision and Å units.",
                #     "input": "XYZ geometry in Å as a string",
                #     "output": "Pretty-printed XYZ geometry in Å as a string"
                # },
                # {
                #     "description": "Assemble a per-molecule report object from computed pieces (coordinates, energy, point group, dipole, MO table, charges).",
                #     "input": "Molecule name/ID, optimized XYZ in Å, total energy (Hartree), point group, dipole (vector+magnitude, Debye), MO table+gap, Mulliken/Löwdin/Hirshfeld charges",
                #     "output": "Structured JSON report for one molecule"
                # },
                # {
                #     "description": "Render a human-readable report (Markdown or HTML) from a report JSON object.",
                #     "input": "Per-molecule report JSON",
                #     "output": "Markdown or HTML string of the report"
                # },
                # {
                #     "description": "Batch driver: for each molecule spec, run the full pipeline (build 3D if SMILES, optimize HF/def2-SVP, compute properties) and produce individual reports.",
                #     "input": "List of molecule specs (each either SMILES or XYZ), optional per-molecule name",
                #     "output": "List of per-molecule JSON reports (one per input)"
                # },
                # {
                #     "description": "Lightweight provenance capture for reproducibility (library versions, method, basis, SCF/opt settings, convergence thresholds).",
                #     "input": "Computation settings and results metadata",
                #     "output": "Provenance JSON blob suitable for embedding in reports"
                # }
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