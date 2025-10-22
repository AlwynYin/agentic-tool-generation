"""
API endpoints for repository management.

Provides endpoints for:
- Uploading package configuration
- Checking repository status
- Registering specific repositories
- Batch registration of missing repositories
"""

import logging
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.models.repository import (
    RepositoryInfo,
    RepositoryRegistrationRequest,
    RepositoryRegistrationResponse,
    PackageConfig
)
from app.services.repository_service import RepositoryService

logger = logging.getLogger(__name__)

router = APIRouter()


class PackageConfigUpload(BaseModel):
    """Request body for uploading package configuration."""
    config: Dict[str, Dict[str, Any]] = Field(
        description="Package configuration as a dictionary"
    )


def get_repository_service() -> RepositoryService:
    """Dependency to get repository service instance."""
    return RepositoryService()


@router.post("/upload-config", response_model=Dict[str, Any])
async def upload_package_config(
    upload: PackageConfigUpload,
    service: RepositoryService = Depends(get_repository_service)
) -> Dict[str, Any]:
    """
    Upload and save a new package configuration.

    This endpoint accepts a package configuration as a JSON object and saves it
    to packages.json. The configuration will be validated and auto-populated with
    default values for missing optional fields.

    Typical workflow:
    1. POST /api/v1/repositories/upload-config - Upload configuration
    2. POST /api/v1/repositories/register-all - Register all packages

    Args:
        upload: PackageConfigUpload with config dictionary

    Returns:
        Success status and validation summary
    """
    try:
        logger.info("Uploading new package configuration")

        # Validate and save the configuration
        result = service.save_package_config(upload.config)

        logger.info(f"Successfully uploaded configuration with {result['package_count']} packages")

        return {
            "success": True,
            "message": "Package configuration uploaded successfully",
            "package_count": result["package_count"],
            "packages": result["packages"],
            "file_path": result["file_path"]
        }

    except ValueError as e:
        logger.error(f"Invalid package configuration: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid package configuration: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error uploading package config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload package config: {str(e)}"
        )


@router.get("/status", response_model=List[RepositoryInfo])
async def get_repository_status(
    service: RepositoryService = Depends(get_repository_service)
) -> List[RepositoryInfo]:
    """
    Get status of all configured packages.

    Returns information about each package including:
    - Whether navigation guide exists
    - Whether repository is downloaded
    - Paths to repository and guide
    - Package configuration

    Returns:
        List of RepositoryInfo objects
    """
    try:
        logger.info("Getting repository status for all packages")
        status = service.get_repository_status()
        return status

    except Exception as e:
        logger.error(f"Error getting repository status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get repository status: {str(e)}"
        )


@router.get("/config", response_model=Dict[str, PackageConfig])
async def get_package_config(
    service: RepositoryService = Depends(get_repository_service)
) -> Dict[str, PackageConfig]:
    """
    Get the current package configuration.

    Returns all package configurations with auto-populated fields.

    Returns:
        Dict mapping package names to PackageConfig objects
    """
    try:
        logger.info("Getting package configuration")
        config = service.load_package_config()
        return config

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Package configuration file not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid package configuration: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error loading package config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load package config: {str(e)}"
        )


@router.get("/missing", response_model=List[str])
async def get_missing_guides(
    service: RepositoryService = Depends(get_repository_service)
) -> List[str]:
    """
    Get list of packages missing navigation guides.

    Returns:
        List of package names that don't have navigation guides
    """
    try:
        logger.info("Checking for missing navigation guides")
        missing = service.check_missing_guides()
        return missing

    except Exception as e:
        logger.error(f"Error checking missing guides: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check missing guides: {str(e)}"
        )


@router.post("/register", response_model=RepositoryRegistrationResponse)
async def register_repositories(
    request: RepositoryRegistrationRequest,
    service: RepositoryService = Depends(get_repository_service)
) -> RepositoryRegistrationResponse:
    """
    Register specific repositories.

    Downloads repositories and generates navigation guides for the
    specified packages.

    Args:
        request: RepositoryRegistrationRequest with package_names

    Returns:
        RepositoryRegistrationResponse with results for each package
    """
    try:
        logger.info(f"Registering {len(request.package_names)} repositories")

        if not request.package_names:
            raise HTTPException(
                status_code=400,
                detail="No package names provided"
            )

        response = await service.register_multiple(request.package_names)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering repositories: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register repositories: {str(e)}"
        )


@router.post("/register-all", response_model=RepositoryRegistrationResponse)
async def register_all_missing(
    service: RepositoryService = Depends(get_repository_service)
) -> RepositoryRegistrationResponse:
    """
    Register all packages missing navigation guides.

    Automatically finds packages without navigation guides and
    registers them (downloads repo + generates guide).

    Returns:
        RepositoryRegistrationResponse with results for all missing packages
    """
    try:
        logger.info("Registering all missing repositories")
        response = await service.register_all_missing()
        return response

    except Exception as e:
        logger.error(f"Error registering all missing repositories: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register all missing repositories: {str(e)}"
        )


@router.get("/health")
async def repository_health() -> Dict[str, Any]:
    """
    Health check for repository service.

    Returns:
        Basic health information
    """
    return {
        "status": "healthy",
        "service": "repository-management"
    }
