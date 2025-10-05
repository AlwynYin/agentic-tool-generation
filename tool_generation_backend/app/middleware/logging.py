"""
Logging middleware for request/response tracking.
"""

import logging
import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        start_time = time.time()

        # Log request
        logging.info(f"→ {request.method} {request.url.path}")

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time
        duration_ms = round(duration * 1000, 2)

        # Log response
        logging.info(
            f"← {request.method} {request.url.path} "
            f"{response.status_code} - {duration_ms}ms"
        )

        return response


def setup_logging_middleware(app: FastAPI, settings: Settings) -> None:
    """Setup logging middleware for the FastAPI application."""
    app.add_middleware(LoggingMiddleware)

    # Configure logging format
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Suppress verbose third-party loggers
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)