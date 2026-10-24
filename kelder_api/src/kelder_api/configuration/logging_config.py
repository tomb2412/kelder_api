DEFAULT_FORMAT = '[{levelname}] - {asctime} - {parent_module} : {message}'
#NOTE - delete this as unused
COMPONENT_FORMAT = '[{levelname}] - {asctime} - {component} - {module} : {message}'

DEFAULT_DATE_FORMAT = '%d/%m/%Y %H:%M:%S'
DEFAULT_FILENAME = "logs/text_log.log"
DEFAULT_JSON_CONFIG = {
    "filename": "logs/json/json_log.json",
    "when": "midnight",
    "backupCount": 5
}

log_conf = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "base_filter": {
            "()": "src.kelder_api.configuration.logging_controller.ComponentFilter",
            "service": "root"
        }
    },
    "formatters":
        {
            "simple": {
                "class": "src.kelder_api.configuration.logging_controller.TruncatingFilePathFormatter",
                "format": DEFAULT_FORMAT,
                "style": '{',
                "datefmt": DEFAULT_DATE_FORMAT,
            },
            "json": {

            }
        },
    "handlers":
        {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "simple",
            },
            "log_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "level": "DEBUG",
                "formatter": "simple",
                "filename": DEFAULT_FILENAME,
                "when": "midnight",
                "backupCount": 5
            }
        },
    "root": {
        "level": "DEBUG",
        "handlers": ["log_file", "console"]
    }
}