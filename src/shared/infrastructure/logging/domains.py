from enum import StrEnum


class LogDomain(StrEnum):
    """
    One entry per bounded context.

    Every log line emitted through ``get_logger(LogDomain.X)`` carries a
    ``domain`` field set to this value, so logs can be filtered/labeled by
    bounded context once they're shipped to Grafana/Loki/Prometheus.
    """

    IDENTITY = "identity"
    QUIZ = "quiz"
    TENANT = "tenant"
    EVENTING = "eventing"
    SHARED = "shared"
