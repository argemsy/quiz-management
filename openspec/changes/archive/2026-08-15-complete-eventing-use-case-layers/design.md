## Context

See proposal.md for motivation. Current state, concretely:

- `FailedEventMessageEntity` (domain) is a frozen dataclass with a `.create()` factory — already correct, no changes needed there.
- `FailedEventMessageRepository` (port) only declares `save`, and the import is broken (`from eventing.domain...`, missing the `src.` prefix used everywhere else in this repo).
- `FailedEventMessageRepositoryImpl` (infra) has a `save` that does nothing (`pass`) — no entity/model mapping exists yet.
- `persist_failed_event_use_case/dto.py` is empty; `use_case.py` has a dangling `def` (syntax error) — this module currently cannot be imported.
- The two things actually wired and working today (`persist_failed_event_message.py`, `retry_failed_event.py`) operate directly on the `FailedEventMessage` Django model, with channel/handler path extraction and JSON-safety coercion done as free functions inline.
- `EventingConfig.ready()` wires `persist_failed_event_message` as `EventBus.set_failure_sink(...)`. The bus already wraps the failure sink call in its own try/except (`_handle_handler_error` in `bus.py`) — a sink that raises is logged and swallowed, it never takes down `publish()`.

## Goals / Non-Goals

**Goals:**
- One working implementation per use case (persist, retry), both going through entity + repository, no ORM calls from `application/`.
- DTO validation happens before any domain/persistence logic runs, using pydantic v2.
- Preserve the exact existing behavioral contract: same fields persisted on failure, retry re-invokes only the failed handler, same `PENDING`/`RESOLVED` transitions, same `retry_count` bump, same re-raise-on-retry-failure so the admin action's success/failure counters keep working unchanged.

**Non-Goals:**
- No changes to `EventBus`, `EventBusMessage`, or `FailedEventMessage`'s model fields/migrations.
- No outbox pattern, no SNS/SQS, no audit log — those are separate, later changes (see project discussion history; this change only unblocks them by giving `eventing` a clean pattern to copy).
- Test coverage is scoped to what this change builds (entity, DTOs, both use cases, the repository implementation). It does not retroactively add tests for `EventBus`, the `shared` kernel, or `identity`/`quiz`/`tenant` — those stay untested until a change that touches them decides otherwise.
- No CI wiring (GitHub Actions or similar) — `tests/` gets scaffolded and made runnable locally via `make test`, running it in CI is a separate concern.

## Decisions

**1. DTO owns extraction, not a separate adapter function.**
`PersistFailedEventDTO.from_event_bus_failure(event, handler, exc)` is a `@classmethod` that computes `channel_path`/`handler_path` (same dotted-path encoding as today: `"module:qualname:MEMBER"` / `"module:qualname"`) and constructs the model — pydantic validates on construction, so a malformed event fails fast, before the use case or repository ever runs. Alternative considered: a free function that builds a validated DTO and hands it to the use case. Rejected — it just relocates the same logic one file over without adding anything; keeping it as a classmethod keeps "how do I build this DTO from a bus failure" next to the DTO's own field definitions.

**2. Payload/metadata JSON-safety stays best-effort, now as a pydantic `field_validator`.**
The existing `_as_json_safe` behavior (try `json.dumps(..., cls=DjangoJSONEncoder)`, on `TypeError` fall back to `{"__unserializable__": repr(value)}`) is preserved as-is inside a `field_validator` on `payload`/`metadata`. This is deliberately **not** stricter than today — the point of a dead-letter record is that it must never fail to save because of the payload it's trying to capture. A validator that rejected unserializable payloads outright would defeat that purpose.

**3. Repository port grows to 4 methods, driven by what both use cases need.**
```python
class FailedEventMessageRepository(ABC):
    def save(self, entity: FailedEventMessageEntity) -> FailedEventMessageEntity: ...
    def get_by_id(self, id: uuid.UUID) -> FailedEventMessageEntity | None: ...
    def mark_resolved(self, id: uuid.UUID) -> FailedEventMessageEntity: ...
    def mark_retry_failed(self, id: uuid.UUID, error_type: str, error_message: str) -> FailedEventMessageEntity: ...
```
`get_by_id`/`mark_resolved`/`mark_retry_failed` exist purely because `RetryFailedEventUseCase` needs them — persist alone would only need `save`. Alternative considered: a generic `update(id, **fields)`. Rejected — the two state transitions the domain actually performs (resolve, record-a-failed-retry) are specific and small enough that naming them explicitly is clearer than a generic setter, and it keeps the ORM's `update_fields=[...]` optimization (only touch the columns that changed) inside the infra layer where it belongs.

**4. Entity stays a frozen dataclass; the infra layer owns entity↔model mapping.**
`FailedEventMessageRepositoryImpl` gets a private `_to_entity(model: FailedEventMessage) -> FailedEventMessageEntity` mapper. `mark_resolved`/`mark_retry_failed` fetch the Django row, mutate the specific columns via `.save(update_fields=[...])` (same pattern `retry_failed_event.py` already uses today), then return the mapped entity. The domain entity itself gains no mutation methods — mutation is a persistence concern, not a domain one, and the entity is only ever consumed by the use cases as a read model.

**5. `RetryFailedEventUseCase` keeps the channel/handler resolution logic that lives in `retry_failed_event.py` today** (`_resolve_channel`/`_resolve_handler`, dotted-path → live object via `importlib` + `functools.reduce(getattr, ...)`), moved as module-level helpers in the new `retry_failed_event_use_case/use_case.py`. This is orchestration (deciding *what* to call), which belongs in the use case, not the repository (whose job is only persistence) or the DTO (whose job is only validating the input `failed_event_id`).

**6. Wiring moves from "pass a bare function" to "close over an instantiated use case".**
`EventingConfig.ready()` builds `repository = FailedEventMessageRepositoryImpl()` once, then:
```python
persist_use_case = PersistFailedEventUseCase(repository)
get_event_bus().set_failure_sink(
    lambda event, handler, exc: persist_use_case.execute(
        PersistFailedEventDTO.from_event_bus_failure(event, handler, exc)
    )
)
```
`FailedEventMessageAdmin.retry_selected` similarly builds `RetryFailedEventUseCase(FailedEventMessageRepositoryImpl())` (module-level or per-request — module-level is fine, the repository is stateless) and calls `.execute(RetryFailedEventDTO(failed_event_id=failed_event.id))` per row instead of the old `retry_failed_event(failed_event)`.

**7. Test layout: `tests/` mirrors `src/` by bounded context, fixtures load via `pytest_plugins`, unit tests use a fake repository.**
- `pytest.ini` at the repo root sets `DJANGO_SETTINGS_MODULE = main.settings.base` (same value `manage.py` defaults to) so `pytest-django` can set up the test database; `python_files = test_*.py`.
- `tests/conftest.py` is a thin loader: `pytest_plugins = ["tests.fixtures.eventing_fixtures"]` — one entry per fixture module, so fixtures stay organized by bounded context (mirroring `src/<app>/`) instead of piling into one root `conftest.py`. `tests/fixtures/eventing_fixtures.py` provides: a sample `EventBusMessage` + a throwaway channel `Enum` + sync/async handlers that raise (for exercising `from_event_bus_failure`), a `FakeFailedEventMessageRepository` (in-memory dict-backed, implements the same ABC) for unit-testing the use cases without hitting the DB, and a `failed_event_message` factory fixture that creates a real DB row via `FailedEventMessageRepositoryImpl` for the `@pytest.mark.django_db` tests.
- Alternative considered for the fake repository: use the real `FailedEventMessageRepositoryImpl` everywhere and mark every use-case test `django_db`. Rejected — the use cases' own orchestration logic (what they call, in what order, what they do on success/failure) is what's being tested there, not persistence; a fake repository keeps those tests fast and makes assertions about *behavior* (e.g. "mark_retry_failed was called with this error_type") instead of *side effects in a database*. The repository implementation itself still gets its own `django_db` tests against the real model.
- Test modules mirror the source tree: `tests/eventing/domain/test_failed_event_message_entity.py`, `tests/eventing/application/persist_failed_event_use_case/test_use_case.py`, `tests/eventing/application/retry_failed_event_use_case/test_use_case.py`, `tests/eventing/infrastructure/test_failed_event_message_repository_imp.py`.

## Risks / Trade-offs

- **[Risk]** A stricter DTO could silently change what gets persisted vs. today. → **Mitigation**: decision #2 keeps the coercion behavior byte-for-byte equivalent; verify manually with the same malformed-payload case used when the DLQ was first built (see proposal's predecessor session).
- **[Risk]** Moving retry's exception handling behind a use case could change what the admin's `except Exception` sees (e.g. wrapping the original exception). → **Mitigation**: `RetryFailedEventUseCase.execute` re-raises the original exception unchanged after calling `mark_retry_failed`, exactly like `retry_failed_event.py` does today — no wrapping.
- **[Risk]** `pytest.ini` and `tests/` are new to the whole repo, not just `eventing` — a config mistake here (wrong `DJANGO_SETTINGS_MODULE`, wrong `python_files` pattern) affects every future test, not just this change's. → **Mitigation**: task list includes running `make test` (the `Makefile` target that already exists and already assumes this layout) as the concrete acceptance check, not just `pytest` run ad hoc.

## Migration Plan

No data migration — `FailedEventMessage`'s schema is unchanged. Deployment is just a code change:
1. Scaffold `tests/` (`pytest.ini`, `conftest.py`, `fixtures/`) so the layers below have somewhere to be tested as they're built.
2. Land the domain/infrastructure/application changes, each with its corresponding test module.
3. Rewire `EventingConfig.ready()` and the admin action.
4. Delete the two now-dead free-function modules.
5. Run `manage.py check` and `make test`.

Rollback is a plain revert — no migrations to reverse.
