#!/usr/bin/env python3
"""
Upload package configuration and register all repositories.

This script uploads a packages.json file to the backend and then
triggers registration for all packages missing navigation guides.

Usage:
    python scripts/upload_and_register.py <config_file.json>
    python scripts/upload_and_register.py  # Uses default tool_service/packages.json
"""

import sys
import json
import asyncio
import argparse
from pathlib import Path
from typing import Dict, Any

import httpx


# Default configuration
DEFAULT_CONFIG_FILE = Path(__file__).parent.parent.parent / "tool_service" / "packages.json"
DEFAULT_BASE_URL = "http://localhost:8000"


async def upload_config(base_url: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upload package configuration to the backend.

    Args:
        base_url: Base URL of the backend API
        config_data: Package configuration dictionary

    Returns:
        Response from upload endpoint

    Raises:
        httpx.HTTPError: If upload fails
    """
    url = f"{base_url}/api/v1/repositories/upload-config"

    print(f"📤 Uploading configuration to {url}")
    print(f"   Packages: {', '.join(config_data.keys())}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            json={"config": config_data}
        )
        response.raise_for_status()
        result = response.json()

    print(f"✅ Upload successful: {result['package_count']} packages")
    print(f"   Saved to: {result['file_path']}")

    return result


async def register_all(base_url: str) -> Dict[str, Any]:
    """
    Register all packages missing navigation guides.

    Args:
        base_url: Base URL of the backend API

    Returns:
        Response from register-all endpoint

    Raises:
        httpx.HTTPError: If registration fails
    """
    url = f"{base_url}/api/v1/repositories/register-all"

    print(f"\n🔧 Registering all missing repositories...")
    print(f"   This may take several minutes depending on the number of packages")

    async with httpx.AsyncClient(timeout=600.0) as client:  # 10 minute timeout for agent work
        response = await client.post(url)
        response.raise_for_status()
        result = response.json()

    print(f"\n✅ Registration complete!")
    print(f"   Total: {result['total']} packages")
    print(f"   Successful: {result['successful']}")
    print(f"   Failed: {result['failed']}")

    # Print details for each result
    if result.get('results'):
        print(f"\n📋 Detailed Results:")
        for res in result['results']:
            status = "✅" if res['success'] else "❌"
            print(f"   {status} {res['package_name']}")
            if res['success']:
                print(f"      Repo: {res.get('repo_path', 'N/A')}")
                print(f"      Guide: {res.get('guide_path', 'N/A')}")
                if res.get('steps_completed'):
                    print(f"      Steps: {', '.join(res['steps_completed'])}")
            else:
                print(f"      Error: {res.get('error', 'Unknown error')}")

    return result


async def main(config_file: Path, base_url: str) -> None:
    """
    Main function to upload config and register all packages.

    Args:
        config_file: Path to packages.json file
        base_url: Base URL of the backend API
    """
    try:
        # Load configuration file
        print(f"📖 Reading configuration from: {config_file}")

        if not config_file.exists():
            print(f"❌ Error: Configuration file not found: {config_file}")
            sys.exit(1)

        with open(config_file, 'r') as f:
            config_data = json.load(f)

        if not config_data:
            print(f"❌ Error: Configuration file is empty")
            sys.exit(1)

        print(f"   Loaded {len(config_data)} packages\n")

        # Step 1: Upload configuration
        upload_result = await upload_config(base_url, config_data)

        # Step 2: Register all packages

        # Summary
        print(f"\n{'='*60}")
        print(f"📊 Summary")
        print(f"{'='*60}")
        print(f"Uploaded: {upload_result['package_count']} packages")
        register_result = await register_all(base_url)
        print(f"Registered: {register_result['successful']}/{register_result['total']} packages")

        if register_result['failed'] > 0:
            print(f"\n⚠️  {register_result['failed']} package(s) failed to register")
            sys.exit(1)
        else:
            print(f"\n🎉 All packages registered successfully!")
            sys.exit(0)

    except httpx.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Details: {error_detail.get('detail', 'No details available')}")
            except:
                print(f"   Response: {e.response.text}")
        sys.exit(1)

    except json.JSONDecodeError as e:
        print(f"\n❌ Invalid JSON in configuration file: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upload package configuration and register all repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload default config and register all
  python scripts/upload_and_register.py

  # Upload custom config file
  python scripts/upload_and_register.py /path/to/custom_packages.json

  # Use different backend URL
  python scripts/upload_and_register.py --url http://localhost:9000

  # Upload and register with custom URL
  python scripts/upload_and_register.py my_packages.json --url http://localhost:9000
        """
    )

    parser.add_argument(
        "config_file",
        nargs="?",
        type=Path,
        default=DEFAULT_CONFIG_FILE,
        help=f"Path to packages.json file (default: {DEFAULT_CONFIG_FILE})"
    )

    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"Backend API base URL (default: {DEFAULT_BASE_URL})"
    )
    args = parser.parse_args()

    # Run async main function
    asyncio.run(main(args.config_file, args.url))
