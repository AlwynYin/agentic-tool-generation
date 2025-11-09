"""
Service layer for repository management and registration.

Handles loading package configurations, checking for missing navigation guides,
and orchestrating repository registration workflows.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.config import get_settings
from app.models.repository import (
    PackageConfig,
    RepositoryInfo,
    RepositoryRegistrationResult,
    RepositoryRegistrationResponse
)
from app.agents.repository_agent import RepositoryRegistrationAgent
from app.utils.repository_utils import (
    check_nav_guide_exists,
    check_repo_exists,
    get_repo_path,
    get_guide_path
)

logger = logging.getLogger(__name__)


class RepositoryService:
    """Service for managing repository registration and configuration."""

    def __init__(self):
        """Initialize repository service."""
        self.settings = get_settings()
        self.configs: Dict[str, PackageConfig] = {}
        self.agent = RepositoryRegistrationAgent()

    def load_package_config(self) -> Dict[str, PackageConfig]:
        """
        Load package configuration from JSON file.

        Auto-populates missing repository fields with defaults.
        Enforces full config format via Pydantic validation.

        Returns:
            Dict mapping package names to PackageConfig objects

        Raises:
            FileNotFoundError: If packages.json not found
            ValueError: If config validation fails
        """
        config_path = Path(self.settings.tools_service_path) / "packages.json"

        if not config_path.exists():
            logger.warning(f"Package config not found: {config_path}")
            logger.info("Using empty configuration")
            return {}

        try:
            logger.info(f"Loading package configuration from {config_path}")

            with open(config_path, 'r') as f:
                raw_config = json.load(f)

            # Parse and auto-populate each package config
            configs = {}
            for package_name, package_data in raw_config.items():
                try:
                    # Auto-populate package_name from dict key if not provided
                    if 'package_name' not in package_data or package_data['package_name'] is None:
                        package_data['package_name'] = package_name
                    # Pydantic will auto-populate missing fields with defaults
                    config = PackageConfig(**package_data)
                    configs[package_name] = config
                    logger.debug(f"Loaded config for {package_name}")
                except Exception as e:
                    logger.error(f"Failed to parse config for {package_name}: {e}")
                    raise ValueError(f"Invalid config for {package_name}: {e}")

            logger.info(f"Successfully loaded {len(configs)} package configurations")
            self.configs = configs
            return configs

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON config: {e}")
            raise ValueError(f"Invalid JSON in {config_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading package config: {e}")
            raise

    def save_package_config(self, raw_config: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Save package configuration to packages.json.

        Validates the configuration and auto-populates missing fields before saving.

        Args:
            raw_config: Dictionary mapping package names to package data

        Returns:
            Dict with save result including package count and file path

        Raises:
            ValueError: If configuration is invalid
        """
        config_path = Path(self.settings.tools_service_path) / "packages.json"

        try:
            logger.info(f"Validating and saving package configuration to {config_path}")

            # Validate and parse each package config
            validated_configs = {}
            for package_name, package_data in raw_config.items():
                try:
                    # Auto-populate package_name from dict key if not provided
                    if 'package_name' not in package_data or package_data['package_name'] is None:
                        package_data['package_name'] = package_name
                    # Pydantic will validate and auto-populate missing fields
                    config = PackageConfig(**package_data)
                    # Convert back to dict for JSON serialization
                    validated_configs[package_name] = config.model_dump()
                    logger.debug(f"Validated config for {package_name}")
                except Exception as e:
                    logger.error(f"Failed to validate config for {package_name}: {e}")
                    raise ValueError(f"Invalid config for {package_name}: {e}")

            # Write to file with pretty formatting
            with open(config_path, 'w') as f:
                json.dump(validated_configs, f, indent=4)

            logger.info(f"Successfully saved configuration with {len(validated_configs)} packages")

            # Update in-memory configs
            self.configs = {
                name: PackageConfig(**data)
                for name, data in validated_configs.items()
            }

            return {
                "package_count": len(validated_configs),
                "packages": list(validated_configs.keys()),
                "file_path": str(config_path)
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to encode JSON: {e}")
            raise ValueError(f"Failed to encode configuration as JSON: {e}")
        except Exception as e:
            logger.error(f"Error saving package config: {e}")
            raise

    def get_available_packages(self) -> List[str]:
        """
        Get list of available package names from configuration.

        Returns:
            List of package names
        """
        if not self.configs:
            self.load_package_config()

        return list(self.configs.keys())

    def check_missing_guides(self) -> List[str]:
        """
        Check which packages are missing navigation guides.

        Returns:
            List of package names missing navigation guides
        """
        if not self.configs:
            self.load_package_config()

        missing = []
        for package_name in self.configs.keys():
            if not check_nav_guide_exists(package_name):
                missing.append(package_name)
                logger.debug(f"Missing navigation guide for: {package_name}")

        logger.info(f"Found {len(missing)} packages missing navigation guides")
        return missing

    def get_repository_status(self) -> List[RepositoryInfo]:
        """
        Get status of all packages (repository and navigation guide existence).

        Returns:
            List of RepositoryInfo objects
        """
        if not self.configs:
            self.load_package_config()

        status_list = []

        for package_name, config in self.configs.items():
            has_guide = check_nav_guide_exists(package_name)
            repo_exists = check_repo_exists(package_name)

            repo_info = RepositoryInfo(
                package_name=package_name,
                has_navigation_guide=has_guide,
                repo_exists=repo_exists,
                repo_path=str(get_repo_path(package_name)) if repo_exists else None,
                guide_path=str(get_guide_path(package_name)) if has_guide else None,
                config=config
            )
            status_list.append(repo_info)

        return status_list

    async def register_repository(self, package_name: str) -> RepositoryRegistrationResult:
        """
        Register a single repository.

        Args:
            package_name: Name of the package to register

        Returns:
            RepositoryRegistrationResult with registration outcome
        """
        try:
            # Load config if not already loaded
            if not self.configs:
                self.load_package_config()

            # Check if package exists in config
            if package_name not in self.configs:
                logger.error(f"Package not found in config: {package_name}")
                return RepositoryRegistrationResult(
                    success=False,
                    package_name=package_name,
                    error=f"Package '{package_name}' not found in configuration"
                )

            config = self.configs[package_name]

            logger.info(f"Starting registration for package: {package_name}")

            # Run agent to register the package
            output = await self.agent.register_package(config)

            # Convert agent output to result
            steps_completed = []
            if output.repo_url:
                steps_completed.append("search")
            if output.download_path:
                steps_completed.append("download")
            if output.guide_generated:
                steps_completed.append("generate_guide")

            result = RepositoryRegistrationResult(
                success=output.success,
                package_name=package_name,
                repo_path=output.download_path,
                guide_path=output.guide_path,
                error=output.error,
                steps_completed=steps_completed
            )

            if result.success:
                logger.info(f"Successfully registered {package_name}")
            else:
                logger.error(f"Failed to register {package_name}: {result.error}")

            return result

        except Exception as e:
            logger.error(f"Exception during repository registration for {package_name}: {e}")
            return RepositoryRegistrationResult(
                success=False,
                package_name=package_name,
                error=str(e)
            )

    async def register_all_missing(self) -> RepositoryRegistrationResponse:
        """
        Register all packages that are missing navigation guides.

        Returns:
            RepositoryRegistrationResponse with batch results
        """
        missing = self.check_missing_guides()

        if not missing:
            logger.info("No missing navigation guides - all packages registered")
            return RepositoryRegistrationResponse(
                total=0,
                successful=0,
                failed=0,
                results=[]
            )

        logger.info(f"Registering {len(missing)} packages with missing navigation guides")

        results = []
        successful = 0
        failed = 0

        for package_name in missing:
            result = await self.register_repository(package_name)
            results.append(result)

            if result.success:
                successful += 1
            else:
                failed += 1

        response = RepositoryRegistrationResponse(
            total=len(missing),
            successful=successful,
            failed=failed,
            results=results
        )

        logger.info(f"Batch registration complete: {successful} successful, {failed} failed")
        return response

    async def register_multiple(self, package_names: List[str]) -> RepositoryRegistrationResponse:
        """
        Register multiple specific packages.

        Args:
            package_names: List of package names to register

        Returns:
            RepositoryRegistrationResponse with batch results
        """
        logger.info(f"Registering {len(package_names)} specified packages")

        results = []
        successful = 0
        failed = 0

        for package_name in package_names:
            result = await self.register_repository(package_name)
            results.append(result)

            if result.success:
                successful += 1
            else:
                failed += 1

        response = RepositoryRegistrationResponse(
            total=len(package_names),
            successful=successful,
            failed=failed,
            results=results
        )

        logger.info(f"Batch registration complete: {successful} successful, {failed} failed")
        return response
