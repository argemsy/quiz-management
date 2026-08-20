## 1. `USERNAME_FIELD` migration

- [x] 1.1 Set `USERNAME_FIELD = "email"` and adjust `REQUIRED_FIELDS` on `src/account/infrastructure/persistence/django/models/user.py::MyUser`
- [x] 1.2 Generate and review the migration (`make migrations`) for `account` — no migration generated; `USERNAME_FIELD`/`REQUIRED_FIELDS` are class attributes, not model fields, so there's no schema change
- [x] 1.3 Confirm `make createsuperuser` still works end-to-end against the new field — verified against a scratch sqlite DB: `createsuperuser --noinput` with `DJANGO_SUPERUSER_EMAIL` succeeds, `get_username()` returns the email

## 2. Redis wiring (shared infrastructure)

- [x] 2.1 Add Redis connection settings to `main/project_settings.py` (`RedisSettings.url`/`socket_timeout_seconds` from `REDIS_URL`/`REDIS_SOCKET_TIMEOUT_SECONDS`, following the `_GroupSettings` pattern; also added `SECURITY.jwt_exp_minutes` for the short `exp` from design.md). Added `REDIS_URL=redis://localhost:6379/0` to root `.env` for host-run processes — `devops/docker.env.example` already had it for containers.
- [x] 2.2 Add a Redis client accessor: `src/shared/infrastructure/cache/redis_client.py` (`RedisClientRegistry`/`get_redis_client()`, mirrors `EventBusRegistry`'s singleton). Uses `redis.asyncio.Redis` (not the sync client) so the auth middleware never blocks the event loop; `socket_timeout`/`socket_connect_timeout` set short (0.5s default) to bound the fail-open path from design.md. Ran `poetry install` — `redis` was declared in `pyproject.toml` but not yet installed in the local venv.
- [x] 2.3 Confirmed: `api` and `admin` both load `env_file: docker.env`, which carries `REDIS_URL=redis://redis:6379/0`; the `redis` hostname resolves on Compose's default network. No `depends_on: redis` added deliberately — matches the fail-open-on-outage design, services shouldn't refuse to start without Redis.

## 3. Account domain layer (currently empty)

- [x] 3.1 Add `src/account/domain/entities/user_entity.py` (`UserEntity`, frozen dataclass, `from_model(MyUser)`) — carries `id`, `email`, `is_superuser`
- [x] 3.2 Add `src/account/domain/entities/user_tenant_entity.py` (`UserTenantEntity`, frozen dataclass, `from_model(UserTenant)`) — carries `id`, `user_id`, `tenant_id`, `role`, `is_active`
- [x] 3.3 Add `src/account/domain/repositories/user_repository.py` (ABC: `authenticate(email, password)`, `find(spec: Specification) -> list[UserEntity]` — revised mid-implementation to the Specification pattern, see 3.5b below)
- [x] 3.4 Add `src/account/domain/repositories/user_tenant_repository.py` (ABC: `find(spec: Specification) -> list[UserTenantEntity]` — same revision)
- [x] 3.5b (added mid-implementation, not in the original plan) Implement the Specification pattern from the standing project memory (`pending-specification-pattern-repositories`) for these two new Postgres-backed repos, per explicit user instruction to not keep growing the repo interface one query method at a time: `src/shared/domain/specification.py` (`Specification`/`FieldFilterSpecification`/`And`/`Or`/`Not`, Django-free, `&`/`|`/`~` composable) and `src/shared/infrastructure/persistence/django/specification.py` (`to_django_q`, the only place that imports `Q`). `UserRepository`/`UserTenantRepository` ports expose `find(spec)`; `authenticate()` stays a dedicated method since it delegates to Django's fixed-signature `authenticate()` backend call, not an ORM filter. `PermissionVersionRepository` (Redis key/value, not a queryable filter store) is unaffected.
- [x] 3.5 Add `src/account/domain/repositories/permission_version_repository.py` (ABC: `get_user_version`, `get_user_tenant_version`, `bump_user_version`, `bump_user_tenant_version`)
- [x] 3.6 Add `src/account/domain/exceptions.py` (`InvalidCredentialsError`, `MembershipNotFoundError`, `InvalidSessionError`, `SessionStaleError`)

## 4. Account infrastructure layer

- [x] 4.1 Implement `src/account/infrastructure/repositories/user_repository_imp.py` (`UserRepositoryImpl`; `authenticate()` via Django's `authenticate()`; `find(spec)` via `MyUser.objects.filter(to_django_q(spec))`, `@async_database()`)
- [x] 4.2 Implement `src/account/infrastructure/repositories/user_tenant_repository_imp.py` (`UserTenantRepositoryImpl`; `find(spec)` via `UserTenantModel.objects.filter(to_django_q(spec))`, `@async_database()`)
- [x] 4.3 Implement `src/account/infrastructure/repositories/permission_version_repository_imp.py` (`PermissionVersionRepositoryImpl`, backed by the shared Redis client from 2.2; keys `perms_version:user:{id}` / `perms_version:user_tenant:{id}`; native `async def`, not `@async_database()` — nothing to bridge, `redis.asyncio` is already async)
- [x] 4.4 Added `src/shared/infrastructure/auth/` — `session_claims.py` (`SessionClaims`, Pydantic frozen), `token_service.py` (`TokenService.encode`/`decode`, distinguishes `TokenExpiredError`/`TokenInvalidError`), `registry.py` (`get_token_service()`). Generalizes what `auth.py::authorize` used to do inline; both the middleware and the account use cases will share this one implementation.

## 5. Account application layer

- [x] 5.1 `login_use_case/`: `dto.py`/`service.py`/`use_case.py` — authenticate via `UserRepository.authenticate`, reject with `TenantRequiredError` if non-staff and no `tenant_id` given (derived directly from the spec's "unless staff-only" wording), delegate membership+version assembly to the new shared `SessionClaimsService` (see 5.1b), mint token via `TokenService`
- [x] 5.2 `switch_tenant_use_case/`: same shape, no password — `user_id` is programmatic input only (mutation resolver fills it from the authenticated session, never a client-supplied GraphQL argument), re-verifies the user still exists then delegates to `SessionClaimsService`
- [x] 5.3 `refresh_session_use_case/`: decodes the old token via `TokenService.decode` (maps `TokenExpiredError`/`TokenInvalidError` to `InvalidSessionError`), re-fetches the user, delegates to `SessionClaimsService` for the *same* `active_tenant_id` the old token had — always re-derives full-fresh claims rather than only patching the version that went stale
- [x] 5.1b (added mid-implementation) `src/account/application/session_claims_service.py` — `SessionClaimsService.assemble(user, tenant_id)`, shared by all three use cases above instead of duplicating "resolve membership + read both version counters + build `SessionClaims`" three times. Not nested in one use case's folder since it's genuinely cross-cutting.
- [x] 5.4 Unit tests for all three use cases: `tests/account/application/{login_use_case,switch_tenant_use_case,refresh_session_use_case}/test_use_case.py`, 10 tests covering every scenario in `specs/account/auth-session/spec.md`'s Login/Switch/Refresh requirements (success, invalid credentials, membership not found, non-staff without tenant, stale-session refresh reflecting the new role, expired token, tampered token). Fakes in new `tests/fixtures/account_fixtures.py`, registered in `tests/conftest.py`. Full suite: 77/77 passing.
  - Bug caught by these tests and fixed: `SessionClaimsService`'s membership lookup originally filtered `is_deleted=False` in the `Specification` it builds — but `UserTenantEntity` (the domain entity) has no `is_deleted` field, that's a persistence-only concept. Moved the exclusion into `UserTenantRepositoryImpl.find()` as an unconditional baseline scope instead of an application-layer filter criterion.

## 6. Permission-version invalidation (event subscriber)

- [x] 6.4 (checked first) `account-audit-trail`'s code-level dependency is satisfied: `AuditableAdminMixin`/`TenantAdmin`/`UserTenantAdmin` publishing `ENTITY_CHANGED` are fully implemented and covered by `tests/account/presentation/admin/test_audit_trail.py` (all passing); only that change's own task 9.3 (a manual admin click-through check) remains open, which doesn't block building a second subscriber against an already-real, tested event.
- [x] 6.1 Add `src/account/infrastructure/event_handlers/permission_invalidation.py` (renamed from the planned `permission_invalidation_handlers.py` — the longer name pushed one import line past flake8's 88-column limit): `handle_entity_changed_for_permissions(event)`. **Deviates from the original plan in two ways, both discovered by actually reading `AuditableAdminMixin`'s real implementation before wiring against it:**
  - **Payload location**: `previous_state`/`current_state`/`content_type` live in `event.data`, not `event.metadata` as planned — `metadata` is unused by `AuditableAdminMixin`, everything is in `data`. `content_type` is the raw `AuditLogContentTypeEnum` member (not a string).
  - **`MyUser.is_superuser` is NOT covered by this event at all**: `MyUserAdmin` does not use `AuditableAdminMixin` — `account-audit-trail`'s own design.md lists "only `TENANT`/`TENANT_USER` are wired" as a deliberate Non-Goal. Publishing `ENTITY_CHANGED` for `MyUser` here to piggyback on it would silently start auditing `MyUser` too, expanding that other change's scope as an unintended side effect. Instead, `MyUserAdmin.save_model` (`src/account/presentation/admin/user.py`) bumps `bump_user_version` directly, bypassing the event entirely — unrelated to auditing, so it doesn't need that machinery.
  - Also broadened beyond just `role`: bumps on `role` change, `is_active` change, or a `DELETION` action (soft-delete) — a deactivated/soft-deleted membership needs its session invalidated too, not only an explicit role edit; the original plan only mentioned "role change."
- [x] 6.1b (found while implementing, not anticipated in design.md) **Real bug, not just a test artifact**: `redis.asyncio`'s connection pool binds to whichever event loop first runs a command through it. The shared singleton client (`get_redis_client()`) is safe for the FastAPI service (one long-lived loop) but breaks the moment a *sync* caller (Django admin, via `asyncio.run()`) uses it more than once in the same process — the second `asyncio.run()` call raises `RuntimeError: Event loop is closed`, because the connection is still bound to the first call's now-closed loop. Both sync-triggered call sites (`handle_entity_changed_for_permissions`, dispatched by the event bus's own `asyncio.run()` fallback for sync publishers; and `MyUserAdmin.save_model`'s direct `asyncio.run()`) now build a throwaway client via a new `create_redis_client()` factory (`src/shared/infrastructure/cache/redis_client.py`) and close it (`aclose()`) within the same call, instead of reusing the singleton. `get_redis_client()` stays reserved for the FastAPI-side call sites (middleware, use cases) where one persistent loop makes the singleton correct and desirable.
- [x] 6.2 Subscribed in `src/account/apps.py::AccountConfig.ready()`, mirroring `QuizConfig.ready()`'s self-subscription. Coexists with `eventing`'s own subscriber to the same `ENTITY_CHANGED` channel (event bus already supports multiple handlers per channel).
- [x] 6.3 `tests/account/infrastructure/event_handlers/test_permission_invalidation.py` (4 tests: role change bumps, unrelated-field no-op, non-`TENANT_USER` content type ignored, soft-delete bumps) + `tests/account/presentation/admin/test_permission_invalidation.py` (3 tests: `is_superuser` change bumps, unrelated field no-op, creation doesn't bump). New `redis_client` test fixture in `tests/fixtures/account_fixtures.py` resets `RedisClientRegistry` per test (pytest-asyncio's per-test event loop hits the same stale-connection issue as 6.1b otherwise). Full suite: 84/84 passing.

## 7. Auth middleware and Context cutover

- [ ] 7.1 Add `src/shared/presentation/auth_middleware.py`: reads `Authorization`, decodes via the token service (4.4); no header → `request.state.user_session = None`; expired/invalid → `request.state.user_session = None` (unauthenticated, not stale); valid but version mismatch → short-circuit a raw `401 {"code": "SESSION_STALE"}` response before GraphQL execution
- [ ] 7.2 For the version check in 7.1, distinguish "key missing" (treat as mismatch → stale) from "store unreachable" (fail open, log via `structlog`, request proceeds using token claims)
- [ ] 7.3 Simplify `src/shared/presentation/schema/context.py::Context.user_session` to read `request.state.user_session` only — remove its dependency on `auth.py`
- [ ] 7.4 Update `src/shared/presentation/schema/types.py::UserSession` — add `active_tenant_id`, `user_tenant_id`, and the two version fields consumed internally (only if still needed after 7.3; otherwise these stay in the token claims layer)
- [ ] 7.5 Mount the middleware on `fastapp` in `main/asgi.py`
- [ ] 7.6 Retire/trim `src/shared/presentation/schema/auth.py` now that decode logic lives in the shared token service (4.4)

## 8. GraphQL mutations

- [ ] 8.1 Add `LoginInput`/`LoginResponse`/`LoginPayload` and a `login` mutation (new `src/account/presentation/schema/mutations/` module, following `src/quiz/presentation/schema/mutations/mutations_admin.py` as the reference: `@handle_mutations_exceptions`, `X-Operation-ID` still required per mandatory pattern #3)
- [ ] 8.2 Add `switchTenant` mutation, same conventions
- [ ] 8.3 Add `refreshSession` mutation, same conventions
- [ ] 8.4 Wire the new mutations into the federated schema root (wherever `quiz`'s mutations are currently composed in)

## 9. End-to-end verification

- [ ] 9.1 Integration test: login → GraphQL request with the issued token succeeds, no DB hit for permissions on that second request
- [ ] 9.2 Integration test: role change via admin → next request with the old token gets `SESSION_STALE` → refresh → retry succeeds with updated role
- [ ] 9.3 Integration test: Redis unreachable → valid unexpired token still accepted; request logged as degraded
- [ ] 9.4 Manual check: staff (superuser, no tenant) login and request path works end-to-end
- [ ] 9.5 `make lint` and `make test` pass for the full slice
