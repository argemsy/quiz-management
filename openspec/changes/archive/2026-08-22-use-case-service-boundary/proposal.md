## Why

`CreateQuizUseCase` (added by `mutation-idempotency-rate-limit`) injects `IdempotencyReservationRepository` directly — the only use case in the codebase that receives a repository instead of a service. Every other use case (`LoginUseCase`, `SwitchTenantUseCase`, `CreateQuestionsUseCase`) already only receives services, so this is a one-off deviation, not an established pattern, and it's worth codifying the boundary explicitly before a second use case copies the shortcut. Separately, `correlation_id`/`operation_id` are threaded into `CreateQuizUseCase.execute()` as loose parameters instead of living on its DTO, and three adjacent gaps surfaced while tracing how these ids flow through the system: `CreateQuestionsDTO` silently drops `EventBusMessage.correlation_id` (breaking the trace chain from `create_quiz` through to the questions it creates), `RecordAuditLogDTO` declares its own one-off `correlation_id: uuid.UUID | None` instead of a shared shape, and `QuestionEntity.__post_init__` raises a bare `ValueError` that the mutation decorator can't distinguish from an internal error, surfacing "a question needs at least one answer choice" as `InternalErrorResponse` instead of `ValidationErrorResponse`.

## What Changes

- New rule: `quiz`, `account`, and `eventing` use cases (`application/*/use_case.py`) MUST only receive services in `__init__`; only services (`application/*/*_service.py`) may receive repositories. Documented as a new mandatory pattern.
- Extract `IdempotencyReservationRepository` out of `CreateQuizUseCase` into a new `IdempotencyService` (`src/shared/application/idempotency_service.py`) wrapping `reserve_and_run`/`mark_terminal`. `CreateQuizUseCase` now receives 4 services and zero repositories.
- New shared DTO mixins, `src/shared/application/dto.py`: `CorrelationIdDTO` (`correlation_id: str`) and `OperationIdDTO` (`operation_id: str`), interface-segregated — a DTO inherits from either, both, or neither based on actual need, never both by default.
- `CreateQuizDTO` gains both mixins (`correlation_id`/`operation_id` move from `execute()` parameters onto the DTO). `LoginDTO`, `SwitchTenantDTO`, `RefreshSessionDTO`, `CreateQuestionsDTO` gain `CorrelationIdDTO` only (no idempotency-protected write in any of them). `RetryFailedEventDTO`/`PersistFailedEventDTO` (Django-admin-triggered, no HTTP request context) gain neither.
- Fix: `quiz_event_handlers.py::handle_questions_requested` passes `event.correlation_id` into `CreateQuestionsDTO` instead of discarding it — restores the trace chain from `create_quiz` through to `questions_created`.
- `RecordAuditLogDTO.correlation_id` migrates from its ad-hoc `uuid.UUID | None` field to inherit `CorrelationIdDTO` (`str`, required) — verified every caller (`audit_event_handlers.py`) always supplies a value (`EventBusMessage.correlation_id` has a non-null `default_factory`), so the `| None` was unused defensiveness, not a real case. **BREAKING for direct callers of `RecordAuditLogDTO`** (none exist outside `audit_event_handlers.py` today): the field type changes from `uuid.UUID` to `str`.
- `CreateQuizUseCase.execute()` signature collapses to a single `dto: CreateQuizDTO` parameter (no decorator, no try/except — see design.md for why the event-bus-publish-on-failure guard doesn't need either).
- `QuestionEntity.__post_init__`'s bare `ValueError` becomes a proper domain exception (new `InvalidQuestionError(DomainError)` in `src/quiz/domain/exceptions.py`), so `@handle_mutations_exceptions` maps it to `ValidationErrorResponse` instead of `InternalErrorResponse`.
- Update `CLAUDE.md` mandatory patterns and `docs/claude/mandatory-patterns.md` to document the use-case/service boundary rule (planned as a documentation task, applied once the code actually complies — not before).

## Capabilities

No entry — this is an internal architecture/DDD-layering refactor (dependency-injection boundaries, DTO base classes, exception classification) with no product-level requirement change. The one user-visible effect (an invalid question now returns `ValidationErrorResponse` instead of `InternalErrorResponse`) corrects behavior against mandatory pattern #4's already-documented exception mapping (`DomainError` → `ValidationErrorResponse`); it doesn't introduce a new rule, it makes real behavior match the existing one. `skip_specs: true` set in `.openspec.yaml` accordingly.

## Impact

- `src/shared/application/` (new directory): `dto.py` (`CorrelationIdDTO`, `OperationIdDTO`), `idempotency_service.py` (`IdempotencyService`)
- `src/quiz/application/create_quiz_use_case/{dto.py,use_case.py}` — DTO gains mixins, `execute()` single-parameter, `IdempotencyReservationRepository` replaced by `IdempotencyService`
- `src/quiz/application/create_questions_use_case/dto.py`, `src/quiz/infrastructure/event_handlers/quiz_event_handlers.py` — `CorrelationIdDTO` + threading the id through
- `src/account/application/{login_use_case,switch_tenant_use_case,refresh_session_use_case}/dto.py` — `CorrelationIdDTO`, plus each resolver passing `correlation_id` into the DTO
- `src/eventing/application/record_audit_log_use_case/dto.py`, `src/eventing/infrastructure/event_handlers/audit_event_handlers.py` — migrate to `CorrelationIdDTO`
- `src/quiz/domain/exceptions.py` — new `InvalidQuestionError`; `src/quiz/domain/entities/question_entity.py` — raises it instead of `ValueError`
- `src/account/presentation/schema/mutations/mutations_admin.py`, `src/quiz/presentation/schema/mutations/mutations_admin.py` — resolvers build DTOs with the id fields instead of passing them as separate `execute()` args
- `CLAUDE.md`, `docs/claude/mandatory-patterns.md` — new mandatory pattern documented
