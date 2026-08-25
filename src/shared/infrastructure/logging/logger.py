import structlog

from src.shared.infrastructure.logging.domains import LogDomain


def get_logger(domain: LogDomain | str) -> structlog.stdlib.BoundLogger:
    """
    Returns a structlog logger pre-bound with ``domain``, so every entry
    logged through it is already taggable/filterable by bounded context.

    Safe to call at import time (before ``configure_logging`` runs) —
    structlog returns a lazy proxy that only resolves the real config on
    first use.
    """
    return structlog.get_logger().bind(domain=str(domain))
