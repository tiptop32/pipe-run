import logging.config


def setup_logging(level: str = "INFO") -> None:
    logging.config.dictConfig(get_logging(level))


def get_logging(level: str = "INFO") -> dict:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)-8s %(name)s %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
        "loggers": {
            "uvicorn": {"propagate": True},
            "sqlalchemy.engine": {"level": "WARNING", "propagate": True},
        },
    }
