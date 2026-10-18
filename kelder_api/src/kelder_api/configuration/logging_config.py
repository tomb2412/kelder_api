DEFAULT_FORMAT = '{levelname} : {asctime} : {module} : {message}'
COMPONENT_FORMAT = '{levelname} : {asctime} : {component} : {module} : {message}'

DEFAULT_DATE_FORMAT = '%d/%m/%Y %H:%M:%S'
DEFAULT_FILENAME = "practice_logging.log"


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
        "handlers": ["log_file"]
    }
}