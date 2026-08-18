# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

**quiz-management** is a system for managing exams ("Proyecto para la gestión de Exámenes"). The repository is **active** with real implementation: `src/`, `tests/`, `devops/`, and `openspec/` all exist and contain working code organized around 4 Django apps with full or partial DDD layering (quiz, eventing with complete domain/application/infrastructure/presentation; tenant and identity with infrastructure + presentation only, domain/application empty).

## Tech stack

- **Python 3.12+** (3.14 pinned via `.python-version`). Dependency management via Poetry.

- **HTTP layer: Django + FastAPI (two separate services)**
  - Django 6.1 serves the admin interface (`manage.py`, `main/wsgi.py`, port 8000)
  - FastAPI 0.141 serves GraphQL (port 8500), with `strawberry.fastapi.GraphQLRouter` mounted in `main/asgi.py`
  - These are two independent processes in `devops/docker-compose.yaml` (`admin` and `api` services), not composed together

- **GraphQL**: `strawberry-graphql` (federation schema), JWT auth via `PyJWT`, custom permission classes (`IsAuthenticated`, `IsAdmin`, `IsStaff`, `IsOrganizationUser`) in `src/shared/presentation/schema/permissions.py`. No Django permission system.

- **Database**: Postgres 15 (via `psycopg2-binary` + `dj-database-url`). Custom user model `src.identity.infrastructure.persistence.django.models.user.MyUser(AbstractUser)` with UUID primary key, set as `AUTH_USER_MODEL = "identity.MyUser"`. Note: a stray `quiz_db.sqlite3` at repo root is not the configured backend (residual local dev artifact).

- **Event bus**: In-process, in-memory pub/sub (`src/shared/infrastructure/event_bus/`), singleton via `get_event_bus()`. Sync handlers run inline, async handlers as asyncio tasks in background. **No Redis/Kafka/SQS**. Dead-letter pattern: `src/eventing/` app registers a `failure_sink` (`PersistFailedEventUseCase`) that persists failed dispatches as `FailedEventMessage` models, retryable via `retry_failed_event_use_case`.

- **Testing**: `pytest` + `pytest-django` + `pytest-asyncio`. Real `tests/` directory with 27 tests (eventing: full coverage of dto/use_case/domain/repo/end-to-end; quiz: infra constraint tests). Fixtures in `tests/fixtures/`, `tests/conftest.py`.

- **Linting**: `black` + `isort` (profile: black, line-length: 88) + `flake8` (max-line-length: 88, extend-ignore: E203). Config in `pyproject.toml` and `.flake8`.

- **Additional**: `nanoid` (short IDs), `structlog` (logging), `factory-boy` (test factories), `freezegun` (time mocking), `syrupy` (snapshot testing), `python-dotenv`, `asgiref`, `pyjwt`, `httpx`.

## Project structure

```
main/                  Django project (admin): settings (base.py, tests.py), asgi.py, wsgi.py, 
                       urls.py, project_settings.py (pydantic-settings for env config)

src/
  quiz/                Full DDD: domain/{entities,repositories,exceptions}, 
                       application/<use_case>/{dto,use_case,*_service},
                       infrastructure/{persistence/django/models,repositories,event_handlers},
                       presentation/{admin,schema/{inputs,mutations,responses,types}}, shared/

  eventing/            Full DDD (dead-letter/outbox for event bus): 
                       domain/{entities,repositories,exceptions},
                       application/{persist_failed_event_use_case,retry_failed_event_use_case},
                       infrastructure/{persistence/django/models,repositories},
                       presentation/{admin}

  tenant/              Infrastructure + presentation only (domain/application empty):
                       infrastructure/{persistence/django/models,repositories},
                       presentation/admin

  identity/            Infrastructure + presentation only (domain/application empty):
                       infrastructure/persistence/django/models (user.py),
                       presentation/admin

  shared/              Cross-cutting (no per-app separation):
                       domain/exceptions.py, infrastructure/{event_bus,logging,persistence/django/models.py},
                       presentation/{admin/mixins,decorators/mutation_handler,schema/{context,permissions,responses,schema,types,auth}}

tests/                 pytest suite: mirrors src/ by app; tests/fixtures/, tests/conftest.py

devops/                Dockerfile, docker-compose.yaml, docker.env(.example)
                       [Note: devops/terraform/ does NOT exist yet — Makefile targets tf-* are stubs]

openspec/              Spec-driven change tracking: specs/quiz/{attempt-result,question-response,tenant-scoping},
                       changes/archive/ (3 archived changes)
```

## Mandatory patterns and rules

These are hard requirements established through development. Violating them will break the system or make code review requests fail.

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

---

### 2. Cross-app dependencies: port pattern
**Rule**: Consumer defines interface in its `domain/repositories/`, producer implements in its `infrastructure/repositories/*_imp.py` importing only its own models.

❌ **BAD**:
```python
# quiz/presentation/mutations.py
from src.tenant.infrastructure.persistence.django.models import TenantModel
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

# tenant/infrastructure/repositories/tenant_lookup_repository_imp.py (producer impl)
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

**Why**: Decouples quiz from tenant's model structure. If tenant changes its schema, quiz is unaffected. Consumer owns the contract, producer chooses implementation. Clear dependency: consumer ← producer.

**Example**: `src/quiz/domain/repositories/tenant_lookup_repository.py` ↔ `src/tenant/infrastructure/repositories/tenant_lookup_repository_imp.py`

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

---

## Code style conventions

### Imports
- **Absolute imports always**: `from src.<app>.<layer>...` (never relative except in `__init__.py` re-exports).
- **Order**: stdlib → third-party → `src.` local, alphabetical within each group.
- All `src.` modules are importable as `src.app.*` because `src/` is the Python package root.

### Type hints
- **Complete**: all function parameters and return types are typed.
- **DTOs** (application layer): Pydantic `BaseModel` with `model_config = ConfigDict(frozen=True)`.
- **Entities** (domain layer): `@dataclass(frozen=True)` with `__post_init__` validation. Never Pydantic.

### Async/sync convention
- **Use case + repo interfaces (ABC)**: `async def`
- **Repo implementations**: `def` (sync), decorated with `@async_database()` from `src/shared/infrastructure/persistence/django/models.py`. This wraps `sync_to_async(thread_sensitive=True)` and retries once on `InterfaceError`/`OperationalError`.
- The ABC/impl signature mismatch (async vs sync) is the convention; not a bug.

### Exceptions
**Hierarchy** (in `src/shared/domain/exceptions.py`):
```
DomainError (base)
  ├─ NotFoundError
  ├─ ApplicationError (validation, orchestration failures)
  └─ InfrastructureError (persistence, external services)
```

Per-app exceptions subclass these (e.g., `TenantNotFoundError(NotFoundError)` in `src/quiz/domain/exceptions.py`).

### Entity ↔ Model mapping
- **Model → Entity**: `Entity.from_model(cls, instance)` classmethod on the entity.
- **Entity → Model**: Ad hoc, inline in the repository implementation (no symmetric `to_model()`). This asymmetry is the current convention.

### Repositories
- **Naming**: `*Repository` (ABC in `domain/repositories/`), `*RepositoryImpl` (impl in `infrastructure/repositories/*_repository_imp.py`).
- **Pattern**: consistent ABC + `@abstractmethod` interfaces, Django implementations.

### Naming conventions
- Use cases: `<verb>_<noun>_use_case/` package (e.g., `create_quiz_use_case/`) with `dto.py`, `use_case.py`, optional `*_service.py`.
- Domain: `*Entity` (frozen dataclass), `*Repository` (ABC).
- Infra: `*RepositoryImpl` (file: `*_repository_imp.py`), `*Model` (Django).
- Presentation (GraphQL): `*Input` (strawberry input), `*Response`/`*Payload` (response wrappers), `*Type` (strawberry types).
- Exceptions: `*Error`.
- Event channels: `*EventChannel` enums.

### Docstrings
- **Only when non-obvious**: rationale for a design choice, e.g., why a port exists (cross-app reason), why validation happens in `__post_init__` vs the constructor. 
- **None on trivial code**: don't restate the signature or method name.
- **Inline comments rare**: same principle — explain *why*, not *what*.

### GraphQL response pattern
```python
# Input
@strawberry.input
class CreateQuizInput:
    ...

# Use case produces an entity
quiz_entity = await use_case.execute(dto, operation_id)

# Response: union of error types + success Payload
CreateQuizResponse = strawberry.union(
    "CreateQuizResponse",
    (ValidationErrorResponse, IntegrityErrorResponse, InternalErrorResponse, CreateQuizPayload)
)

# Payload wraps the entity type
@strawberry.type
class CreateQuizPayload:
    operation_id: str
    payload: QuizType

# Type wraps the domain entity (held in Private so it doesn't get serialized)
@strawberry.type
class QuizType:
    @strawberry.field
    def id(self) -> strawberry.ID:
        return strawberry.ID(str(self.value.id))
    
    @strawberry.field
    def name(self) -> str:
        return self.value.name
    
    # ... more fields
```

### Primary keys
All Django models use UUID: `id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`.

---

## Commands

Most commands run through Docker Compose via the `Makefile`. See `Makefile` for the full list.

```bash
make help            # list all available targets

# Code quality
make lint            # black + isort + flake8 on src/ and tests/
make lint-src        # black + isort + flake8 on src/ only
make clean           # remove __pycache__, *.pyc, *.pyo, *~

# Testing
make test            # pytest
make test-dev        # pytest -s -vv
make test-snapshot   # pytest --snapshot-update (syrupy)

# Docker / database / deployment
make up              # pull + build + start services
make down            # stop services
make migrations      # makemigrations (in migrator service)
make migrate         # migrate (in migrator service)
# ... more targets, see Makefile
```

To run a single test, use `pytest tests/path/to/test_file.py::test_name`.

---

## Known gaps and considerations

- **Django vs FastAPI split**: Admin (Django, port 8000) and GraphQL (FastAPI, port 8500) run as separate services. Confirm this is intentional long-term, not accidental sprawl.

- **identity app isolation**: Currently unused by quiz/tenant (no cross-app refs in either direction). If quiz/tenant need to validate users in future, apply the port pattern: define a port in quiz/tenant and let identity implement it.

- **eventing integration**: Only integrated as `failure_sink` on the event bus; no explicit port consumed by other apps. If this evolves (e.g., other apps subscribing to specific event channels), document the new integration pattern.

- **Entity↔Model mapping asymmetry**: `from_model()` exists; `to_model()` does not (inline in repos). This is the current convention; can be refactored to a separate mapper class later if needed.

- **Decorator code duplication**: `@handle_mutations_exceptions` has near-identical `async_wrapper` and `sync_wrapper` bodies — not blocking, but a cleanup candidate if the file is touched again.

- **Filename typo**: `src/tenant/infrastructure/persistence/django/models/tenat_user.py` is missing an 'n' — won't be renamed in this plan because it touches migrations/imports; flagged for future fix.

- **Terraform stubs**: `devops/terraform/` does not exist yet, though `Makefile` already has `tf-*` targets. This is a known gap, not an error.

- **SQLite residual**: `quiz_db.sqlite3` at repo root is not the configured backend (Postgres is) — likely leftover from local dev; consider adding to `.gitignore` if not already there.
