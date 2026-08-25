## 1. Test Infrastructure

- [x] 1.1 Add `pytest-django` as a project dependency (`poetry add --group dev pytest-django` or equivalent)
- [x] 1.2 Create `pytest.ini` at the repo root: `DJANGO_SETTINGS_MODULE = main.settings.base`, `python_files = test_*.py`
- [x] 1.3 Create `tests/__init__.py`, `tests/fixtures/__init__.py`
- [x] 1.4 Create `tests/conftest.py` with `pytest_plugins = ["tests.fixtures.eventing_fixtures"]`
- [x] 1.5 Create `tests/fixtures/eventing_fixtures.py`: a throwaway channel `Enum` + sample `EventBusMessage` fixture, sync/async handler fixtures that raise, a `FakeFailedEventMessageRepository` (in-memory, implements `FailedEventMessageRepository`) fixture, and a `django_db`-backed `failed_event_message` factory fixture using the real repository
- [x] 1.6 Verify the scaffold with `pytest --collect-only` (should collect zero tests but not error)

## 2. Domain

- [x] 2.1 Fix the broken import in `src/eventing/domain/repositories/failed_event_message_repository.py` (`eventing.domain...` → `src.eventing.domain...`)
- [x] 2.2 Expand `FailedEventMessageRepository` (ABC) with `get_by_id(id) -> FailedEventMessageEntity | None`, `mark_resolved(id) -> FailedEventMessageEntity`, `mark_retry_failed(id, error_type, error_message) -> FailedEventMessageEntity`, alongside the existing `save(entity) -> FailedEventMessageEntity`
- [x] 2.3 Add `tests/eventing/domain/test_failed_event_message_entity.py` covering `FailedEventMessageEntity.create(...)` (defaults: `id` generated, `status=PENDING`, `retry_count=0`, `created_at == updated_at`)

## 3. Infrastructure

- [x] 3.1 Implement `FailedEventMessageRepositoryImpl.save` — create the `FailedEventMessage` row from the entity's fields, return the mapped entity
- [x] 3.2 Add a private `_to_entity(model) -> FailedEventMessageEntity` mapper
- [x] 3.3 Implement `get_by_id`, `mark_resolved`, `mark_retry_failed` on `FailedEventMessageRepositoryImpl`, mirroring the `update_fields=[...]` targeting `retry_failed_event.py` already uses
- [x] 3.4 Add `tests/eventing/infrastructure/test_failed_event_message_repository_imp.py` (`@pytest.mark.django_db`): `save` persists and round-trips through `get_by_id`; `get_by_id` returns `None` for a missing id; `mark_resolved` sets `status=RESOLVED` and bumps `retry_count`; `mark_retry_failed` updates `error_type`/`error_message`/`retry_count` and leaves `status=PENDING`

## 4. Application — persist_failed_event_use_case

- [x] 4.1 Write `PersistFailedEventDTO` (pydantic v2) in `dto.py` with fields: `channel_path`, `handler_path`, `resource_name`, `correlation_id`, `payload`, `metadata`, `error_type`, `error_message`
- [x] 4.2 Add `field_validator`s on `payload`/`metadata` preserving the existing best-effort JSON-safety coercion from `persist_failed_event_message.py`'s `_as_json_safe`
- [x] 4.3 Add `PersistFailedEventDTO.from_event_bus_failure(event, handler, exc)` classmethod, porting the `_channel_path`/`_handler_path` extraction logic
- [x] 4.4 Finish `PersistFailedEventUseCase.execute(dto)` in `use_case.py`: build the entity via `FailedEventMessageEntity.create(...)` from the DTO, call `repository.save(entity)`, return the result
- [x] 4.5 Add `tests/eventing/application/persist_failed_event_use_case/test_dto.py`: `from_event_bus_failure` extracts the correct `channel_path`/`handler_path` for both a sync and an async handler fixture; a non-JSON-serializable `event.data` (e.g. a plain object instance) still produces a valid DTO with `payload={"__unserializable__": ...}` instead of raising
- [x] 4.6 Add `tests/eventing/application/persist_failed_event_use_case/test_use_case.py` using the `FakeFailedEventMessageRepository` fixture: `execute(dto)` calls `repository.save` with an entity matching the DTO's fields and returns it

## 5. Application — retry_failed_event_use_case (new)

- [x] 5.1 Create `src/eventing/application/retry_failed_event_use_case/__init__.py`
- [x] 5.2 Write `RetryFailedEventDTO` (pydantic v2) in `dto.py` with a single `failed_event_id: uuid.UUID` field
- [x] 5.3 Write `RetryFailedEventUseCase` in `use_case.py`: move `_resolve_channel`/`_resolve_handler` here as module-level helpers, `execute(dto)` fetches the entity via `repository.get_by_id`, resolves channel/handler, builds an `EventBusMessage`, invokes the handler (same sync/async dispatch as today), calls `repository.mark_resolved` on success or `repository.mark_retry_failed` on failure, and re-raises the original exception unchanged on failure
- [x] 5.4 Add `tests/eventing/application/retry_failed_event_use_case/test_use_case.py` using the `FakeFailedEventMessageRepository` and the raising handler fixtures: success path calls `mark_resolved`; failure path calls `mark_retry_failed` with the new error and re-raises the original exception type

## 6. Wiring

- [x] 6.1 Update `EventingConfig.ready()` to instantiate `FailedEventMessageRepositoryImpl()` and `PersistFailedEventUseCase(repository)`, and register a lambda that builds the DTO via `from_event_bus_failure` and calls `execute` as the `EventBus` failure sink
- [x] 6.2 Update `FailedEventMessageAdmin.retry_selected` to call `RetryFailedEventUseCase(FailedEventMessageRepositoryImpl()).execute(RetryFailedEventDTO(failed_event_id=failed_event.id))` per row, keeping the existing succeeded/failed counters

## 7. Cleanup

- [x] 7.1 Delete `src/eventing/application/persist_failed_event_message.py`
- [x] 7.2 Delete `src/eventing/application/retry_failed_event.py`
- [x] 7.3 Grep the repo for any remaining imports of the two deleted modules and fix/remove them

## 8. Verification

- [x] 8.1 `python manage.py check` passes
- [x] 8.2 `make test` (i.e. `pytest`) passes with the full suite from sections 1–5 green
- [x] 8.3 Add one end-to-end integration test, `tests/eventing/test_dlq_end_to_end.py` (`@pytest.mark.django_db`): publish an `EventBusMessage` on the real `get_event_bus()` singleton to a channel whose only handler raises → assert a `FailedEventMessage` row exists with `status=PENDING`; fix the handler (swap the subscriber) and run `RetryFailedEventUseCase` → assert `status=RESOLVED`, `retry_count=1`
