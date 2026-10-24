import copy
import json
import logging
from datetime import datetime, timezone
from logging.config import dictConfig
from pathlib import Path

from src.kelder_api.configuration.logging_config import (
    DEFAULT_JSON_CONFIG,
    LOG_DIR,
    log_conf,
)


def extract_parent_module(file_path: str) -> str:
    pathname = file_path.replace(".py", "")
    return ".".join(pathname.split("/")[-2:])


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, timezone.utc)

        out = {
            "ts": ts.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "name": record.name,
            "service": getattr(record, "service", "-"),
            "component": getattr(record, "component", "-"),
            "parent_module": extract_parent_module(record.pathname),
            "msg": record.getMessage(),
            "logger": record.name,
        }

        data = getattr(record, "data", None)
        if data:
            out["data"] = data
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


class TruncatingFilePathFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.parent_module = extract_parent_module(record.pathname)

        return super(TruncatingFilePathFormatter, self).format(record)


class ComponentFilter(logging.Filter):
    """Adds a component name for readable container log output."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service
        return True


def setup_logging(service: str, config: dict = log_conf):
    config = copy.deepcopy(config)
    json_config = copy.deepcopy(DEFAULT_JSON_CONFIG)
    service_log_dir = Path(LOG_DIR) / service.lower()

    file_configs = [
        handler_config
        for handler_config in config.get("handlers", {}).values()
        if handler_config.get("filename")
    ] + [json_config]
    for file_config in file_configs:
        file_path = service_log_dir / file_config["filename"]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_config["filename"] = str(file_path)

    dictConfig(config)

    handler = logging.handlers.TimedRotatingFileHandler(**json_config)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(
        ComponentFilter(
            service=service,
        )
    )
    logger = logging.getLogger()
    logger.addHandler(hdlr=handler)

    logger = logging.getLogger(__name__)
    logger.info("Dict config set")


def get_logger(name: str, component: str) -> logging.Logger:
    logger = logging.getLogger(name)
    return logging.LoggerAdapter(logger, {"component": component})
