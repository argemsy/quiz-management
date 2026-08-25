## Context

See proposal.md - Why for motivation. Constraints that shape the approach:

- `CreateQuizUseCase` (`src/quiz/application/create_quiz_use_case/use_case.py`) is the only use case in the codebase injected with a repository (`IdempotencyReservationRepository`) instead of only services. Every other use case (`LoginUseCase`, `SwitchTenantUseCase`, `CreateQuestionsUseCase`) already only receives services — this design brings the outlier in line, it isn't inventing a new convention from scratch.
- `IdempotencyReservationRepository` (port) / `IdempotencyReservationRepositoryImpl` (in `eventing`, owns the `IdempotencyKey` model) already exist and are unaffected — only the caller changes, from the use case directly to a new service.
- `Context.correlation_id` / `Context.operation_id` (`src/shared/presentation/schema/context.py`) are both plain `str`, sourced from HTTP headers with no format validation. `EventBusMessage.correlation_id` (`src/shared/infrastructure/event_bus/messages.py`) is also `str`, with a `default_factory=lambda: str(uuid.uuid4())` — i.e. the bus deliberately allows an internally-generated correlation id when there's no inbound request to propagate one from. Any new shared DTO mixin must match this `str` convention rather than tightening it to `uuid.UUID`, which would fight a deliberate existing design choice.
- `src/shared/` currently has `domain/`, `infrastructure/`, `presentation/` but no `application/` layer (per `CLAUDE.md`'s documented structure) — this design introduces it for the first time, hosting cross-cutting application-layer concerns with no single owning app (mirrors how `IdempotencyReservationRepository`'s port already lives in `src/shared/domain/repositories/` for the same "no owner" reason).
- `RecordAuditLogDTO` (`src/eventing/application/record_audit_log_use_case/dto.py`) already declares its own `correlation_id: uuid.UUID | None` field, populated exclusively from `event.correlation_id` in `audit_event_handlers.py` (`EventBusMessage.correlation_id`, never `None` in practice since the bus's `default_factory` guarantees a value).
- `QuestionEntity.__post_init__` (`src/quiz/domain/entities/question_entity.py`) raises a bare `ValueError`, not a `DomainError` subclass — `_validate_questions` in `CreateQuizUseCase` calls it before anything else runs, so this exception is on the direct path being touched here.

## Goals / Non-Goals

**Goals:**
- Establish and apply, in the same change, a concrete rule: use cases (`application/*/use_case.py`) receive only services; only services (`application/*/*_service.py`, and the new `IdempotencyService`) receive repositories.
- Give every use case DTO that has an actual need for `correlation_id` and/or `operation_id` a consistent, reusable shape instead of ad-hoc fields or loose `execute()` parameters — via interface-segregated mixins, not one combined base class forced onto every DTO regardless of need.
- Fix the two concrete gaps found while tracing this: `CreateQuestionsDTO` dropping `EventBusMessage.correlation_id`, and `QuestionEntity`'s bare `ValueError` misclassifying as an internal error.

**Non-Goals:**
- Retrofitting `RetryFailedEventDTO`/`PersistFailedEventDTO` (Django-admin-triggered, no HTTP request in scope) with either id — there is no value to source them from; forcing placeholders would be worse than leaving them out.
- Validating that `correlation_id`/`operation_id` header values are actually well-formed UUIDs. They stay unvalidated `str` end-to-end, matching `Context`'s and `EventBusMessage`'s existing behavior. Out of scope here; a separate concern if it ever becomes a real problem.
- Changing anything about `IdempotencyReservationRepository`'s port contract, `IdempotencyKey`'s data model, or the Redis fast-path lock in `mutation_handler.py` — all untouched, only their caller moves.
- A generic decorator around use case `execute()` methods for logging or exception translation. Explicitly rejected for `CreateQuizUseCase` in this change (see Decisions) — `@handle_mutations_exceptions` at the resolver already owns exception-to-response mapping, and no second layer of interception is added.

## Decisions

**`IdempotencyReservationRepository` moves into a new `IdempotencyService` (`src/shared/application/idempotency_service.py`), not into `QuizService`.** Alternative considered: give `QuizService` a `create_with_idempotency()` method that owns both `QuizRepository` and `IdempotencyReservationRepository`. Rejected because it would permanently couple "how a Quiz is persisted" with "how any mutation's idempotency key is reserved" inside one entity-specific service — the latter is generic infrastructure (reserve → run a caller-supplied write → mark terminal) with no dependency on `Quiz` at all, and `tasks.md` (from `mutation-idempotency-rate-limit`) already flags this as "the next mutation this pattern gets extended to." A standalone service keeps that extension point reusable without teaching every future entity-service about idempotency semantics.
```python
class IdempotencyService:
    def __init__(self, repository: IdempotencyReservationRepository) -> None:
        self.repository = repository

    async def run(self, operation_id: str, write: Callable[[], T]) -> T:
        return await self.repository.reserve_and_run(operation_id, write)

    async def mark_success(self, operation_id: str, response_payload: dict) -> None:
        await self.repository.mark_terminal(
            operation_id, IdempotencyOutcome.SUCCEEDED, response_payload
        )
```
`CreateQuizUseCase` calls `self.idempotency_service.run(...)` then `.mark_success(...)` — same two calls as today, just routed through a service instead of the raw repository. `DuplicateOperationError` still propagates unchanged (it's raised by the repository impl, `IdempotencyService` doesn't catch it) all the way to the resolver's existing `except DuplicateOperationError` handling — no change needed there.

**Two interface-segregated mixins (`CorrelationIdDTO`, `OperationIdDTO`), not one combined base.** Alternative considered: a single `TraceableDTO(correlation_id, operation_id)` every use case DTO inherits from uniformly. Rejected — verified against every current use case that only `CreateQuizDTO` has an idempotency-protected write; forcing `operation_id` onto `LoginDTO`/`SwitchTenantDTO`/`RefreshSessionDTO`/`CreateQuestionsDTO` would mean either a fake value or an unused field with no real contract behind it. Segregating means each DTO's inheritance list documents exactly which cross-cutting concerns it actually participates in — `CreateQuizDTO(CreateQuizFields, CorrelationIdDTO, OperationIdDTO)` vs. `LoginDTO(LoginFields, CorrelationIdDTO)` is legible on its own, no need to check usage elsewhere to know whether a field is load-bearing.

**Mixin fields are `str`, matching `Context`/`EventBusMessage`, not `uuid.UUID`.** Already the working assumption confirmed with the user; documented here for the record. Consequence: `RecordAuditLogDTO.correlation_id` narrows from `uuid.UUID | None` to `str` (required) when it adopts `CorrelationIdDTO` — confirmed safe by reading `audit_event_handlers.py`: both call sites (`execute_many` batch path and single-record path) always pass `event.correlation_id`, and `EventBusMessage.correlation_id`'s `default_factory` guarantees it's never absent. The Django `AuditLog.correlation_id` model field (a `UUIDField`) is unaffected — Django's ORM already converts a well-formed UUID string on save, same as it does today when Pydantic hands it a `uuid.UUID` object; the validation boundary just moves from "Pydantic parses the header string into a `UUID` object" to "Django parses the same string at save time," which is a wash in practice since nothing today sends a malformed value.

**`CreateQuestionsDTO` gains `CorrelationIdDTO`; `handle_questions_requested` threads `event.correlation_id` through.** One-line fix at the call site (`quiz_event_handlers.py:20-25`), closing the trace gap identified in proposal.md - Why.

**`QuestionEntity`'s `ValueError` becomes `InvalidQuestionError(DomainError)`.** New exception in `src/quiz/domain/exceptions.py`, next to `TenantNotFoundError`/`TenantUserNotFoundError`. `@handle_mutations_exceptions` already maps any `DomainError` to `ValidationErrorResponse` — no decorator or resolver change needed beyond the exception's own class.

**`CreateQuizUseCase.execute()` takes a single `dto: CreateQuizDTO` parameter; no decorator, no try/except is added around it.** The event-bus-publish-on-failure guard the user asked for ("evitemos propagar el mensaje al eventbus si no es exitosa la creación del quiz") is satisfied structurally, not with an explicit check: `IdempotencyService.run()` re-raises whatever `IdempotencyReservationRepository.reserve_and_run()` raises (`DuplicateOperationError` on replay, or the underlying write's own exception on a genuine failure) — it never returns a sentinel on failure. Because `execute()` has no try/except, any exception raised there — from `_validate_questions`, `TenantValidationService`, or `IdempotencyService.run()` — unwinds the function immediately, so the `event_bus.publish(...)` line physically cannot execute unless everything before it succeeded. This is the same control-flow guarantee the code already relies on today; formalizing "no decorator, no try/except" here is a decision to keep relying on it rather than adding a redundant explicit guard.

## Risks / Trade-offs

- [`src/shared/application/` is a new precedent — first time `shared` has an application layer] → Accepted: mirrors the existing precedent of `IdempotencyReservationRepository`'s port living in `src/shared/domain/repositories/` for the same "cross-cutting, no single owning app" reason. `CLAUDE.md`'s project-structure section needs a one-line addition once this ships (tracked in tasks.md).
- [`RecordAuditLogDTO.correlation_id` narrowing from `uuid.UUID | None` to `str` is technically breaking for any caller outside `audit_event_handlers.py`] → No such caller exists today (verified by grep); accepted as a same-change fix rather than a deprecation cycle, consistent with this project's early-stage/no-back-compat-shims convention (`project_early_stage` memory).
- [Segregated mixins mean a future DTO's author must actively decide which mixin(s) apply, rather than getting both "for free"] → Accepted trade-off, it's the point: an unused id field silently sitting on a DTO forever is worse than a two-second decision per new use case.

## Migration Plan

- No database migration — `IdempotencyKey`'s schema, the Redis fast-path lock, and the idempotency port/impl are untouched.
- Pure code refactor plus one Pydantic field-type narrowing (`RecordAuditLogDTO.correlation_id`). No dual-read/back-compat path needed (no external caller of that DTO).
- Rollback: revert the commit(s); no data migration to reverse.
