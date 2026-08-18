## 1. Scaffold `src/account`

- [x] 1.1 Create `src/account/{domain,application,infrastructure,presentation,shared}` mirroring the existing app layout (`domain/` and `application/` stay empty, matching `identity`/`tenant` today).
- [x] 1.2 Create `src/account/apps.py` with `AccountConfig(name="src.account", label="account")`, importing `src.account.presentation.admin` in `ready()`.
- [x] 1.3 Create `src/account/infrastructure/persistence/django/models/__init__.py`, `src/account/infrastructure/persistence/django/migrations/__init__.py`, `src/account/infrastructure/repositories/__init__.py`, `src/account/presentation/admin/__init__.py`.

## 2. Move and rename models

- [x] 2.1 Move `MyUser` (`src/identity/infrastructure/persistence/django/models/user.py`) to `src/account/infrastructure/persistence/django/models/user.py` unchanged.
- [x] 2.2 Move `Tenant` (`src/tenant/infrastructure/persistence/django/models/tenant.py`) to `src/account/infrastructure/persistence/django/models/tenant.py` unchanged.
- [x] 2.3 Move `TenantUser` (`src/tenant/infrastructure/persistence/django/models/tenat_user.py`) to `src/account/infrastructure/persistence/django/models/user_tenant.py`, renaming the class to `UserTenant` and `Meta.db_table` to `"user_tenant"`.
- [x] 2.4 Convert `UserTenant.user` from `models.UUIDField(editable=False)` to `models.ForeignKey("MyUser", on_delete=models.PROTECT)`. Confirm `UserTenant.tenant` keeps `on_delete=models.PROTECT`.
- [x] 2.5 Move `src/tenant/shared/tenant_enums.py` to `src/account/shared/account_enums.py`; rename `TenantUserRoleEnum` → `UserTenantRoleEnum`, keep `TenantTypeEnum` as-is. Update the two models' imports accordingly.
- [x] 2.6 Add Google-style docstrings to `MyUser`, `Tenant`, `UserTenant` where the WHY isn't obvious from the field alone (e.g., why `UserTenant.user`/`.tenant` use `PROTECT`). `UserTenant` got one (the PROTECT rationale); `MyUser`/`Tenant` didn't need one — nothing non-obvious beyond what's already stated in CLAUDE.md's PK convention.

## 3. Move admin

- [x] 3.1 Move `MyUserAdmin` (`src/identity/presentation/admin/user.py`) to `src/account/presentation/admin/user.py` unchanged.
- [x] 3.2 Move `TenantAdmin` (`src/tenant/presentation/admin/tenant.py`) to `src/account/presentation/admin/tenant.py` unchanged.
- [x] 3.3 Move `TenantUserAdmin` (`src/tenant/presentation/admin/tenant_user.py`) to `src/account/presentation/admin/user_tenant.py`, renaming the class to `UserTenantAdmin` and updating `list_display`/`search_fields` for the new FK field (`search_fields` can no longer search a UUID field by text the same way — use `user__email`/`user__username` instead of `"user"`).

## 4. Move the tenant-lookup port implementation

- [x] 4.1 Move `TenantLookupRepositoryImpl` from `src/tenant/infrastructure/repositories/tenant_lookup_repository_imp.py` to `src/account/infrastructure/repositories/tenant_lookup_repository_imp.py`, updating its internal model imports to `src.account...` and its `tenant_user_exists` query to use the new FK. Changed `user=tenant_user_id` to `user_id=tenant_user_id` for clarity now that `user` is a real FK.
- [x] 4.2 Update `src/account/infrastructure/repositories/__init__.py` to export `TenantLookupRepositoryImpl`.
- [x] 4.3 Update the import in `src/quiz/presentation/schema/mutations/mutations_admin.py` from `src.tenant.infrastructure.repositories` to `src.account.infrastructure.repositories` (and reordered it alphabetically among the `src.*` imports per project convention).

## 5. Update settings

- [x] 5.1 In `main/settings/base.py`: replace `"src.tenant"` and `"src.identity"` in `INSTALLED_APPS` with `"src.account"`.
- [x] 5.2 Change `AUTH_USER_MODEL` from `"identity.MyUser"` to `"account.MyUser"`.
- [x] 5.3 In `MIGRATION_MODULES`, replace the `"identity"` and `"tenant"` entries with `"account": "src.account.infrastructure.persistence.django.migrations"`.

## 6. Delete the old apps

- [x] 6.1 Delete `src/identity/` entirely.
- [x] 6.2 Delete `src/tenant/` entirely.
- [x] 6.3 Grep the repo for any remaining `src.identity` / `src.tenant` / `TenantUser` / `tenant_enums` references and fix or confirm none remain outside this change's own files. Only hit: `TenantUserNotFoundError` in `src/quiz/domain/exceptions.py` — `quiz`'s own domain exception class, doesn't import the moved model, out of scope for this change.

## 7. Rebuild the database

- [x] 7.1 Delete the old migration files (removed with the app directories in step 6; no orphaned `.pyc` found).
- [x] 7.2 Generate the fresh `account` migration (`makemigrations account` against the running `admin` service) — one `0001_initial.py` creating `MyUser`, `Tenant`, `UserTenant`.
- [x] 7.3 `make reset_db` is not a real Django command (`django-extensions` isn't a project dependency — pre-existing Makefile gap, unrelated to this change). Rebuilt the database manually instead: `DROP DATABASE ... WITH (FORCE)` + `CREATE DATABASE` via psql in the `db` container.
- [x] 7.4 `make migrate` to apply the fresh migration set — all migrations (including `account.0001_initial`) applied cleanly.

## 8. Verify

- [x] 8.1 `make lint` — no new errors from the move. Remaining flake8 findings (E501 in the generated migration, F401 on the `ready()` import in `apps.py`) match the exact same pre-existing pattern already present in `quiz`/`eventing`'s own `apps.py`/migrations — not regressions. Fixed one real isort ordering issue in the generated migration and the import order in `mutations_admin.py`.
- [x] 8.2 `make test` — full suite run inside the `admin` container: 63/63 passed, unchanged.
- [x] 8.3 Verified via Django shell + HTTP (services already running in Docker, so this substituted for a manual browser click-through): created a `MyUser` + `Tenant` + `UserTenant` end to end, confirmed the FK (`user_id`/`tenant_id`), the `related_name="user_tenants"` reverse accessor, and that `PROTECT` blocks deleting a `MyUser` with an active membership. Confirmed `admin.site._registry` has `TenantAdmin`/`MyUserAdmin`/`UserTenantAdmin` all under `app_label == "account"`, and `/admin/login/` returns HTTP 200. (The dev server's autoreload thread crashed once mid-edit on a transient migration-graph error and needed one `docker compose restart admin` to recover — confirmed via a fresh `manage.py migrate --check` and `manage.py check`, both clean, that this wasn't a real code issue.)
- [x] 8.4 Confirmed `openspec/specs/quiz/tenant-scoping/spec.md` has no diff (`git status` clean on `openspec/specs/`) — port contract unchanged.
