## Why

The `eventing` app has two parallel implementations of the same dead-letter behavior: a working one (`persist_failed_event_message.py`, `retry_failed_event.py`) that talks directly to the Django ORM model, and a half-built DDD path (`persist_failed_event_use_case/`, the entity, the repository port/impl) that is broken (empty DTO, a use case method with no body, a no-op repository) and not wired anywhere. Before `eventing` becomes the pattern other bounded contexts copy for their own event-driven use cases (audit log is the next consumer), it needs to actually follow its own layering — one finished path, not two.

## What Changes

- Finish `domain/repositories/failed_event_message_repository.py`: fix the broken import (`eventing.domain...` → `src.eventing.domain...`) and expand the port beyond `save` to cover what persistence and retry both need: `save`, `get_by_id`, `mark_resolved`, `mark_retry_failed`.
- Implement `infrastructure/repositories/failed_event_message_repository_imp.py` for real (currently `save` is a no-op `pass`) against the `FailedEventMessage` Django model.
- Finish `application/persist_failed_event_use_case/`: a pydantic v2 `PersistFailedEventDTO` with a `from_event_bus_failure(event, handler, exc)` classmethod that extracts and validates the dead-letter fields from the raw `EventBusMessage`/handler/exception, and a `PersistFailedEventUseCase.execute(dto)` orchestrator that builds the entity and calls the repository.
- **New**: `application/retry_failed_event_use_case/` — same pattern (DTO + orchestrator use case) replacing the current function-based `retry_failed_event.py`, which mutates the Django model directly and bypasses entity/repository entirely.
- Rewire `EventingConfig.ready()` to register the use case (via the repository implementation) as the `EventBus` failure sink, instead of the free function.
- Rewire `FailedEventMessageAdmin.retry_selected` to call `RetryFailedEventUseCase` instead of the `retry_failed_event` function.
- **BREAKING (internal)**: delete `application/persist_failed_event_message.py` and `application/retry_failed_event.py` once their replacements are wired — no other code outside `eventing` imports them.
- **New**: scaffold `tests/` for the whole repo (doesn't exist yet, even though `Makefile`'s `test`/`test-dev` targets already assume it) — `pytest.ini` at the repo root, `tests/conftest.py` loading fixture modules via `pytest_plugins`, a `tests/fixtures/` package for shared fixtures, and automated tests covering everything this change builds (entity, DTOs, both use cases, the repository implementation).

## Capabilities

No spec-level behavior changes: the dead-letter capture (fields persisted on handler failure) and retry semantics (re-invoke only the failed handler, `PENDING`/`RESOLVED` transitions, `retry_count` bump) stay exactly as they behave today. This is an internal layering refactor of an existing, unspecified capability — see `skip_specs: true` in `.openspec.yaml`.

### New Capabilities
(none)

### Modified Capabilities
(none)

## Impact

- `src/eventing/domain/repositories/failed_event_message_repository.py`
- `src/eventing/infrastructure/repositories/failed_event_message_repository_imp.py`
- `src/eventing/application/persist_failed_event_use_case/{dto.py,use_case.py}`
- `src/eventing/application/retry_failed_event_use_case/{dto.py,use_case.py}` (new)
- `src/eventing/apps.py` (`EventingConfig.ready()` wiring)
- `src/eventing/presentation/admin/failed_event_message.py`
- Deletes: `src/eventing/application/persist_failed_event_message.py`, `src/eventing/application/retry_failed_event.py`
- Adds a runtime dependency on `pydantic` for the DTOs (already a project dependency per `pyproject.toml`, not newly introduced).
- No migration changes — `FailedEventMessage` model fields are unchanged.
- New: `pytest.ini`, `tests/__init__.py`, `tests/conftest.py`, `tests/fixtures/__init__.py`, `tests/fixtures/eventing_fixtures.py`, and test modules under `tests/eventing/`.
- New dev dependency: `pytest-django` (needed for `@pytest.mark.django_db` access to the real `FailedEventMessage` table in the repository tests; `pytest` and `pytest-asyncio` are already project dependencies).
