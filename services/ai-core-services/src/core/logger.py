import logging
import sys

try:
    from pythonjsonlogger.json import JsonFormatter
except ImportError:
    from pythonjsonlogger.jsonlogger import JsonFormatter

from src.core.config import settings


def get_logger(name: str = "ai-service") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(settings, "LOG_LEVEL", "INFO").upper())

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(filename)s %(lineno)s %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

    return logger


logger = get_logger()
