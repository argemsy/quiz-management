# Mandatory patterns and rules

> Referenced from `CLAUDE.md` (kept there as a one-line summary per rule to stay under its 300-line cap). Full rationale and code examples live here.

These are hard requirements established through development. Violating them will break the system or make code review requests fail.

---

### 1. Never ORM writes in loops
**Rule**: Pre-generate UUIDs, accumulate in lists, then `bulk_create()` once.

❌ **BAD**:
```python
for question in questions:
    QuestionModel.objects.create(quiz=quiz, text=question.text)  # N queries
```

✅ **GOOD**:
```python
questions_to_create = [
    QuestionModel(id=uuid.uuid4(), quiz=quiz, text=q.text) for q in questions
]
QuestionModel.objects.bulk_create(questions_to_create)  # 1 query
```

**Why**: Prevents N+1 queries, atomic by design when using `transaction.atomic()`.

**Example**: `src/quiz/infrastructure/repositories/question_repository_imp.py`

**Variant — loop and write split across layers via the event bus**: the rule applies to the *end-to-end* effect of a code path, not just whether the method you're editing has a literal `for` loop next to a `.create()`. A method whose own DB write is already a single query can still be this anti-pattern if it loops and calls `get_event_bus().publish()` once per object, and each publish synchronously triggers an in-process handler in a *different* app that does its own single-row `.create()`.

❌ **BAD**:
```python
# account/presentation/admin/mixins.py
for obj in queryset:
    event_bus.publish(EventBusMessage(channel=..., data={"id": obj.id, ...}))  # N events
    # -> eventing/infrastructure/event_handlers/audit_event_handlers.py handles each
    #    one synchronously, calling AuditLog.objects.create() -> N single-row INSERTs
```

✅ **GOOD**:
```python
# account/presentation/admin/mixins.py
for chunk in batched(queryset.iterator(chunk_size=1000), 1000):
    event_bus.publish(EventBusMessage(channel=..., data={"records": [...]}))  # 1 event per chunk
    # -> handler branches on data["records"] and calls execute_many(),
    #    which uses AuditLogRepositoryImpl.record_many() -> bulk_create()
```

**Watch for in review**: any Django admin `@admin.action` — its `queryset` argument is not bounded by page size ("select all N matching your search" routinely produces 10k-100k+ rows), so "small, manually curated selection" is not a safe assumption to justify skipping batching. Fix both halves: `.iterator(chunk_size=1000)` on the read side (stream, don't materialize the whole selection into a list) and `bulk_create()` (via a `record_many()`/`execute_many()` pair mirroring the existing singular methods) on the write side.

**Example**: `src/account/presentation/admin/mixins.py::AuditableAdminMixin._bulk_update_with_audit` (BAD→GOOD both visible in git history).

---

### 2. Cross-app dependencies: port pattern
**Rule**: Consumer defines interface in its `domain/repositories/`, producer implements in its `infrastructure/repositories/*_imp.py` importing only its own models.

❌ **BAD**:
```python
# quiz/presentation/mutations.py
from src.account.infrastructure.persistence.django.models import TenantModel
if TenantModel.objects.filter(id=tenant_id).exists():  # violates isolation
    ...
```

✅ **GOOD**:
```python
# quiz/domain/repositories/tenant_lookup_repository.py (port)
class TenantLookupRepository(ABC):
    @abstractmethod
    async def tenant_exists(self, tenant_id: uuid.UUID) -> bool:
        pass

# account/infrastructure/repositories/tenant_lookup_repository_imp.py (producer impl)
class TenantLookupRepositoryImpl(TenantLookupRepository):
    @async_database()
    def tenant_exists(self, tenant_id: uuid.UUID) -> bool:
        return TenantModel.objects.filter(id=tenant_id, is_active=True).exists()

# quiz/presentation/schema/mutations/mutations_admin.py (injection)
use_case = CreateQuizUseCase(
    quiz_service,
    TenantValidationService(TenantLookupRepositoryImpl()),  # injected at presentation
    event_bus
)
```

**Why**: Decouples quiz from account's model structure. If account changes its schema, quiz is unaffected. Consumer owns the contract, producer chooses implementation. Clear dependency: consumer ← producer.

**Example**: `src/quiz/domain/repositories/tenant_lookup_repository.py` ↔ `src/account/infrastructure/repositories/tenant_lookup_repository_imp.py`

---

### 3. `correlation_id` (tracing) and `operation_id` (idempotency) — two client-supplied ids, never server-generated
**Rule**: Every mutation request carries **two** distinct client-supplied ids — `correlation_id` (`X-Correlation-ID`) for tracing, `operation_id` (`X-Operation-ID`) for idempotency. Both **ALWAYS** come from the client. **NEVER** generate either server-side. Fail fast (raise) if either header is missing.

Before `mutation-idempotency-rate-limit`, a single `operation_id` did both jobs at once (echoed in every response purely for log correlation, while its docstring already claimed — inaccurately, since no dedup logic existed yet — that it was "for idempotency"). The two concerns were split once real idempotency enforcement was built, because they have different lifecycles: `correlation_id` is required and read on **every** mutation (`mutation_handler.py`'s `async_wrapper` accesses it unconditionally); `operation_id` is likewise required on every mutation (same fail-fast enforcement, so no mutation is exempt), but only a use case that's actually wired for idempotency (currently `create_quiz` — see `IdempotencyReservationRepository` in pattern 2's cross-app example) does anything with it beyond the required-header check and the generic Redis fast-path lock.

❌ **WRONG**:
```python
@cached_property
def correlation_id(self) -> str:
    if not (req := self.request):
        return str(uuid.uuid4())  # server generates — breaks tracing across a real retry!
    return req.headers.get("X-Correlation-ID") or str(uuid.uuid4())
```

✅ **CORRECT** (`src/shared/presentation/schema/context.py`):
```python
@cached_property
def correlation_id(self) -> str:
    if not (req := self.request):
        raise ValueError("correlation_id requires HTTP request context")
    correlation_id = req.headers.get("X-Correlation-ID")
    if not correlation_id:
        raise ValueError(
            "X-Correlation-ID header is required to trace a mutation "
            "and everything it publishes. Client must generate and send "
            "a unique UUID per request."
        )
    return correlation_id

@cached_property
def operation_id(self) -> str:
    if not (req := self.request):
        raise ValueError("operation_id requires HTTP request context")
    operation_id = req.headers.get("X-Operation-ID")
    if not operation_id:
        raise ValueError(
            "X-Operation-ID header is required for mutation idempotency. "
            "Client must generate and send a unique UUID per mutation "
            "attempt, never server-side."
        )
    return operation_id
```

**Why**: If the server generates either id, the guarantee it exists for breaks. For `correlation_id`: a server-generated id on a network retry can't be tied back to the original attempt's logs/events, defeating tracing. For `operation_id`: a server-generated id changes on every retry, so the operation isn't idempotent — duplicate execution results. The client owns both ids and resends the *same* `operation_id` — never a new `correlation_id`, since a retry is still logically the same attempt for tracing purposes too — on a network retry of the same logical action; it mints a **new** `operation_id` only after seeing a terminal response (success or business/validation error), never after an unresolved attempt. Both are enforced by failing fast if their header is missing.

**Idempotency enforcement itself** (not just carrying the id) has two layers, and Redis alone is *not* the guarantee:
- **Redis fast-path** (`src/shared/infrastructure/cache/idempotency_lock.py`): a short-TTL `SET NX EX` lock, purely to skip a Postgres round-trip for the common duplicate-click case. Fails open on Redis being unreachable — it isn't the correctness guarantee, so failing open here doesn't risk a duplicate record.
- **Postgres unique constraint** (`IdempotencyKey.operation_id`, owned by `eventing` — see `IdempotencyReservationRepository.reserve_and_run`): the actual guarantee. The reservation insert and the mutation's business write happen in one `transaction.atomic()` block; a repeated `operation_id` surfaces as `IntegrityError` on the unique constraint, which `reserve_and_run` turns into `DuplicateOperationError` for the caller to handle (replay the prior outcome) instead of re-executing.

**Example**: `src/shared/presentation/schema/context.py` (`Context.correlation_id`/`Context.operation_id`); `src/quiz/application/create_quiz_use_case/use_case.py` + `src/quiz/presentation/schema/mutations/mutations_admin.py` (`create_quiz`/`_replay_create_quiz`) for a full reference implementation of the enforcement layers above.

---

### 4. Mutation exception handling via decorator
**Rule**: Use `@handle_mutations_exceptions` on all mutations. Never use manual `try/except`.

❌ **BAD**:
```python
@strawberry.mutation
async def create_quiz(self, info: Info, input: CreateQuizInput) -> CreateQuizResponse:
    try:
        dto = CreateQuizDTO.model_validate(strawberry.asdict(input))
        quiz = await use_case.execute(dto)
        return CreateQuizPayload(correlation_id=info.context.correlation_id, payload=quiz)
    except DomainError as e:
        return ValidationErrorResponse(correlation_id=..., message=str(e))
    except InfrastructureError as e:
        return IntegrityErrorResponse(correlation_id=..., message=str(e))
    # ... repeat for other exceptions
```

✅ **GOOD**:
```python
@strawberry.mutation(permission_classes=[IsStaff])
@handle_mutations_exceptions
async def create_quiz(self, info: Info, input: CreateQuizInput) -> CreateQuizResponse:
    correlation_id = info.context.correlation_id
    dto = CreateQuizDTO.model_validate(
        {**strawberry.asdict(input), "correlation_id": correlation_id, "operation_id": info.context.operation_id}
    )
    quiz_entity = await use_case.execute(dto)  # ids travel on the DTO, not as loose args — see pattern 5
    return CreateQuizPayload(correlation_id=correlation_id, payload=QuizType(value=quiz_entity))
```

The decorator (`src/shared/presentation/decorators/mutation_handler.py`) handles all exception mapping:
- `DomainError`/`ApplicationError` → `ValidationErrorResponse`
- `InfrastructureError` → `IntegrityErrorResponse`
- `pydantic.ValidationError` → `ValidationErrorResponse`
- `django.db.IntegrityError` → `IntegrityErrorResponse`
- Any other `Exception` → `InternalErrorResponse` (logged with `exc_info=True`)

All responses carry `correlation_id`. The decorator also enforces `operation_id`'s required-header check and the Redis idempotency fast-path lock (pattern 3) on every mutation — a use case wired for full idempotency enforcement carries `operation_id` on its DTO as shown in pattern 5's example, and its resolver catches `DuplicateOperationError` to replay a prior outcome instead of returning it as a new error.

**Example**: `src/quiz/presentation/schema/mutations/mutations_admin.py`

---

### 5. Use cases receive only services; only services receive repositories
**Rule**: `application/*/use_case.py` constructors take services (`*Service`, `IdempotencyService`, `EventBus`) — never a `domain/repositories/` port directly. If a use case needs a repository-backed operation, wrap it in a service first.

❌ **BAD**:
```python
# quiz/application/create_quiz_use_case/use_case.py
class CreateQuizUseCase:
    def __init__(
        self,
        quiz_service: QuizService,
        idempotency_repository: IdempotencyReservationRepository,  # a repository, not a service
    ) -> None:
        self.idempotency_repository = idempotency_repository

    async def execute(self, dto: CreateQuizDTO, correlation_id: str, operation_id: str) -> QuizEntity:
        quiz = await self.idempotency_repository.reserve_and_run(operation_id, ...)
        await self.idempotency_repository.mark_terminal(operation_id, ...)
        ...
```

✅ **GOOD**:
```python
# shared/application/idempotency_service.py — generic wrapper, reusable by any use case
class IdempotencyService:
    def __init__(self, repository: IdempotencyReservationRepository) -> None:
        self.repository = repository

    async def run(self, operation_id: str, write: Callable[[], T]) -> T:
        return await self.repository.reserve_and_run(operation_id, write)

    async def mark_success(self, operation_id: str, response_payload: dict) -> None:
        await self.repository.mark_terminal(operation_id, IdempotencyOutcome.SUCCEEDED, response_payload)

# quiz/application/create_quiz_use_case/use_case.py
class CreateQuizUseCase:
    def __init__(
        self,
        quiz_service: QuizService,
        tenant_validation_service: TenantValidationService,
        event_bus: EventBus,
        idempotency_service: IdempotencyService,  # a service, wrapping the repository itself
    ) -> None:
        self.idempotency_service = idempotency_service

    async def execute(self, dto: CreateQuizDTO) -> QuizEntity:
        quiz = await self.idempotency_service.run(dto.operation_id, ...)
        await self.idempotency_service.mark_success(dto.operation_id, ...)
        ...
```

**Why**: A use case orchestrates business steps; a service owns how one of those steps is actually persisted. Letting a use case reach for a repository directly blurs that line and tends to spread repository-specific plumbing (transaction wrapping, retry semantics) into orchestration code that should stay declarative. `IdempotencyReservationRepository` is cross-cutting infra with no single owning app (same reasoning as its port living in `src/shared/domain/repositories/`, not `eventing`'s domain) — `IdempotencyService` is its equally-owner-less wrapper, so the next mutation that needs idempotency reuses it instead of re-deriving the pattern.

**Related**: `CreateQuizDTO`, and every other use case DTO invoked from a GraphQL mutation resolver, additionally carries `correlation_id`/`operation_id` via the interface-segregated mixins `CorrelationIdDTO`/`OperationIdDTO` (`src/shared/application/dto.py`) instead of `execute()` taking them as loose parameters — a DTO inherits only the mixin(s) it actually needs (e.g. `CreateQuizDTO` needs both; `LoginDTO` needs only `CorrelationIdDTO`, no idempotency-protected write). This keeps a use case's full input — business fields and cross-cutting ids alike — in one immutable, typed place.

**Example**: `src/quiz/application/create_quiz_use_case/use_case.py` (`CreateQuizUseCase`), `src/shared/application/idempotency_service.py` (`IdempotencyService`), `src/shared/application/dto.py` (`CorrelationIdDTO`/`OperationIdDTO`).
