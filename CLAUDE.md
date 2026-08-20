# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Length rule**: keep this file at **300 lines or fewer**. When a section needs more detail than that budget allows, extract the full version into `docs/claude/<topic>.md` and leave only a condensed summary + reference here — don't inline everything back in. This keeps the cost of reading this file on every session low; the full detail is still one targeted read away when actually needed.

## Project state

**quiz-management** is a system for managing exams ("Proyecto para la gestión de Exámenes"). The repository is **active** with real implementation: `src/`, `tests/`, `devops/`, and `openspec/` all exist and contain working code organized around 3 Django apps with full or partial DDD layering (quiz, eventing with complete domain/application/infrastructure/presentation; account with infrastructure + presentation only, domain/application empty).

## Tech stack

- **Python 3.12+** (3.14 pinned via `.python-version`). Dependency management via Poetry.

- **HTTP layer: Django + FastAPI (two separate services)**
  - Django 6.1 serves the admin interface (`manage.py`, `main/wsgi.py`, port 8000)
  - FastAPI 0.141 serves GraphQL (port 8500), with `strawberry.fastapi.GraphQLRouter` mounted in `main/asgi.py`
  - These are two independent processes in `devops/docker-compose.yaml` (`admin` and `api` services), not composed together

- **GraphQL**: `strawberry-graphql` (federation schema), JWT auth via `PyJWT`, custom permission classes (`IsAuthenticated`, `IsAdmin`, `IsStaff`, `IsOrganizationUser`) in `src/shared/presentation/schema/permissions.py`. No Django permission system.

- **Database**: Postgres 15 (via `psycopg2-binary` + `dj-database-url`). Custom user model `src.account.infrastructure.persistence.django.models.user.MyUser(AbstractUser)` with UUID primary key, set as `AUTH_USER_MODEL = "account.MyUser"`. Note: a stray `quiz_db.sqlite3` at repo root is not the configured backend (residual local dev artifact).

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

  account/             Infrastructure + presentation only (domain/application empty).
                       Owns MyUser, Tenant, and UserTenant (a user's membership in a
                       tenant) — merged from former identity + tenant apps so creating
                       a tenant-scoped user doesn't span two apps:
                       infrastructure/{persistence/django/models,repositories},
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

Hard requirements from development history — violating them breaks the system or fails review. Full rationale + BAD/GOOD code examples: `docs/claude/mandatory-patterns.md`.

1. **Never ORM writes in loops** — pre-generate UUIDs, accumulate in a list, `bulk_create()` once. Prevents N+1 queries; applies even when the loop and the write are in different layers via the event bus (see `docs/claude/mandatory-patterns.md`). Example: `src/quiz/infrastructure/repositories/question_repository_imp.py`.
2. **Cross-app dependencies: port pattern** — consumer defines the interface in its `domain/repositories/`; producer implements it in `infrastructure/repositories/*_imp.py`, importing only its own models. Dependency direction: consumer ← producer. Example: `src/quiz/domain/repositories/tenant_lookup_repository.py` ↔ `src/account/infrastructure/repositories/tenant_lookup_repository_imp.py`.
3. **`operation_id` for mutation idempotency** — ALWAYS from the client's `X-Operation-ID` header, NEVER generated server-side; fail fast (raise) if the header is missing. Example: `src/shared/presentation/schema/context.py`, `Context.operation_id`.
4. **Mutation exception handling via decorator** — `@handle_mutations_exceptions` on every mutation, never manual `try/except`. Maps `DomainError`/`ApplicationError`→`ValidationErrorResponse`, `InfrastructureError`→`IntegrityErrorResponse`, `pydantic.ValidationError`→`ValidationErrorResponse`, `django.db.IntegrityError`→`IntegrityErrorResponse`, anything else→`InternalErrorResponse` (logged `exc_info=True`). Example: `src/quiz/presentation/schema/mutations/mutations_admin.py`.

---

## Code style conventions

Full detail + GraphQL response pattern example: `docs/claude/code-style.md`.

- **Imports**: absolute only (`from src.<app>.<layer>...`); order stdlib → third-party → `src.` local, alphabetical within each group.
- **Type hints**: complete on every function. DTOs = Pydantic `BaseModel` (`ConfigDict(frozen=True)`). Entities = `@dataclass(frozen=True)` with `__post_init__` validation, never Pydantic.
- **Async/sync**: use case + repo ABCs are `async def`; repo impls are sync `def` decorated with `@async_database()` (wraps `sync_to_async(thread_sensitive=True)`, retries once on `InterfaceError`/`OperationalError`). The signature mismatch is intentional.
- **Exceptions**: hierarchy in `src/shared/domain/exceptions.py` — `DomainError` → `NotFoundError` / `ApplicationError` / `InfrastructureError`; per-app exceptions subclass these.
- **Entity ↔ Model**: `Entity.from_model(cls, instance)` classmethod; no symmetric `to_model()` (inline in repo impl instead) — asymmetric on purpose.
- **Repositories**: `*Repository` (ABC in `domain/repositories/`), `*RepositoryImpl` (impl in `infrastructure/repositories/*_repository_imp.py`).
- **Naming**: use cases `<verb>_<noun>_use_case/` package; domain `*Entity`/`*Repository`; infra `*RepositoryImpl`/`*Model`; GraphQL `*Input`/`*Response`/`*Payload`/`*Type`; exceptions `*Error`; event channels `*EventChannel`.
- **Docstrings/comments**: only when non-obvious (design rationale); never restate the signature; inline comments explain *why*, not *what*.
- **Primary keys**: all Django models use UUID (`id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`).

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

## Git workflow

**Default**: commit directly, as today. No PRs, no stacking, for ordinary work — a fix, a single-layer change, a small feature.

**Exception — multi-layer features**: when a change spans 3+ DDD layers of an app in one logical unit (e.g. a new use case touching `domain` → `application` → `infrastructure` → `presentation`, or a cross-app port change touching consumer port + producer impl + injection site), use `gh-stack` (`gh extension install github/gh-stack`, already installed locally — verify with `gh extension list`) to split it into one branch/PR per layer instead of one commit mixing all of them:

```bash
gh stack init feature/<name>          # first layer (e.g. domain)
# ...work, commit...
gh stack add feature/<name>-<layer>   # next layer, depends on the previous one
# ...repeat per layer...
gh stack push && gh stack submit      # push branches, open linked PRs
gh stack view                         # see stack status
```

**Why**: this project's DDD layering (domain/application/infrastructure/presentation) maps directly onto stack layers — each PR becomes one reviewable, revertible, bisectable unit instead of a commit that mixes concerns across layers.

**Known limits of this convention today**: no `.github/workflows` CI exists yet and there is a single developer, so the review-speed/CI-per-PR benefits `gh-stack` is built for don't fully apply yet — this is adopted narrowly, for its git-history/bisectability value on genuinely multi-layer changes, not as a blanket policy. Revisit generalizing it if CI gets added or a second contributor joins.

Still applies regardless of workflow: the git safety protocol in the global CLAUDE.md (no `--force`, no skipping hooks, show diff and get confirmation before pushing/committing) — stacking changes *what* gets committed and how many PRs, not those rules.

---

## Known gaps and considerations

- **Django vs FastAPI split**: Admin (Django, port 8000) and GraphQL (FastAPI, port 8500) run as separate services. Confirm this is intentional long-term, not accidental sprawl.

- **account app isolation**: `MyUser` itself is currently unused by `quiz` (no direct cross-app refs — `quiz` only consumes `Tenant`/`UserTenant` data through the `TenantLookupRepository` port). If `quiz` needs to validate users directly in future, extend that same port pattern.

- **eventing integration**: Only integrated as `failure_sink` on the event bus; no explicit port consumed by other apps. If this evolves (e.g., other apps subscribing to specific event channels), document the new integration pattern.

- **Entity↔Model mapping asymmetry**: `from_model()` exists; `to_model()` does not (inline in repos). This is the current convention; can be refactored to a separate mapper class later if needed.

- **Decorator code duplication**: `@handle_mutations_exceptions` has near-identical `async_wrapper` and `sync_wrapper` bodies — not blocking, but a cleanup candidate if the file is touched again.

- **Terraform stubs**: `devops/terraform/` does not exist yet, though `Makefile` already has `tf-*` targets. This is a known gap, not an error.

- **SQLite residual**: `quiz_db.sqlite3` at repo root is not the configured backend (Postgres is) — likely leftover from local dev; consider adding to `.gitignore` if not already there.
