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

### 3. `operation_id` for mutation idempotency
**Rule**: `operation_id` **ALWAYS** comes from the client via `X-Operation-ID` header. **NEVER** generate server-side.

❌ **WRONG**:
```python
@cached_property
def operation_id(self) -> str:
    if not (req := self.request):
        return get_operation_id()  # server generates — breaks idempotency!
    return req.headers.get("X-Operation-ID") or get_operation_id()
```

✅ **CORRECT**:
```python
@cached_property
def operation_id(self) -> str:
    if not (req := self.request):
        raise ValueError("operation_id requires HTTP request context")
    operation_id = req.headers.get("X-Operation-ID")
    if not operation_id:
        raise ValueError(
            "X-Operation-ID header is required for mutation idempotency. "
            "Client must generate and send a unique UUID per request."
        )
    return operation_id  # return what client sent, never generate
```

**Why**: If the server generates a new ID on each retry, the operation isn't idempotent — duplicate execution results. The client must own the ID and resend the same one on network retry. This is enforced by failing fast if the header is missing.

**Example**: `src/shared/presentation/schema/context.py`, `Context.operation_id`

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
        return CreateQuizPayload(operation_id=info.context.operation_id, payload=quiz)
    except DomainError as e:
        return ValidationErrorResponse(operation_id=..., message=str(e))
    except InfrastructureError as e:
        return IntegrityErrorResponse(operation_id=..., message=str(e))
    # ... repeat for other exceptions
```

✅ **GOOD**:
```python
@strawberry.mutation(permission_classes=[IsStaff])
@handle_mutations_exceptions
async def create_quiz(self, info: Info, input: CreateQuizInput) -> CreateQuizResponse:
    operation_id = info.context.operation_id
    dto = CreateQuizDTO.model_validate(strawberry.asdict(input))
    quiz_entity = await use_case.execute(dto, operation_id)
    return CreateQuizPayload(operation_id=operation_id, payload=QuizType(value=quiz_entity))
```

The decorator (`src/shared/presentation/decorators/mutation_handler.py`) handles all exception mapping:
- `DomainError`/`ApplicationError` → `ValidationErrorResponse`
- `InfrastructureError` → `IntegrityErrorResponse`
- `pydantic.ValidationError` → `ValidationErrorResponse`
- `django.db.IntegrityError` → `IntegrityErrorResponse`
- Any other `Exception` → `InternalErrorResponse` (logged with `exc_info=True`)

All responses carry `operation_id`.

**Example**: `src/quiz/presentation/schema/mutations/mutations_admin.py`
