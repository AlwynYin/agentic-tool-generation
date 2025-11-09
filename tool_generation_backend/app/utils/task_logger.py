"""
Task-specific file logging utility.

This module provides file-based logging for individual tasks,
creating separate log files for each component of the pipeline.
"""

import logging
from pathlib import Path
from typing import Optional, Dict
from app.config import get_settings

# Cache of task-specific loggers
_task_loggers: Dict[str, logging.Logger] = {}


def setup_task_logging(job_id: str, task_id: str) -> Path:
    """
    Set up logging directory structure for a task.

    Creates the logs directory if it doesn't exist.

    Args:
        job_id: Job identifier
        task_id: Task identifier

    Returns:
        Path: Path to the logs directory
    """
    settings = get_settings()

    # Create logs directory: tools/{job_id}/{task_id}/logs/
    logs_dir = Path(settings.tools_path) / job_id / task_id / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    return logs_dir


def get_task_logger(
    name: str,
    job_id: str,
    task_id: str,
    level: int = logging.DEBUG
) -> logging.Logger:
    """
    Get or create a task-specific file logger.

    Creates a logger that writes to a file in the task's logs directory.
    Each logger writes to its own file: {name}.log

    Args:
        name: Logger name (e.g., "pipeline", "intake", "search")
        job_id: Job identifier
        task_id: Task identifier
        level: Logging level (default: DEBUG)

    Returns:
        logging.Logger: Configured file logger
    """
    # Create unique logger key
    logger_key = f"{job_id}_{task_id}_{name}"

    # Return cached logger if exists
    if logger_key in _task_loggers:
        return _task_loggers[logger_key]

    # Set up logs directory
    logs_dir = setup_task_logging(job_id, task_id)

    # Create logger
    logger = logging.getLogger(f"task.{logger_key}")
    logger.setLevel(level)
    logger.propagate = False  # Don't propagate to root logger

    # Create file handler
    log_file = logs_dir / f"{name}.log"
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(level)

    # Create formatter with timestamps
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(file_handler)

    # Cache logger
    _task_loggers[logger_key] = logger

    return logger


def log_divider(logger: logging.Logger, title: Optional[str] = None) -> None:
    """
    Log a visual divider for readability.

    Args:
        logger: Logger to write to
        title: Optional title for the divider
    """
    if title:
        logger.debug("=" * 80)
        logger.debug(f" {title}")
        logger.debug("=" * 80)
    else:
        logger.debug("-" * 80)


def log_multiline(logger: logging.Logger, message: str, data: str, max_lines: int = 50) -> None:
    """
    Log a message with multiline data, truncating if too long.

    Args:
        logger: Logger to write to
        message: Header message
        data: Multiline data to log
        max_lines: Maximum number of lines to log (default: 50)
    """
    logger.debug(message)
    lines = data.split('\n')

    if len(lines) > max_lines:
        # Log first half and last few lines with truncation notice
        first_chunk = lines[:max_lines // 2]
        last_chunk = lines[-(max_lines // 4):]

        for line in first_chunk:
            logger.debug(line)
        logger.debug(f"... [TRUNCATED {len(lines) - max_lines} lines] ...")
        for line in last_chunk:
            logger.debug(line)
    else:
        for line in lines:
            logger.debug(line)


def cleanup_task_loggers(job_id: str, task_id: str) -> None:
    """
    Clean up and close file handlers for a task's loggers.

    Args:
        job_id: Job identifier
        task_id: Task identifier
    """
    prefix = f"{job_id}_{task_id}_"

    # Find all loggers for this task
    loggers_to_remove = [key for key in _task_loggers if key.startswith(prefix)]

    # Close handlers and remove from cache
    for logger_key in loggers_to_remove:
        logger = _task_loggers[logger_key]

        # Close all file handlers
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

        # Remove from cache
        del _task_loggers[logger_key]