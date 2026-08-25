# Code style conventions

> Referenced from `CLAUDE.md` (kept there as a condensed bullet list to stay under its 300-line cap). Full detail and the GraphQL response pattern example live here.

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
