import functools
import inspect
from typing import Any, Callable, Union

from django.db import IntegrityError
from pydantic import ValidationError as PydanticValidationError

from src.shared.domain.exceptions import (
    ApplicationError,
    DomainError,
    InfrastructureError,
)
from src.shared.infrastructure.cache.idempotency_lock import (
    release_fast_path_lock,
    try_acquire_fast_path_lock,
)
from src.shared.infrastructure.logging import LogDomain, get_logger
from src.shared.presentation.schema.context import Info
from src.shared.presentation.schema.responses import (
    BaseErrorResponse,
    IntegrityErrorResponse,
    InternalErrorResponse,
    ValidationErrorResponse,
)

logger = get_logger(LogDomain.QUIZ)


def handle_mutations_exceptions(func: Callable) -> Callable:
    """
    Decorator for GraphQL mutation handlers.

    Automatically catches and maps exceptions to typed error responses:
    - DomainError, ApplicationError → ValidationErrorResponse
    - InfrastructureError → IntegrityErrorResponse
    - PydanticValidationError → ValidationErrorResponse
    - Django IntegrityError → IntegrityErrorResponse
    - Exception (catch-all) → InternalErrorResponse

    Logs each exception automatically with log_tag and error details.
    Supports both async and sync functions.
    """

    @functools.wraps(func)
    async def async_wrapper(
        self, info: Info, *args, **kwargs
    ) -> Union[BaseErrorResponse, Any]:
        log_tag = f"{self.__class__.__name__}.{func.__name__}"
        correlation_id = info.context.correlation_id
        operation_id = info.context.operation_id

        if not await try_acquire_fast_path_lock(operation_id):
            logger.info(
                "duplicate_operation_in_flight",
                log_tag=log_tag,
                correlation_id=correlation_id,
                operation_id=operation_id,
            )
            return IntegrityErrorResponse(
                correlation_id=correlation_id,
                message=(
                    "A request with this operation_id is already being "
                    "processed; retry shortly."
                ),
            )

        try:
            try:
                return await func(self, info, *args, **kwargs)

            except (DomainError, ApplicationError) as exc:
                logger.warning(
                    f"{exc.__class__.__name__}",
                    log_tag=log_tag,
                    correlation_id=correlation_id,
                    error=str(exc),
                )
                return ValidationErrorResponse(
                    correlation_id=correlation_id,
                    message=str(exc),
                    field=None,
                )

            except PydanticValidationError as exc:
                error_msg = ", ".join([e["msg"] for e in exc.errors()])
                logger.warning(
                    "ValidationError",
                    log_tag=log_tag,
                    correlation_id=correlation_id,
                    error=error_msg,
                )
                return ValidationErrorResponse(
                    correlation_id=correlation_id,
                    message=error_msg,
                    field=None,
                )

            except InfrastructureError as exc:
                logger.warning(
                    f"{exc.__class__.__name__}",
                    log_tag=log_tag,
                    correlation_id=correlation_id,
                    error=str(exc),
                )
                return IntegrityErrorResponse(
                    correlation_id=correlation_id,
                    message=str(exc),
                )

            except IntegrityError as exc:
                logger.warning(
                    "IntegrityError",
                    log_tag=log_tag,
                    correlation_id=correlation_id,
                    error=str(exc),
                )
                return IntegrityErrorResponse(
                    correlation_id=correlation_id,
                    message="Database integrity violation.",
                )

            except Exception as exc:
                logger.error(
                    "InternalError",
                    log_tag=log_tag,
                    correlation_id=correlation_id,
                    error=str(exc),
                    exc_info=True,
                )
                return InternalErrorResponse(
                    correlation_id=correlation_id,
                    message="Unexpected internal error.",
                )
        finally:
            # Pure short-lived mutex, not the correctness guarantee (that's
            # the Postgres unique constraint on IdempotencyKey.operation_id
            # a use case may enforce via IdempotencyReservationRepository) —
            # always release so a legitimate later retry with this same
            # operation_id isn't blocked by a stale in-flight lock.
            await release_fast_path_lock(operation_id)

    @functools.wraps(func)
    def sync_wrapper(
        self, info: Info, *args, **kwargs
    ) -> Union[BaseErrorResponse, Any]:
        log_tag = f"{self.__class__.__name__}.{func.__name__}"
        correlation_id = info.context.correlation_id
        # Accessed (not just declared) so the required-header check runs for
        # every mutation, sync included — no Redis fast-path lock here: the
        # shared Redis client is `redis.asyncio`-only, and every mutation in
        # this codebase is async today (see mutation-idempotency-rate-limit
        # tasks.md 4.1).
        info.context.operation_id

        try:
            return func(self, info, *args, **kwargs)

        except (DomainError, ApplicationError) as exc:
            logger.warning(
                f"{exc.__class__.__name__}",
                log_tag=log_tag,
                correlation_id=correlation_id,
                error=str(exc),
            )
            return ValidationErrorResponse(
                correlation_id=correlation_id,
                message=str(exc),
                field=None,
            )

        except PydanticValidationError as exc:
            error_msg = ", ".join([e["msg"] for e in exc.errors()])
            logger.warning(
                "ValidationError",
                log_tag=log_tag,
                correlation_id=correlation_id,
                error=error_msg,
            )
            return ValidationErrorResponse(
                correlation_id=correlation_id,
                message=error_msg,
                field=None,
            )

        except InfrastructureError as exc:
            logger.warning(
                f"{exc.__class__.__name__}",
                log_tag=log_tag,
                correlation_id=correlation_id,
                error=str(exc),
            )
            return IntegrityErrorResponse(
                correlation_id=correlation_id,
                message=str(exc),
            )

        except IntegrityError as exc:
            logger.warning(
                "IntegrityError",
                log_tag=log_tag,
                correlation_id=correlation_id,
                error=str(exc),
            )
            return IntegrityErrorResponse(
                correlation_id=correlation_id,
                message="Database integrity violation.",
            )

        except Exception as exc:
            logger.error(
                "InternalError",
                log_tag=log_tag,
                correlation_id=correlation_id,
                error=str(exc),
                exc_info=True,
            )
            return InternalErrorResponse(
                correlation_id=correlation_id,
                message="Unexpected internal error.",
            )

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
