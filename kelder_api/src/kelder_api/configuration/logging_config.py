from __future__ import annotations

import logging
from logging.config import dictConfig

LOG_FORMAT = "%(levelname)s | %(asctime)s | %(module_short)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_BASE_CONFIGURED = False


class ComponentFilter(logging.Filter):
    """Adds a shortened logger name for readable container log output."""

    def __init__(self, component: str) -> None:
        super().__init__()
        self.component = component

    def filter(self, record: logging.LogRecord) -> bool:
        record.component = self.component
        record.module_short = self._shorten_name(record.name)
        return True

    @staticmethod
    def _shorten_name(name: str) -> str:
        if not name:
            return "root"
        parts = name.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return parts[0]


def setup_logging(component: str) -> None:
    """Send logs to the container stream for Docker-managed rotation."""
    global _BASE_CONFIGURED

    # Configure the root stream once. Docker retains a bounded copy per container.
    if not _BASE_CONFIGURED:
        dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "filters": {
                    "base_filter": {
                        "()": "src.kelder_api.configuration.logging_config.ComponentFilter",
                        "component": "root",
                    }
                },
                "formatters": {
                    "standard": {
                        "format": LOG_FORMAT,
                        "datefmt": DATE_FORMAT,
                    }
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO",
                        "formatter": "standard",
                        "filters": ["base_filter"],
                    },
                },
                "root": {
                    "handlers": ["console"],
                    "level": "DEBUG",
                },
            }
        )
        _BASE_CONFIGURED = True

    logger = logging.getLogger(component)
    logger.setLevel(logging.DEBUG)
    logger.propagate = True
