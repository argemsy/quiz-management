import threading

from src.shared.infrastructure.event_bus.bus import EventBus


class EventBusRegistry:
    """
    Holds the single, process-wide ``EventBus`` instance.

    This is a thread-safe lazy holder, not an EventBus itself — it doesn't
    publish or subscribe to anything, it just guarantees every caller gets
    the same shared bus. Each app registers its own handlers against that
    shared instance from its own ``AppConfig.ready()`` (same place admin
    registration already happens), so this module never needs to import
    domain-specific handlers itself.
    """

    _instance: EventBus | None = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> EventBus:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = EventBus()
        return cls._instance

    @classmethod
    def reset_for_tests(cls) -> None:
        """Only for use in test fixtures."""
        cls._instance = None


def get_event_bus() -> EventBus:
    return EventBusRegistry.get_instance()
