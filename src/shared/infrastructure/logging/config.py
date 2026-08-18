import logging.config
import sys

import structlog


def configure_logging(*, json_logs: bool, log_level: str = "INFO") -> None:
    """
    Wires structlog to stdlib logging so every domain logger (see
    ``get_logger``) and every third-party/stdlib log line (Django included)
    get shipped through the same handler with the same shape.

    Call this exactly once, from settings, before anything logs.

    Args:
        json_logs: True renders line-delimited JSON (what a log shipper
            feeding Loki/Elasticsearch/etc. expects). False renders colored,
            human-readable console output (local dev).
        log_level: Root logger level.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "structlog": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": renderer,
                    "foreign_pre_chain": shared_processors,
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "structlog",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
        }
    )
