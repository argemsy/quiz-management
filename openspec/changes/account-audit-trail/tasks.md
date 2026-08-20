## 1. Cleanup

- [x] 1.1 Revert `UserTenantInLineAdmin` and `inlines = [...]` from `src/account/presentation/admin/tenant.py`

## 2. Eventing: domain layer for AuditLog

- [x] 2.1 Add `AuditLogEntity` (`@dataclass(frozen=True)`, `from_model()` classmethod) in `src/eventing/domain/entities/audit_log_entity.py`
- [x] 2.2 Add `AuditLogRepository` ABC (`async def record(self, entity: AuditLogEntity) -> AuditLogEntity`) in `src/eventing/domain/repositories/audit_log_repository.py`

## 3. Eventing: infrastructure layer for AuditLog

- [x] 3.1 Add `AuditLogRepositoryImpl` in `src/eventing/infrastructure/repositories/audit_log_repository_imp.py` — sync `def record`, decorated with `@async_database()`, `bulk_create`-free single insert (this is a single-row write, not a loop)

## 4. Eventing: RecordAuditLogUseCase

- [x] 4.1 Add `RecordAuditLogDTO` (frozen Pydantic `BaseModel`) in `src/eventing/application/record_audit_log_use_case/dto.py` — fields: `content_type`, `source_type`, `action_type`, `object_id`, `object_repr`, `user`, `tenant`, `correlation_id`, `previous_state`, `current_state`
- [x] 4.2 Add `use_case.py` in `src/eventing/application/record_audit_log_use_case/` (`__init__.py`, `dto.py`, `use_case.py` — no separate `service.py`: matches the actual `persist_failed_event_use_case` shape, which has no service layer either; the design doc's mention of one was inaccurate)

## 5. Eventing: event handler + subscription

- [x] 5.1 Add `handle_account_entity_changed(event: EventBusMessage)` in `src/eventing/infrastructure/event_handlers/audit_event_handlers.py` — maps `event.data` to `RecordAuditLogDTO`, calls `RecordAuditLogUseCase`
- [x] 5.2 Subscribe it to `AccountEventChannel.ENTITY_CHANGED` in `EventingConfig.ready()` (`src/eventing/apps.py`), alongside the existing `failure_sink` registration

## 6. Account: event channel + admin mixin

- [x] 6.1 Add `AccountEventChannel(Enum)` with `ENTITY_CHANGED` in `src/account/shared/account_event_channels.py`
- [x] 6.2 Add `AuditableAdminMixin` in `src/account/presentation/admin/mixins.py`:
  - class attribute `audit_content_type: AuditLogContentTypeEnum` (set per subclass)
  - override `save_model(request, obj, form, change)`: on `change=True`, fetch and serialize the pre-image (`model_to_dict`) before calling `super().save_model(...)`; publish `ADDITION`/`CHANGE` after the save commits
  - override `soft_delete_instances(request, queryset)`: for each object in the queryset, serialize before/after state, call the existing bulk `queryset.update(...)`, then publish one `DELETION` event per object
  - shared `_publish_audit_event(request, obj, action_type, previous_state)` helper used by both overrides
  - `tenant` resolution is per-subclass: `TenantAdmin` uses the object's own id, `UserTenantAdmin` uses `obj.tenant_id`

## 7. Account: wire the mixin

- [x] 7.1 Add `AuditableAdminMixin` to `TenantAdmin` (`src/account/presentation/admin/tenant.py`) with `audit_content_type = AuditLogContentTypeEnum.TENANT`
- [x] 7.2 Add `AuditableAdminMixin` to `UserTenantAdmin` (`src/account/presentation/admin/user_tenant.py`) with `audit_content_type = AuditLogContentTypeEnum.TENANT_USER`

## 8. Tests

- [x] 8.0 Fix pre-existing bug found while testing: `UserTenant` has no explicit UUID primary key (defaults to `BigAutoField`), violating the project's own PK convention and breaking `AuditLog.object_id` (a `UUIDField`) for UserTenant audit rows. Added `id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` to `src/account/infrastructure/persistence/django/models/user_tenant.py` (matching `Tenant`) and migration `0002_alter_usertenant_id.py` (RemoveField+AddField, since Postgres can't cast bigint->uuid in place; safe pre-launch, no real UserTenant data exists yet).
- [x] 8.1 Unit test `RecordAuditLogUseCase` writes an `AuditLog` row with the expected fields
- [x] 8.2 Test `handle_account_entity_changed`/the real event-bus wiring records an `AuditLog` row (goes through `bus.publish()`, not a bare `await`, to match how the handler is actually invoked in production)
- [x] 8.3 Admin-level test covering: Tenant add, Tenant edit (previous/current state populated), Tenant soft-delete (one entry per object), and the same three for UserTenant — all passing

## 9. Verify

- [x] 9.1 `make lint-src` (black/isort/flake8 clean on every file this change touches; pre-existing lint debt in unrelated lines of `src/eventing/apps.py` and `tests/fixtures/eventing_fixtures.py` left as-is — not introduced by this change)
- [x] 9.2 `make test` (or targeted `pytest` on the new/changed test files) — full suite: 67 passed
- [ ] 9.3 Manually create/edit/soft-delete a Tenant and a UserTenant in Django admin, confirm rows appear in `AuditLogAdmin` with correct `user`, `created_at`, `content_type`, `action_type`, `source_type=ADMIN`
