## Context

See `proposal.md` - Why. Relevant current state:

- `AuditLog` (in `eventing`) and its migration already exist, fully shaped (`content_type`/`source_type`/`action_type`, `user`, `tenant`, `correlation_id`, `metadata.previous_state`/`current_state`), with a read-only `AuditLogAdmin`. Nothing writes to it yet.
- `TenantAdmin`/`UserTenantAdmin` do plain `ModelAdmin` CRUD directly against the ORM — no use case layer sits in front of them (`account`'s `application/` layer is still empty/WIP for this path).
- The event bus (`src/shared/infrastructure/event_bus/`) is explicitly built to be called from sync Django admin code: `publish()` runs a subscribed async handler via `asyncio.run()` when there's no event loop, and a failing handler is caught, logged, and handed to the existing dead-letter `failure_sink` — it never propagates back to the caller.
- `quiz` already has the reference pattern for a producer/consumer pair: its own `QuizEventChannel` enum in `quiz/shared/`, a handler in `infrastructure/event_handlers/`, subscribed in `QuizConfig.ready()`.

## Goals / Non-Goals

**Goals:**
- Every Tenant/UserTenant create, edit, and soft-delete made through Django admin produces an `AuditLog` row.
- Reuse the existing `AuditLog` schema and the existing event bus as-is — no new infrastructure.

**Non-Goals:**
- Auditing the GraphQL API path (`source_type=API`) — `AuditLogSourceEnum` already anticipates it, but wiring mutations is separate follow-up work, not part of this fast pass.
- Auditing any entity beyond Tenant/UserTenant (Quiz, Question, etc.) — `AuditLogContentTypeEnum` already lists them, but only `TENANT`/`TENANT_USER` are wired here.
- Hard-delete auditing — Tenant/UserTenant are only ever soft-deleted through the admin actions this change touches; `has_delete_permission` is untouched.
- The `UserTenantInLineAdmin` inline on `TenantAdmin` — reverted, not redesigned. Editing `UserTenant` inline (with its own audit-safe delete handling) is a separate future change if still wanted.

## Decisions

**One channel per bounded context, not one per entity×action.** `AccountEventChannel.ENTITY_CHANGED` carries `content_type`/`action_type` inside `event.data`, exactly mirroring how those fields already live on `AuditLog` itself. Alternative considered: a channel per (entity, action) pair (`TENANT_CREATED`, `TENANT_UPDATED`, ...) — rejected because it multiplies channels for every future audited entity (10 content types × 3 actions today) while the eventing-side handler logic would stay identical regardless; the payload already carries the classification, so the channel doesn't need to.

**A single, content-type-agnostic handler in `eventing`.** `handle_account_entity_changed(event)` just maps `event.data` onto `RecordAuditLogDTO` and calls `RecordAuditLogUseCase` — it doesn't branch on `content_type`. This keeps the consumer side unaware of `account`-specific concerns, so adding a new producer app later (e.g. `quiz` auditing its own entities) means adding another `subscribe()` call in `EventingConfig.ready()`, not new handler logic.

**`AuditableAdminMixin` lives in `account/presentation/admin/`, not `shared/`.** It needs a per-`ModelAdmin` `audit_content_type: AuditLogContentTypeEnum` class attribute and knows how to resolve `tenant` differently for `TenantAdmin` (the object's own id) vs `UserTenantAdmin` (`obj.tenant_id`) — that mapping is `account`-specific, not generic infra. Importing `AuditLogContentTypeEnum` from `eventing.shared.eventing_enums` into `account` is a plain enum/value import (not a repository or model import), so it doesn't trip the cross-app port-pattern rule.

**Previous-state capture in `save_model`:** on `change=True`, fetch `type(obj).objects.get(pk=obj.pk)` and serialize it (`django.forms.models.model_to_dict`) *before* calling `super().save_model(...)`, then serialize `obj` again afterward for `current_state`. On `change=False`, `previous_state={}`.

**Soft-delete auditing is per-object, not one aggregated entry per bulk action.** Overriding `soft_delete_instances` to iterate the queryset and publish one event per object, instead of a single event describing "N tenants soft-deleted." Alternative (one aggregated entry) was rejected: it can't answer "who deleted *this* tenant," which is the actual question that motivated this change. This is a deliberate exception to the "no ORM writes/reads in loops" mandatory pattern — justified because admin bulk-action selections are small and manually curated, not a hot path; each iteration is a `publish()` call, not an extra query, since `queryset.update(...)` (the real write) still runs once.

**Event publish happens after the underlying save/update commits**, not before — so an audit-handler failure (caught by the bus, sent to the dead-letter sink) never blocks or rolls back the actual admin operation. The audit trail is best-effort/eventually-consistent by the same design already accepted for the rest of the event bus.

## Risks / Trade-offs

- [Sync admin request pays for `asyncio.run()` + a DB write per publish] → Acceptable: Django admin is low-traffic, not a perf-sensitive path; revisit only if it becomes measurably slow.
- [A bulk soft-delete of many rows means many sequential `publish()`/`asyncio.run()` cycles in one request] → Acceptable given admin selections are small and manual; if bulk audit volume grows, batch `AuditLog` writes then, not now.
- [Audit write failure is silent to the admin user (caught by the bus, only visible via the dead-letter admin)] → Already the accepted behavior of the existing dead-letter/retry mechanism; no new risk introduced.

## Migration Plan

No database migration needed — `AuditLog` and its table already exist. This is a pure code change (new admin mixin, new `eventing` application/domain/infrastructure files, one new subscription in `EventingConfig.ready()`, and reverting the inline). Rollback is a plain revert; no data backfill either direction.
