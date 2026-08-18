## Why

`identity` (owns `MyUser`) and `tenant` (owns `Tenant`/`TenantUser`) are two separate Django apps today, but neither has any domain or application layer yet — both are infrastructure + admin only. Creating a user without a tenant lives entirely in `identity`, which is fine, but creating a `TenantUser` (a user's membership in a tenant) always requires coordinating two apps for something that is conceptually one aggregate: a user and their organizational membership. Since the project is ~4 days old with no production data and no spec-level behavior built on top of this split yet, this is the cheapest point at which to collapse it into one cohesive bounded context.

## What Changes

- **BREAKING** (internal only, no external consumers exist yet): merge `src/identity` and `src/tenant` into a single new Django app `src/account`, replacing both.
- Rename Django app label/module: `identity` + `tenant` → `account`. Update `INSTALLED_APPS`, `AUTH_USER_MODEL` (`identity.MyUser` → `account.MyUser`), and `MIGRATION_MODULES` in `main/settings/base.py`.
- Move `MyUser` (unchanged), `Tenant` (unchanged) into `src/account/infrastructure/persistence/django/models/`.
- Rename `TenantUser` → `UserTenant`, fixing the pre-existing `tenat_user.py` filename typo in the same move; apply the same `user_tenant` naming line to everything derived from it (enum, admin class, db table, filenames).
- Convert `UserTenant.user` from a raw `UUIDField` to a real `ForeignKey("MyUser", on_delete=models.PROTECT)` — the cross-app boundary that justified the raw UUID (port pattern, no direct model imports across apps) no longer exists once both models live in the same app. `UserTenant.tenant` keeps its existing `ForeignKey("Tenant", on_delete=models.PROTECT)`.
- Set `UserTenant`'s table name to `user_tenant` (was `tenant_user`), matching the corrected model name.
- Rename `TenantUserRoleEnum` → `UserTenantRoleEnum`; `TenantTypeEnum` is unaffected (it belongs to `Tenant`, not `UserTenant`).
- Move `TenantLookupRepositoryImpl` (the producer-side implementation of quiz's `TenantLookupRepository` port) from `src/tenant/infrastructure/repositories/` to `src/account/infrastructure/repositories/`. The port itself (`src/quiz/domain/repositories/tenant_lookup_repository.py`) is untouched — only its implementer's import path changes.
- Update the single wiring site that imports the impl: `src/quiz/presentation/schema/mutations/mutations_admin.py`.
- Delete `src/identity` and `src/tenant` entirely (models, migrations, admin, apps.py) once ported.
- Wipe and regenerate migration history for the merged app: drop the old `identity`/`tenant` migrations, generate one fresh initial migration under `account`, and rebuild the local database (`make reset_db` + `make migrations` + `make migrate`). No production data exists to preserve.
- Add Google-style docstrings (Args/Returns/Raises where applicable) to the merged module's classes and any non-trivial flow, per the project's "docstring only when WHY is non-obvious" rule.

## Capabilities

No spec-level behavior changes: this is a pure internal restructuring (app rename, model move, FK tightening, migration rebuild). The port contract `quiz` depends on (`TenantLookupRepository.tenant_exists` / `tenant_user_exists`) keeps its exact signature and semantics — only the class implementing it moves. `openspec/specs/quiz/tenant-scoping/spec.md` describes that contract in terms of the port and needs no change. `skip_specs: true` is set in this change's `.openspec.yaml`.

### New Capabilities
(none)

### Modified Capabilities
(none)

## Impact

- **Code**: `src/identity/**` and `src/tenant/**` deleted; new `src/account/**` created. One import updated in `src/quiz/presentation/schema/mutations/mutations_admin.py`.
- **Settings**: `main/settings/base.py` — `INSTALLED_APPS`, `AUTH_USER_MODEL`, `MIGRATION_MODULES`.
- **Database**: `tenant_user` table renamed to `user_tenant` with a new FK column (`user_id` instead of a bare `user` UUID column); `identity_myuser`/`tenant_*`-labeled migration history replaced by a single `account` migration. Requires a full local DB reset — acceptable, no real data exists yet.
- **Tests**: none currently import `tenant`/`identity` models directly (verified — `quiz` tests use raw UUIDs for `tenant`/`tenant_user` fields on `QuizForm`, not model imports), so no test changes are required by the move itself. New tests for the merged `account` app's models/admin can be added as part of this change's tasks if desired.
- **Consumers**: `quiz` app — no code changes beyond the single import path, since it only ever depended on the port abstraction, not on `tenant`'s or `identity`'s internals.
