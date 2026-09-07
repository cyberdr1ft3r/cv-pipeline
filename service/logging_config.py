import logging
import sys
from typing import Dict, Any
from pythonjsonlogger import jsonlogger

def setup_logging() -> Dict[str, logging.Logger]:
    """Setup structured JSON logging for the application"""

    # Create JSON formatter
    json_formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)

    # Create specific loggers
    app_logger = logging.getLogger("cv_pipeline.app")
    security_logger = logging.getLogger("cv_pipeline.security")
    request_logger = logging.getLogger("cv_pipeline.request")
    perf_logger = logging.getLogger("cv_pipeline.performance")

    return {
        "app": app_logger,
        "security": security_logger,
        "request": request_logger,
        "performance": perf_logger,
    }

# Initialize loggers
loggers = setup_logging()
app_logger = loggers["app"]
security_logger = loggers["security"]
request_logger = loggers["request"]
perf_logger = loggers["performance"]