## Context

Today `src/identity` (owns `MyUser`) and `src/tenant` (owns `Tenant`, `TenantUser`) are separate Django apps, both infrastructure + presentation(admin) only — no `domain`/`application` layers exist in either yet. `quiz` depends on tenant data only through a port: `src/quiz/domain/repositories/tenant_lookup_repository.py` (the ABC) is implemented by `TenantLookupRepositoryImpl` in `src/tenant/infrastructure/repositories/`, and wired at a single call site in `src/quiz/presentation/schema/mutations/mutations_admin.py`. See `proposal.md` for the motivation (creating a `TenantUser` today means coordinating two apps for one cohesive concept).

## Goals / Non-Goals

**Goals:**
- Collapse `identity` + `tenant` into one Django app, `account`, that owns `MyUser`, `Tenant`, and `UserTenant` (renamed from `TenantUser`).
- Tighten `UserTenant.user` from a raw UUID into a real FK now that the cross-app boundary that justified the UUID is gone.
- Leave zero footprint on `quiz` beyond one import path.
- Finish with a clean single migration for `account` — no migration archaeology.

**Non-Goals:**
- No new domain/application logic (use cases, domain services) is being introduced. `domain/` and `application/` under `account` stay empty scaffolding, ready for the first real use case (e.g., "create user with tenant") but that use case itself is out of scope here.
- No GraphQL schema for `account` — none exists today for `identity` or `tenant`, and this change doesn't add one.
- No change to the `TenantLookupRepository` port's contract or to `quiz`'s behavior.
- No production-data migration strategy — none exists to preserve (see proposal's Impact section).

## Decisions

**1. New app name: `account` (not `identity`, not `tenant`).**
Once the app owns both individual users and their organizational memberships, "identity" undersells it and "tenant" is even narrower. `account` reads naturally for "the thing a user has, including which org(s) they belong to." Class names `MyUser` and `Tenant` stay as-is per explicit instruction — only the app/module and `TenantUser` rename.

**2. `TenantUser` → `UserTenant`, and everything derived from it follows the same line.**
- File: `tenat_user.py` (pre-existing typo) → `user_tenant.py` (fixed as part of the same move, not a separate cleanup).
- DB table: `tenant_user` → `user_tenant`.
- Enum: `TenantUserRoleEnum` → `UserTenantRoleEnum`. `TenantTypeEnum` is untouched — it belongs to `Tenant`, not to the membership model.
- Admin class: `TenantUserAdmin` → `UserTenantAdmin`.
- Shared enums file `tenant_enums.py` → `account_enums.py`, since it now lives in `account` and holds enums for more than just "tenant" (`TenantTypeEnum` + `UserTenantRoleEnum`). This wasn't explicitly requested but follows the same consistency line as the rest of the renames — flagging here in case the user wants to keep the old filename.

**3. `UserTenant.user` becomes `ForeignKey("MyUser", on_delete=models.PROTECT)`.**
The raw `UUIDField` existed specifically so `tenant` never had to import `identity`'s Django model (the port pattern forbids cross-app model imports). Inside one app, that constraint doesn't apply, and a real FK buys referential integrity plus reverse access (`my_user.usertenant_set`) for free. `PROTECT` matches the existing `UserTenant.tenant` FK's `on_delete` — deleting a `MyUser` or a `Tenant` that still has active memberships should fail loudly, not cascade silently, until a real deactivation flow exists.

**4. Migration history is wiped, not preserved.**
Django has no clean way to move a model between apps without either faking migration state or squashing with `state_operations` — both add ceremony to preserve history nobody needs, since the project is ~4 days old with no data worth keeping (confirmed by user). Simpler path: delete `src/identity/.../migrations/0001_initial.py` and `src/tenant/.../migrations/0001_initial.py`, create the models fresh under `src/account/.../models/`, generate one new initial migration, `make reset_db`.

**5. `TenantLookupRepositoryImpl` moves as-is; the port doesn't change.**
It's the producer side of an existing port pattern (`quiz` defines, `tenant`/now `account` implements). Only its package path changes (`src.tenant.infrastructure.repositories` → `src.account.infrastructure.repositories`); its two methods (`tenant_exists`, `tenant_user_exists`) keep their signatures untouched, so `quiz`'s domain layer is unaffected.

**6. Docstrings added during the move follow Google convention.**
Per explicit instruction: classes and non-trivial flows in the merged module get Google-style docstrings (`Args:`/`Returns:`/`Raises:`) where the project's existing "only when WHY is non-obvious" rule already calls for one — this doesn't relax that rule, it only fixes the format once a docstring is warranted.

## Risks / Trade-offs

- **[Risk]** Deleting migrations and models by hand is easy to get subtly wrong (leftover `ContentType`/permission rows pointing at the old `identity`/`tenant` app labels) → **Mitigation**: `make reset_db` drops and recreates the whole database, so stale `django_content_type`/`auth_permission` rows never survive the reset; no manual cleanup needed.
- **[Risk]** `PROTECT` on both FKs means deleting a `MyUser` with any tenant membership, or a `Tenant` with any member, will raise `ProtectedError` until membership rows are cleaned up first → **Mitigation**: acceptable for now (no deactivation/offboarding flow exists yet); revisit if/when a "deactivate user" use case is designed.
- **[Trade-off]** Renaming `account_enums.py` (see Decision 2) is a judgment call beyond what was explicitly asked → flagged for the user to veto before `tasks.md` locks in file paths.

## Migration Plan

1. Scaffold `src/account/` mirroring the existing `domain/application/infrastructure/presentation/shared` layout (domain/application empty).
2. Move + rename models, admin, enums, repository impl into `src/account/` per Decisions 1–3.
3. Update `main/settings/base.py` (`INSTALLED_APPS`, `AUTH_USER_MODEL`, `MIGRATION_MODULES`).
4. Update the one import in `src/quiz/presentation/schema/mutations/mutations_admin.py`.
5. Delete `src/identity/` and `src/tenant/` entirely.
6. Generate the fresh `account` migration, `make reset_db`, `make migrate`.
7. Run `make lint` and `make test` to confirm nothing else references the old paths.

No rollback plan needed beyond `git revert` — no deployed environment or real data exists yet.

## Open Questions

None — all decisions needed to write `tasks.md` are resolved above. Decision 2's `account_enums.py` rename is called out for veto, not left open; proceeding with it unless the user objects.
