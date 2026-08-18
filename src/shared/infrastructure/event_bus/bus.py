import asyncio
from collections import defaultdict
from enum import Enum
from inspect import iscoroutinefunction
from typing import Awaitable, Callable, Optional, TypeVar, Union

from src.shared.infrastructure.event_bus.messages import EventBusMessage
from src.shared.infrastructure.logging import LogDomain, get_logger

logger = get_logger(LogDomain.SHARED)

MessageT = TypeVar("MessageT", bound=EventBusMessage)
AsyncEventBusHandler = Callable[[MessageT], Awaitable[None]]
SyncEventBusHandler = Callable[[MessageT], None]
EventBusHandler = Union[AsyncEventBusHandler, SyncEventBusHandler]
FailureSink = Callable[[EventBusMessage, EventBusHandler, Exception], None]


class EventBus:
    """
    In-memory Event Bus implementing the Publisher-Subscriber pattern.

    Accepts both sync and async handlers per channel:
      - Async handlers run as background asyncio tasks (fire-and-forget),
        bounded by a semaphore so a burst of events can't spawn unbounded
        concurrent work. If ``publish`` is called with no event loop running
        (e.g. from a synchronous Django admin action), there's no loop to
        schedule a background task on, so the async handler is run to
        completion via ``asyncio.run`` instead — it still executes safely,
        just not concurrently with the rest of the request.
      - Sync handlers run inline, synchronously, right where ``publish`` is
        called. This is what makes it safe to call ``publish`` directly from
        a Django admin action or any other purely synchronous code path.

    A single failing handler is caught and logged; it never takes down the
    bus or the other subscribers for that channel.
    """

    def __init__(self, max_concurrency: int = 10) -> None:
        self._handlers: dict[Enum, list[EventBusHandler]] = defaultdict(list)
        self._background_tasks: set[asyncio.Task] = set()
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._failure_sink: Optional[FailureSink] = None

    def set_failure_sink(self, sink: FailureSink) -> None:
        """
        Registers a callback invoked (best-effort, in addition to the
        warning log) whenever a handler raises — e.g. to persist a
        dead-letter record so the failed message can be inspected and
        retried later. A broken sink is itself caught and logged; it never
        breaks the bus.
        """
        self._failure_sink = sink

    @property
    def handlers(self) -> dict[Enum, list[EventBusHandler]]:
        return {
            channel: handlers
            for channel, handlers in self._handlers.items()
            if handlers
        }

    def subscribe(self, channel: Enum, handler: EventBusHandler) -> None:
        """Registers a sync or async handler for a channel."""
        self._handlers[channel].append(handler)

    def publish(self, event: EventBusMessage) -> None:
        """
        Publishes an event to every handler subscribed to its channel.

        Safe to call from sync or async code, and safe to call when nobody
        is subscribed yet (a no-op, not an error — publishers shouldn't need
        to know whether anyone is listening).
        """
        handlers = self._handlers.get(event.channel, [])
        if not handlers:
            logger.debug(
                "event_bus_no_handlers",
                channel=event.channel.name,
                correlation_id=event.correlation_id,
            )
            return

        for handler in handlers:
            if iscoroutinefunction(handler):
                self._dispatch_async(handler, event)
            else:
                self._call_sync(handler, event)

    def _dispatch_async(
        self, handler: AsyncEventBusHandler, event: EventBusMessage
    ) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop (e.g. called from a sync admin action): there's
            # nowhere to schedule a background task, so run it to completion
            # now instead of silently dropping it.
            asyncio.run(self._safe_async_call(handler, event))
            return

        task = loop.create_task(self._safe_async_call(handler, event))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _call_sync(self, handler: SyncEventBusHandler, event: EventBusMessage) -> None:
        try:
            handler(event)
        except Exception as exc:  # noqa: BLE001
            self._handle_handler_error(handler, event, exc)

    async def _safe_async_call(
        self, handler: AsyncEventBusHandler, event: EventBusMessage
    ) -> None:
        async with self._semaphore:
            try:
                await handler(event)
            except Exception as exc:  # noqa: BLE001
                self._handle_handler_error(handler, event, exc)

    def _handle_handler_error(
        self, handler: EventBusHandler, event: EventBusMessage, exc: Exception
    ) -> None:
        logger.warning(
            "event_bus_handler_failed",
            handler=getattr(handler, "__name__", repr(handler)),
            channel=event.channel.name,
            correlation_id=event.correlation_id,
            error=repr(exc),
        )

        if self._failure_sink is None:
            return

        try:
            self._failure_sink(event, handler, exc)
        except Exception as sink_exc:  # noqa: BLE001
            logger.warning(
                "event_bus_failure_sink_failed",
                correlation_id=event.correlation_id,
                error=repr(sink_exc),
            )

    async def wait_until_finished(self) -> None:
        """Awaits every in-flight background task spawned by async handlers."""
        if pending_tasks := set(self._background_tasks):
            await asyncio.gather(*pending_tasks, return_exceptions=True)
