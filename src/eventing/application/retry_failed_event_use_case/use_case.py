import asyncio
import functools
import importlib
from inspect import iscoroutinefunction

from src.eventing.application.retry_failed_event_use_case.dto import RetryFailedEventDTO
from src.eventing.domain.entities.failed_event_message_entity import (
    FailedEventMessageEntity,
)
from src.eventing.domain.exceptions import FailedEventMessageNotFoundError
from src.eventing.domain.repositories.failed_event_message_repository import (
    FailedEventMessageRepository,
)
from src.shared.infrastructure.event_bus import EventBusMessage
from src.shared.infrastructure.logging import LogDomain, get_logger

logger = get_logger(LogDomain.EVENTING)


def _resolve_channel(channel_path: str):
    module_path, qualname, member_name = channel_path.split(":")
    module = importlib.import_module(module_path)
    enum_cls = functools.reduce(getattr, qualname.split("."), module)
    return enum_cls[member_name]


def _resolve_handler(handler_path: str):
    module_path, qualname = handler_path.split(":")
    module = importlib.import_module(module_path)
    return functools.reduce(getattr, qualname.split("."), module)


class RetryFailedEventUseCase:
    """
    Re-invokes exactly the handler that failed for a dead-letter record —
    not the whole channel — so handlers that already succeeded the first
    time around don't run again. Re-raises if the retry fails again (the
    row is left as PENDING with an updated error and a bumped retry_count
    so the failure is still visible and retryable).
    """

    def __init__(self, repository: FailedEventMessageRepository) -> None:
        self.repository = repository

    def execute(self, dto: RetryFailedEventDTO) -> FailedEventMessageEntity:
        failed_event = self.repository.get_by_id(dto.failed_event_id)
        if failed_event is None:
            raise FailedEventMessageNotFoundError(dto.failed_event_id)

        channel = _resolve_channel(failed_event.channel_path)
        handler = _resolve_handler(failed_event.handler_path)

        message = EventBusMessage(
            channel=channel,
            resource_name=failed_event.resource_name,
            correlation_id=str(failed_event.correlation_id),
            data=failed_event.payload,
            metadata=failed_event.metadata or {},
        )

        try:
            if iscoroutinefunction(handler):
                asyncio.run(handler(message))
            else:
                handler(message)
        except Exception as exc:  # noqa: BLE001
            updated = self.repository.mark_retry_failed(
                dto.failed_event_id,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            logger.warning(
                "failed_event_retry_failed",
                failed_event_id=str(dto.failed_event_id),
                correlation_id=str(updated.correlation_id),
                error=repr(exc),
            )
            raise
        else:
            updated = self.repository.mark_resolved(dto.failed_event_id)
            logger.info(
                "failed_event_retried",
                failed_event_id=str(dto.failed_event_id),
                correlation_id=str(updated.correlation_id),
            )
            return updated
