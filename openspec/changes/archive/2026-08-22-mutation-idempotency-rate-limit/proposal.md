## Why

`jwt-session-auth` shipped the transport-level auth boundary (`AuthMiddleware`) but left two adjacent gaps that surfaced as soon as we started reasoning about client retries against it. First, `Context.operation_id` (`src/shared/presentation/schema/context.py:17-27`) already conflates two unrelated purposes under one name: it's logged and echoed back on every error response purely for tracing (`mutation_handler.py` passes it to every `logger.warning`/`logger.error` call and every `BaseErrorResponse`), while `src/quiz/application/create_quiz_use_case/use_case.py:47` separately hand-translates that same value into `EventBusMessage.correlation_id` — a field the event bus already defines natively (`messages.py:21-26`) for exactly this purpose. No code path actually deduplicates a mutation today, despite `CLAUDE.md`'s mandatory pattern #3 already describing `operation_id` as being "for mutation idempotency." Building real idempotency on top of a name that's already doing tracing duty would make the dedup logic and the trace-correlation logic collide under one field. Second, the GraphQL API (`main/asgi.py`) has no request-volume defense at all: nothing bounds how many requests a single IP can send, and `LoginService.login()` (`src/account/application/login_use_case/service.py`) has no attempt-throttling, leaving credential brute-forcing wide open.

## What Changes

- Rename `Context.operation_id` → `Context.correlation_id` (`X-Operation-ID` header → `X-Correlation-ID`) across `context.py`, `@handle_mutations_exceptions` (`mutation_handler.py`), every mutation resolver, and every response type that carries it (`BaseErrorResponse`, `QuizGenericPayload`, `LoginResponse`, etc.). **BREAKING**: both the request header name and the `operation_id` GraphQL response field name change for every client. `create_quiz_use_case`'s manual `correlation_id=operation_id` translation is removed — the value flows to `EventBusMessage.correlation_id` under its own name now.
- Remove the unused `get_operation_id()` nanoid generator in `responses.py:10-11` — dead code, superseded by this change, and its existence contradicts mandatory pattern #3 (never generate this server-side).
- Reintroduce `X-Operation-ID` with a new meaning: a client-minted idempotency key. Contract: the client mints one UUID per distinct mutation attempt (e.g. per button click), reuses the same UUID across retries of that same attempt (double-click, network timeout) until a terminal response arrives, and mints a fresh UUID after any terminal response — success or business/validation error alike. Internal/unexpected errors are not terminal from the client's perspective (it doesn't know whether the write happened) and must be retried with the same key.
- Add mutation idempotency enforcement, two layers:
  - Redis fast-path: atomic `SETNX`-based lock on `operation_id` with a short TTL, to short-circuit the common duplicate-click case without a Postgres round-trip. Fails open on Redis unavailability (same precedent as `AuthMiddleware._is_stale`), since it is not the correctness guarantee.
  - Postgres source of truth: a new `idempotency_keys` table (`operation_id` unique, `status`, `response_payload` JSON) with a migration. The key-row insert and the mutation's business write happen in one `transaction.atomic()` block per use case; a duplicate `operation_id` surfaces as `IntegrityError` on the unique constraint, mapped to a replayed response. This is what actually prevents duplicate rows when a client retries after not seeing a response (network latency, not adversarial replay) — Redis alone cannot guarantee it (outage, TTL eviction, and a race window between two near-simultaneous `SETNX` calls are all real failure modes for a cache-only lock).
  - Three-way response caching: success and business/validation errors (`DomainError`/`ApplicationError`) are cached and replayed verbatim on a duplicate `operation_id`; unexpected internal errors are not cached — the lock is released so a retry genuinely re-attempts the write.
- Add `RateLimitMiddleware` in `src/shared/presentation/` (same `BaseHTTPMiddleware` pattern as `AuthMiddleware`, mounted outermost/before it in `main/asgi.py` so it runs before JWT decode). General bucket, keyed by `request.client.host` (the real TCP peer IP — this deployment has no reverse proxy in front of `uvicorn` per `devops/docker-compose.yaml`, so `X-Forwarded-For` is untrusted/unset and must not be used), atomic Redis `INCR`+`EXPIRE`, applied to every request except the login mutation.
- Add a stricter, separate login-attempt throttle inside the login flow (`LoginService.login()` or its GraphQL resolver), same atomic-`INCR` primitive, its own Redis key namespace, a lower threshold than the general bucket — this cannot live in the generic middleware without parsing the GraphQL document to detect the `login` mutation, so it belongs where the login flow already lives.
- Update `CLAUDE.md` mandatory pattern #3 to describe the split (`correlation_id` for tracing, `operation_id` for idempotency) instead of the current single-purpose description.

## Capabilities

### New Capabilities
- `shared/mutation-idempotency`: the `correlation_id`/`operation_id` contract for GraphQL mutations — tracing propagation to the event bus, and the idempotency guarantee (Redis fast-path + Postgres unique-constraint source of truth + three-way response caching) that prevents duplicate writes from repeated client submissions of the same logical action.
- `shared/rate-limiting`: IP-based request throttling — a general bucket covering all traffic, and a stricter login-specific bucket guarding `LoginService.login()` against credential brute-forcing.

### Modified Capabilities
(none — no capability under `openspec/specs/` currently documents mutation error/response contracts or request throttling; `account/auth-session` from `jwt-session-auth` hasn't been synced to main specs yet and doesn't cover either concern)

## Impact

- `src/shared/presentation/schema/context.py` (`operation_id` → `correlation_id`, new `operation_id` idempotency-key property)
- `src/shared/presentation/schema/responses.py` (rename fields, remove `get_operation_id()`)
- `src/shared/presentation/decorators/mutation_handler.py` (rename, add idempotency lock/replay around the wrapped call)
- `src/shared/presentation/auth_middleware.py` (ordering reference — `RateLimitMiddleware` mounts before it)
- `src/shared/presentation/rate_limit_middleware.py` (new)
- `src/eventing/infrastructure/persistence/django/models/` (new `IdempotencyKey` model, alongside `FailedEventMessage`/`AuditLog` — `src.shared` isn't a registered Django app, `eventing` already hosts this project's cross-cutting non-domain persistence) + migration
- `src/shared/infrastructure/cache/redis_client.py` (reused, no new infra — already provisioned per `jwt-session-auth`)
- `main/asgi.py` (register `RateLimitMiddleware`, mount order)
- `src/account/application/login_use_case/service.py` and/or its GraphQL resolver (login-specific throttle)
- Every mutation resolver and response/payload type currently referencing `operation_id` (`quiz` and `account` presentation layers) — mechanical rename
- `src/quiz/application/create_quiz_use_case/use_case.py` (drop the manual `correlation_id=operation_id` translation)
- `CLAUDE.md` mandatory pattern #3 (doc update)
- **BREAKING** for any GraphQL client: header rename (`X-Operation-ID` → `X-Correlation-ID` for tracing) plus a new required `X-Operation-ID` header per mutation (idempotency key) plus the `operation_id` → `correlation_id` response field rename. Frontend work is out of scope for this backend change but must land in the same rollout.
