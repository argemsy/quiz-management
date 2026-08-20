## Why

Admins can create, edit, and soft-delete `Tenant` and `UserTenant` records from Django admin with zero traceability: no record of who made the change or when, beyond Django's own internal `LogEntry` (which isn't surfaced anywhere and doesn't cover the GraphQL API). The `eventing` app already has a purpose-built `AuditLog` model (`content_type`/`source_type`/`action_type`, tenant scoping, `correlation_id`, before/after `metadata`) and a read-only admin view for it, but nothing writes to it — it's a fully designed, completely empty table.

## What Changes

- Add an `AccountEventChannel.ENTITY_CHANGED` channel: `account` admin publishes an event to the shared event bus on every Tenant/UserTenant create, edit, or soft-delete.
- Add an `AuditableAdminMixin` in `account/presentation/admin/` that `TenantAdmin` and `UserTenantAdmin` both use, publishing ADDITION/CHANGE on `save_model` and DELETION (per object, not aggregated) on the existing `soft_delete_instances` bulk action.
- Add the missing `eventing` write path for `AuditLog`: domain entity + repository port, infrastructure repository impl, and a `RecordAuditLogUseCase`, following the same 4-layer package convention already used by `persist_failed_event_use_case`.
- Add an `eventing` event handler subscribed to `AccountEventChannel.ENTITY_CHANGED` (registered in `EventingConfig.ready()`, same pattern as `quiz`'s `QUESTIONS_REQUESTED` subscription) that turns the event into an `AuditLog` row via the new use case.
- Revert the `UserTenantInLineAdmin` inline just added to `TenantAdmin` — it opens two problems out of scope for a fast fix: it bypasses `save_model`/`soft_delete_instances` entirely (Django routes inline mutations through `save_formset`, not the sibling `ModelAdmin`), and its default `can_delete` behavior hard-deletes `UserTenant` rows instead of soft-deleting them like every other path does. Keeping `UserTenant` editable only through its own `ModelAdmin` keeps this change to a single mutation path per model.

## Capabilities

### New Capabilities
- `eventing/audit-log`: recording an immutable, queryable `AuditLog` entry (who, when, what changed, previous/current state) for changes to audited entities, sourced from Django admin activity on `Tenant` and `UserTenant`.

### Modified Capabilities
(none — no existing spec covers admin traceability today)

## Impact

- `src/account/shared/account_event_channels.py` (new)
- `src/account/presentation/admin/mixins.py` (new)
- `src/account/presentation/admin/tenant.py`, `user_tenant.py` (use `AuditableAdminMixin`; revert inline on `tenant.py`)
- `src/eventing/domain/entities/audit_log_entity.py`, `domain/repositories/audit_log_repository.py` (new)
- `src/eventing/infrastructure/repositories/audit_log_repository_imp.py` (new)
- `src/eventing/application/record_audit_log_use_case/` (new: dto, service, use_case)
- `src/eventing/infrastructure/event_handlers/audit_event_handlers.py` (new)
- `src/eventing/apps.py` (subscribe the new handler in `ready()`)
- No schema change: `AuditLog` model and its migration already exist.
