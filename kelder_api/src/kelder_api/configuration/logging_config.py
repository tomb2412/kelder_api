from __future__ import annotations

import logging
from datetime import datetime, timedelta
from logging.config import dictConfig
from pathlib import Path

LOG_FORMAT = "%(levelname)s | %(asctime)s | %(module_short)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
AGGREGATE_FILENAME = "app-info.log"
_CONFIGURED_COMPONENTS: set[str] = set()
_BASE_CONFIGURED = False
RETENTION_DAYS = 14


class ComponentFilter(logging.Filter):
    """Injects the component name so the formatter can reference %(component)s."""

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


def _log_directory(provided: str | Path | None = None) -> Path:
    if provided is not None:
        return Path(provided)
    # NOTE I think this adds to root/app/logs in the container
    default_dir = Path(__file__).resolve().parents[3] / "logs"
    default_dir.mkdir(parents=True, exist_ok=True)
    return default_dir


def _purge_old_logs(log_root: Path) -> None:
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    for file_path in log_root.glob("*.log"):
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        except OSError:
            continue
        if mtime < cutoff:
            try:
                file_path.unlink()
            except OSError:
                pass


def setup_logging(component: str, log_dir: str | Path | None = None) -> None:
    """Configure logging handlers for a given component."""
    global _BASE_CONFIGURED

    log_root = _log_directory(log_dir)
    log_root.mkdir(parents=True, exist_ok=True)
    _purge_old_logs(log_root)

    # Configure the shared root handlers once (console + aggregate).
    if not _BASE_CONFIGURED:
        aggregate_log = log_root / AGGREGATE_FILENAME
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
                    "aggregate_file": {
                        "class": "logging.FileHandler",
                        "level": "INFO",
                        "filename": str(aggregate_log),
                        "encoding": "utf-8",
                        "formatter": "standard",
                        "filters": ["base_filter"],
                    },
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO",
                        "formatter": "standard",
                        "filters": ["base_filter"],
                    },
                },
                "root": {
                    "handlers": ["aggregate_file", "console"],
                    "level": "DEBUG",
                },
            }
        )
        _BASE_CONFIGURED = True

    if component in _CONFIGURED_COMPONENTS:
        return

    # Add a dedicated handler for this component logger without reconfiguring root.
    component_log = log_root / f"{component}.log"
    handler = logging.FileHandler(component_log, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    handler.addFilter(ComponentFilter(component))

    logger = logging.getLogger(component)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = True

    _CONFIGURED_COMPONENTS.add(component)
