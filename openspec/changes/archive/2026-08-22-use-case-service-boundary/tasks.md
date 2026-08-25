## 1. Shared application layer foundation

- [x] 1.1 Create `src/shared/application/__init__.py` (new layer, doesn't exist yet)
- [x] 1.2 Add `src/shared/application/dto.py` with `CorrelationIdDTO` (`correlation_id: str`) and `OperationIdDTO` (`operation_id: str`), both `BaseModel` with `ConfigDict(frozen=True)`, per design.md - Decisions
- [x] 1.3 Add `src/shared/application/idempotency_service.py::IdempotencyService`, wrapping `IdempotencyReservationRepository` with `run(operation_id, write)` (delegates to `reserve_and_run`) and `mark_success(operation_id, response_payload)` (delegates to `mark_terminal` with `IdempotencyOutcome.SUCCEEDED`)

## 2. CreateQuizUseCase refactor

- [x] 2.1 `CreateQuizDTO` (`src/quiz/application/create_quiz_use_case/dto.py`) inherits `CorrelationIdDTO` and `OperationIdDTO` in addition to its existing fields
- [x] 2.2 `CreateQuizUseCase.__init__` (`use_case.py`) replaces `idempotency_repository: IdempotencyReservationRepository` with `idempotency_service: IdempotencyService`
- [x] 2.3 `CreateQuizUseCase.execute` collapses to a single `dto: CreateQuizDTO` parameter (drop the standalone `correlation_id`/`operation_id` args); reads both from `dto.correlation_id`/`dto.operation_id` internally; calls `self.idempotency_service.run(...)` / `.mark_success(...)` instead of the repository directly
- [x] 2.4 No decorator, no try/except added around `execute()` — confirm (via the test in 7.2) that the event-bus publish is structurally unreachable on any failure path, per design.md's control-flow argument
- [x] 2.5 `mutations_admin.py::create_quiz` resolver (`src/quiz/presentation/schema/mutations/mutations_admin.py`) builds `CreateQuizDTO` with `correlation_id`/`operation_id` included (from `info.context`), passes only `dto` to `use_case.execute(...)`; constructs `IdempotencyService(idempotency_repo_imp.IdempotencyReservationRepositoryImpl())` instead of the repository impl directly

## 3. QuestionEntity exception classification

- [x] 3.1 Add `InvalidQuestionError(DomainError)` to `src/quiz/domain/exceptions.py`
- [x] 3.2 `QuestionEntity.__post_init__` (`src/quiz/domain/entities/question_entity.py`) raises `InvalidQuestionError` instead of `ValueError`
- [x] 3.3 Update any existing test asserting the old `ValueError` (grep `pytest.raises(ValueError)` around `QuestionEntity`) to expect `InvalidQuestionError` — verified: no existing test referenced `QuestionEntity` or its `ValueError`, nothing to update

## 4. CreateQuestionsDTO tracing fix

- [x] 4.1 `CreateQuestionsDTO` (`src/quiz/application/create_questions_use_case/dto.py`) inherits `CorrelationIdDTO`
- [x] 4.2 `handle_questions_requested` (`src/quiz/infrastructure/event_handlers/quiz_event_handlers.py`) passes `correlation_id=event.correlation_id` when building the DTO
- [x] 4.3 `CreateQuestionsUseCase.execute`'s existing `logger.info("questions_created", ...)` includes `correlation_id=dto.correlation_id`

## 5. Account app DTOs

- [x] 5.1 `LoginDTO`, `SwitchTenantDTO`, `RefreshSessionDTO` (each app's `dto.py` under `src/account/application/`) inherit `CorrelationIdDTO`
- [x] 5.2 Each use case's success log (`LoginUseCase`'s `"user_logged_in"`, `SwitchTenantUseCase`'s `"tenant_switched"`, `RefreshSessionUseCase`'s equivalent) includes `correlation_id=dto.correlation_id`
- [x] 5.3 `mutations_admin.py` (`src/account/presentation/schema/mutations/mutations_admin.py`) — `login`, `switch_tenant`, `refresh_session` resolvers build their DTO with `correlation_id=info.context.correlation_id` included

## 6. Eventing app: RecordAuditLogDTO migration

- [x] 6.1 `RecordAuditLogDTO` (`src/eventing/application/record_audit_log_use_case/dto.py`) drops its ad-hoc `correlation_id: uuid.UUID | None` field and inherits `CorrelationIdDTO` instead (`correlation_id: str`, required)
- [x] 6.2 Confirm both call sites in `audit_event_handlers.py::_to_dto` (single-record and `records` batch paths) still compile against the narrower type — no code change needed, verified by full eventing test suite passing
- [x] 6.3 Check `AuditLogRepositoryImpl` (wherever `RecordAuditLogDTO.correlation_id` is written to the `AuditLog.correlation_id` `UUIDField`) still round-trips correctly with a plain `str` input — found `AuditLogEntity.correlation_id` is domain-modeled as `uuid.UUID` (matching `from_model`'s read path and `FailedEventMessageEntity`'s precedent), so `RecordAuditLogUseCase._to_entity` now does the one explicit `uuid.UUID(dto.correlation_id)` parse at the DTO→entity boundary

## 7. Tests

- [x] 7.1 Update `tests/quiz/.../test_create_quiz*.py` (idempotency tests from `mutation-idempotency-rate-limit`) for the new `CreateQuizUseCase.execute(dto)` single-parameter signature and `CreateQuizDTO`'s new required fields — verified no test constructs `CreateQuizDTO`/`CreateQuizUseCase` directly (all go through the GraphQL resolver), nothing to update
- [x] 7.2 Add/adjust a test asserting that when `IdempotencyService.run` raises (simulating a write failure), `EventBus.publish` is never called — new `tests/quiz/application/create_quiz_use_case/test_use_case.py` (2 tests: generic failure, `DuplicateOperationError`)
- [x] 7.3 Add a test for `InvalidQuestionError` surfacing as `ValidationErrorResponse` (not `InternalErrorResponse`) through `create_quiz`'s full GraphQL stack, for a question with zero answer choices — added to `tests/quiz/presentation/schema/test_create_quiz_idempotency.py`
- [x] 7.4 Add/adjust a test confirming `handle_questions_requested` propagates `correlation_id` from the `QUESTIONS_REQUESTED` event into `CreateQuestionsDTO` and the `"questions_created"` log — new `tests/quiz/infrastructure/event_handlers/test_quiz_event_handlers.py`
- [x] 7.5 Run the full suite (`make test`) and confirm no regressions from the `RecordAuditLogDTO` field-type narrowing — 103/103 passed; `black`/`isort`/`flake8` clean on all files touched by this change

## 8. Documentation

- [x] 8.1 Add a new mandatory pattern to `CLAUDE.md` and `docs/claude/mandatory-patterns.md`: use cases (`application/*/use_case.py`) receive only services; only services receive repositories — with `CreateQuizUseCase`/`IdempotencyService` as the reference example
- [x] 8.2 Add a one-line mention of `src/shared/application/` to `CLAUDE.md`'s project-structure section (first time `shared` has this layer)
- [x] 8.3 Confirm `CLAUDE.md` is still ≤300 lines after both additions; move overflow to `docs/claude/mandatory-patterns.md` if not — 168 lines, well within budget
