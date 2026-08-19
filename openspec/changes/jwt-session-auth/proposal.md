## Why

`account`'s `domain`/`application` layers are empty for authentication: nothing in this repo issues a JWT today, `src/shared/presentation/schema/auth.py` only decodes one, and `Context.user_session` calls that decoder directly — coupling the GraphQL presentation layer to "how identity is verified." There is also no mechanism to invalidate a session before its (currently unset) expiry: if an admin demotes a `UserTenant.role` from `ADMIN` to `COLLABORATOR`, the demoted user's existing JWT keeps granting `ADMIN` access indefinitely. This change builds login, a transport-level auth middleware, and a near-immediate permission-invalidation path together, since the invalidation mechanism drives what the JWT claims and the middleware need to look like.

## What Changes

- Add `LoginUseCase`, `SwitchTenantUseCase`, and `RefreshSessionUseCase` to `account/application/` — first real use cases in that layer for authentication (the two existing use cases there handle user/tenant creation, not auth).
- **BREAKING**: `MyUser.USERNAME_FIELD` changes from `"username"` (inherited default) to `"email"`, with an accompanying migration. Login is by email; `authenticate()` requires this to resolve correctly.
- Add a FastAPI `AuthMiddleware` in `src/shared/presentation/` that reads the `Authorization` header, verifies the JWT, and sets `request.state.user_session`. `Context.user_session` (`src/shared/presentation/schema/context.py`) changes from decoding the JWT itself to reading `request.state.user_session` — it no longer imports `auth.py` or knows JWT exists.
- Session model: JWT represents one active tenant per session (like a Slack workspace), not a multi-tenant claim array. Claims carry two independent permission-version numbers: a global one (covers `MyUser.is_superuser` → `IS_STAFF`) and a per-membership one (covers `UserTenant.role` → `IS_ADMIN`/`IS_COLLABORATOR`), since those two permission sources have different scopes and change independently.
- Wire Redis (already provisioned in `devops/docker-compose.yaml`, currently unused by any code) as the store for both permission-version counters, checked by the middleware on every request.
- Add an event handler subscribed to the `AccountEventChannel.ENTITY_CHANGED` channel (introduced by the in-progress `account-audit-trail` change) that increments the relevant Redis version counter when `UserTenant.role` or `MyUser.is_superuser` actually changes — reusing that change's before/after payload instead of adding a parallel channel.
- Add a session-refresh endpoint/mutation that re-derives permissions from Postgres and reissues a JWT when the middleware detects a stale permission-version — kept as a separate component from the middleware, which only verifies and never reissues.
- Redis unavailability (not a missing key — an actual connection/timeout error) fails open, bounded by a short JWT `exp` (target: 10–15 minutes) and logged via `structlog`; a missing-but-reachable key is treated as an ordinary version mismatch and self-heals through the refresh path.

## Capabilities

### New Capabilities
- `account/auth-session`: issuing a session (login), switching the active tenant, verifying a session on each request, and invalidating/refreshing it when the underlying permissions change.

### Modified Capabilities
(none — no existing spec covers authentication today; `Context.user_session` and `auth.py` are implementation, not a documented capability)

## Impact

- `src/account/infrastructure/persistence/django/models/user.py` (`USERNAME_FIELD`) + new migration
- `src/account/application/login_use_case/`, `switch_tenant_use_case/`, `refresh_session_use_case/` (new)
- `src/account/domain/` (currently empty — first domain entities/repos for this app, e.g. session/permission-version concerns)
- `src/shared/presentation/auth_middleware.py` (new)
- `src/shared/presentation/schema/context.py` (simplified — reads `request.state` only)
- `src/shared/presentation/schema/auth.py` (JWT decode logic moves into/behind the middleware; this module's role narrows or is absorbed)
- `src/shared/presentation/schema/types.py` (`UserSession` — add version claims, `active_tenant_id`)
- `src/eventing/infrastructure/event_handlers/` (new subscriber to `ENTITY_CHANGED`, bumping Redis version counters)
- `main/asgi.py` (mount the new middleware on `fastapp`)
- `main/settings/base.py` / `main/project_settings.py` (Redis connection settings — new)
- `devops/docker-compose.yaml` (Redis service already present, now actually consumed)
