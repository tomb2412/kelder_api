import copy
from datetime import datetime, timezone
import logging
from logging.config import dictConfig
import json

from src.kelder_api.configuration.logging_config import log_conf

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, timezone.utc)

        out = {
            "ts": ts.isoformat(timespec='milliseconds').replace("+00:00", "Z"),
            "level":record.levelname.lower(),
            "name": record.name,
            "service": getattr(record, "service", "-"),
            "component": getattr(record, "component", "-"),
            "msg": record.getMessage(),
            "logger": record.name,
        }

        data = getattr(record, "data", None)
        if data:
            out["data"] = data
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)

class ComponentFilter(logging.Filter):
    """Adds a component name for readable container log output."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service
        return True

def setup_logging(service: str, config: dict = log_conf):
        dictConfig(copy.deepcopy(config))

        handler = logging.StreamHandler()
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