## Context

See `proposal.md` - Why. Relevant current state:

- `src/shared/presentation/schema/context.py`'s `Context.user_session` decodes the JWT inline via `src/shared/presentation/schema/auth.py::authorize()`. No middleware layer exists; verification is coupled to the GraphQL presentation layer.
- No login/token-issuance code exists anywhere in `src/` today — `auth.py` only decodes. `MyUser(AbstractUser)` inherits Django's password hashing (`check_password`/`set_password`) for free, but `USERNAME_FIELD` is still the inherited `"username"`, not `email`, even though `email` is `unique=True`.
- Django's `SessionMiddleware`/`AuthenticationMiddleware` (`main/settings/base.py`) are wired only into the Django ASGI app (admin, port 8000). `fastapp` (`main/asgi.py`) is a separate `FastAPI()` instance with none of that middleware mounted — Django's cookie/session-based `login(request, user)` cannot reach the GraphQL request path without re-plumbing session middleware into a second framework, which is not worth it when a stateless JWT already fits a cross-service API better.
- The only API surface `fastapp` currently exposes is the GraphQL router (`graphql_app`) — there are no REST routes today.
- Permissions today (`SessionPermissionEnum`) come from two independent, differently-scoped sources: `MyUser.is_superuser` → `IS_STAFF` (global, no tenant) and `UserTenant.role` (`ADMIN`/`DIRECTOR` → `IS_ADMIN`, `COLLABORATOR` → `IS_COLLABORATOR`) (scoped to one membership row).
- A session represents one active tenant at a time (confirmed: "como Slack" — pick a workspace, switch to change it), not a multi-tenant claims array.
- `devops/docker-compose.yaml` already runs a `redis` service; nothing in `src/` or Django settings uses it yet.
- The in-progress `account-audit-trail` change adds `AccountEventChannel.ENTITY_CHANGED`, published on every `Tenant`/`UserTenant` admin save, carrying `metadata.previous_state`/`current_state`. This change's invalidation handler is a second subscriber to that same event, not a new channel — **this change has a sequencing dependency on `account-audit-trail` landing first** (or at minimum, on `ENTITY_CHANGED` and its before/after payload existing).

## Goals / Non-Goals

**Goals:**
- Decouple "how a request's identity is verified" (JWT) from `Context`, which should only read an already-resolved session.
- A permission change (`UserTenant.role`, `MyUser.is_superuser`) takes effect on the affected session's next request, without waiting for JWT expiry.
- Zero Postgres hits on the request happy path (valid, non-stale session).
- Reuse the existing event bus and the `account-audit-trail` event instead of adding parallel invalidation plumbing.

**Non-Goals:**
- Changing Django admin's own login (port 8000 already works via `SessionMiddleware`/`AuthenticationMiddleware`; untouched by this change).
- External IdP integration (Auth0, Cognito, etc.) — this change keeps token issuance in-house; swapping the issuer later is a follow-up enabled by, not part of, this design.
- Password reset / MFA / account lockout flows.
- Refresh-token rotation or a denylist for stolen tokens — the mitigation here is a short `exp`, not token revocation infrastructure. Revisit if the threat model requires it.

## Decisions

**Login/switch-tenant/refresh are GraphQL mutations, not REST routes.** `fastapp` has no REST surface today; adding one just for auth would be a second API style for a three-endpoint slice. These become ordinary mutations under the existing `@handle_mutations_exceptions` / Input-Response-Payload pattern (`src/quiz/presentation/schema/mutations/mutations_admin.py` is the reference). They still require `X-Operation-ID` like every other mutation (mandatory pattern #3) — including `login`, which happens before a session exists; the operation-id contract is per-request, not per-session.

**`AuthMiddleware` verifies and populates only; it never rejects for "not authenticated."** No `Authorization` header (or a header that fails to decode) → `request.state.user_session = None`, same behavior `Context.user_session` has today. Authorization enforcement stays exactly where it is now: the `strawberry.permission.BasePermission` classes in `permissions.py` (`IsAuthenticated`, `IsAdmin`, etc.), reading `info.context.user_session`. The middleware's only two states are "populated" and "stale" — never "forbidden."

**A stale permission-version short-circuits at the middleware, before GraphQL execution, as a raw HTTP 401.** Because the middleware runs pre-routing on the ASGI app, it can return a plain `Response(status_code=401, content={"code": "SESSION_STALE"})` outside the GraphQL response envelope entirely — this is not a GraphQL field error, it never reaches `strawberry`'s executor. Client-side, this is the standard "401 → call refresh → retry once" interceptor pattern, distinct from a normal `AuthenticationError` GraphQL response (which stays a 200 + typed union response, per the existing mutation-exception pattern, for "you don't have this permission" cases).

**Session = one active tenant per JWT (Slack-style), not a multi-tenant claims array.** Claims carry `user_id`, `is_staff`, `active_tenant_id`, `role`, `user_tenant_id`, plus two independent version numbers (next decision). Switching tenants re-mints the JWT via `SwitchTenantUseCase`; it does not require re-entering a password, since the caller is already authenticated — it only re-verifies that an active `UserTenant(user, tenant_id)` exists.

**Two independent permission-version scopes, not one.** `IS_STAFF` depends only on `MyUser.is_superuser` (global); `IS_ADMIN`/`IS_COLLABORATOR` depend only on the active `UserTenant.role` (per membership). A single version number would force every `UserTenant` edit anywhere to invalidate every session for that user, or vice versa. Two Redis keys — `perms_version:user:{user_id}` and `perms_version:user_tenant:{user_tenant_id}` — mirror the two independent sources exactly. Alternative considered: one version per user covering both, rejected because it conflates two update frequencies and scopes that have nothing to do with each other.

**Missing Redis key vs. unreachable Redis are handled differently, on purpose.** A key that doesn't exist (cold start, TTL, a Redis flush) is treated as an ordinary version mismatch (`0 != claims.version`) — it flows through the same stale-session path as a real permission change and self-heals via refresh, no special-casing needed. Only an actual connection/timeout error triggers fail-open, and that fail-open is bounded by a short JWT `exp` (target 10–15 min) and logged via `structlog` at warning level. Rationale: making all of authentication depend on Redis's uptime (fail-closed universally) is a worse failure mode than a bounded, logged staleness window during a genuine Redis outage — the existing event-bus dead-letter pattern in this codebase already accepts "best-effort, eventually consistent" for less critical paths; this applies the same trade-off philosophy to a case where the alternative is a hard outage.

**Reuse `account-audit-trail`'s `ENTITY_CHANGED` event for `UserTenant` invalidation instead of a new channel — but `MyUser` isn't on that event at all (corrected after implementation).** The event carries `content_type`/`previous_state`/`current_state` inside `event.data` (not `event.metadata`, as first assumed here — `AuditableAdminMixin` never uses `metadata`). The invalidation handler (a second subscriber, not a new producer) bumps `bump_user_tenant_version` when `role` changes, `is_active` changes, or the action is a soft-delete (`DELETION`) — broader than "role only," since a deactivated or soft-deleted membership needs its session invalidated too. `MyUser.is_superuser`, however, is **not** covered by this event: `MyUserAdmin` doesn't use `AuditableAdminMixin` at all — `account-audit-trail` deliberately scoped audit logging to `TENANT`/`TENANT_USER` only. Publishing `ENTITY_CHANGED` for `MyUser` here to reuse the same invalidation path would silently start auditing `MyUser` too, an unintended expansion of that other change's scope. `MyUserAdmin.save_model` instead bumps `bump_user_version` directly — no event, no audit-trail involvement, since the concern (permission-cache invalidation) isn't about auditing.

**`MyUser.USERNAME_FIELD = "email"`.** Login is by email (the field that's actually `unique=True`); keeping the inherited `"username"` default would mean `authenticate()` silently requires a field nobody's login form collects. **BREAKING** at the model level — needs a migration; low risk today since no login path exists yet to depend on the old default.

**`UserRepository`/`UserTenantRepository` use the Specification pattern instead of one method per query (adopted mid-implementation).** This project had a standing, not-yet-applied design agreement (services build a filter/`Specification` object, repos expose a single `find(spec)`, only the Django implementation ever touches `Q`) to avoid the repo interface growing one hand-written method per filter combination as the app's query needs grow. `account`'s auth repos are the first new repository/service pair built since that agreement, so it applies here: `src/shared/domain/specification.py` (`Specification`/`FieldFilterSpecification`, `&`/`|`/`~` composable, Django-free) plus `src/shared/infrastructure/persistence/django/specification.py` (`to_django_q`, imported only by the Django repo implementations). `UserRepository.authenticate()` is the one exception — it delegates to Django's fixed-signature `authenticate()` backend call, not an ORM filter, so there's no growing set of query variants to guard against there. `PermissionVersionRepository` (Redis key/value by a known id) is out of scope for this pattern; it isn't a filterable query store.

**Django's password hashing is reused; Django's session/login is not.** `authenticate()` (default `ModelBackend`, no custom backend configured) and `MyUser.check_password()` are pure ORM/algorithm calls with no dependency on `request.session` — safe to call from a `LoginUseCase` with zero coupling to Django's request cycle. `django.contrib.auth.login(request, user)` is not used at all; it requires `SessionMiddleware`, which is not — and should not be — mounted on `fastapp` (see Context).

## Risks / Trade-offs

- [Redis becomes a dependency in the request hot path for every GraphQL call] → Mitigated by the fail-open-on-outage decision above; latency impact is one `GET`/two `GET`s per request (STAFF path checks one key, tenant-scoped path checks two), not a query plan.
- [This change cannot land independently of `account-audit-trail`'s event/payload shape] → Sequencing dependency, not a blocker; call out explicitly in `tasks.md` when written.
- [`USERNAME_FIELD` migration touches the user model that `account-audit-trail`'s admin mixin work is also touching in parallel] → Low actual conflict risk (different fields), but coordinate merge order to avoid migration-number collisions in `account`'s migration history.
- [Bulk `UserTenant.role` reassignment (e.g., an admin re-org via bulk admin action) triggers one `publish()`/Redis `INCR` per row, sequentially] → Same trade-off already accepted in `account-audit-trail`'s design for bulk soft-delete: admin selections are small and manual, not a hot path; revisit only if that stops being true.
- [A leaked JWT remains valid for its full `exp` even after this invalidation mechanism catches a *permission downgrade*] → By design: this mechanism targets "permissions changed under a legitimate, still-valid identity," not "token compromised." Token compromise is out of scope (see Non-Goals); the short `exp` bounds this risk the same way it bounds the Redis-outage risk.
- [`redis.asyncio`'s connection pool binds to whichever event loop first uses it — a shared client reused across independent `asyncio.run()` calls from sync code (Django admin) raises "Event loop is closed" on the second call] → Discovered during implementation, not anticipated in the original design. Fixed at the source: sync-triggered call sites (the admin-side permission-invalidation subscriber, `MyUserAdmin.save_model`) each build a throwaway client (`create_redis_client()`) and close it within their own single `asyncio.run()`, instead of touching the shared singleton (`get_redis_client()`) at all. The singleton stays correct and intended only for the FastAPI service's own call sites, which run under one persistent event loop.

## Migration Plan

1. `USERNAME_FIELD` migration on `MyUser` first — independent of everything else, no data to backfill (no existing login path depends on the old default).
2. Redis connection settings (`main/project_settings.py`) + client wiring — additive, no behavior change until consumed.
3. `account/domain` and `account/application`: `LoginUseCase`, `SwitchTenantUseCase`, `RefreshSessionUseCase` — buildable and testable in isolation before touching the request path.
4. `eventing` subscriber to `ENTITY_CHANGED` for version bumps — depends on `account-audit-trail` having landed.
5. `AuthMiddleware` + `Context.user_session` simplification + `main/asgi.py` mount — this is the cutover step; until this lands, `auth.py`'s current inline decode keeps working unmodified, so steps 1–4 carry no risk to the running system.
6. GraphQL mutations for login/switch-tenant/refresh, wired to the use cases from step 3.

Rollback: steps 1–4 and 6 are additive (new files, new migration) and revert cleanly with a standard migration rollback + file removal. Step 5 (the middleware mount) is a one-line revert in `main/asgi.py` plus restoring `Context.user_session`'s previous body — no data migration involved in the cutover itself.

## Open Questions

- Exact `exp` value (10 vs. 15 minutes, or configurable per environment) — tunable later without changing the approach, the specs, or the task breakdown.
- Whether `RefreshSessionUseCase` needs its own narrower JWT verification (e.g., accept a token whose signature is valid but whose permission-version is stale, while still rejecting an expired or tampered one) — an implementation detail of that use case, doesn't change its external contract.
