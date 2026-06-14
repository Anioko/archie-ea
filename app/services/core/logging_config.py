"""
Structured Logging Configuration

Configures application-wide logging with:
- JSON formatting for production
- Detailed formatting for development
- Rotating file handlers
- Separate error log
"""

import logging
import logging.config
import os
from pathlib import Path


def setup_logging(app_env: str = "development"):
    """
    Setup structured logging based on environment

    Args:
        app_env: Environment (development/production/testing)
    """

    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Determine log level
    log_level = "DEBUG" if app_env == "development" else "INFO"

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "[%(asctime)s] %(levelname)-8s [%(name)s:%(lineno)d] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "simple": {"format": "%(levelname)s: %(message)s"},
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d",
            }
            if app_env == "production"
            else {"format": "[%(asctime)s] %(levelname)-8s %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "detailed" if app_env == "development" else "simple",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": "json" if app_env == "production" else "detailed",
                "filename": "logs/app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json" if app_env == "production" else "detailed",
                "filename": "logs/errors.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
                "encoding": "utf-8",
            },
            "import_audit_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json" if app_env == "production" else "detailed",
                "filename": "logs/import_audit.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            # Root logger
            "": {"level": log_level, "handlers": ["console", "file", "error_file"]},
            # App logger
            "app": {
                "level": log_level,
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            # Service-specific loggers
            "app.services": {
                "level": log_level,
                "handlers": ["file", "error_file"],
                "propagate": False,
            },
            "app.services.llm_service": {
                "level": log_level,
                "handlers": ["file", "error_file"],
                "propagate": False,
            },
            "app.services.archimate": {
                "level": log_level,
                "handlers": ["file", "error_file"],
                "propagate": False,
            },
            # Import audit logger — dedicated log for import operations
            "import_audit": {
                "level": "INFO",
                "handlers": ["import_audit_file", "file"],
                "propagate": False,
            },
            # Suppress noisy third-party loggers
            "werkzeug": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "urllib3": {"level": "WARNING", "handlers": ["file"], "propagate": False},
        },
    }

    logging.config.dictConfig(logging_config)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured for {app_env} environment")
    logger.info(f"Log files: logs/app.log, logs/errors.log")


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
