## 1. Shared mixin: deactivation timestamp

- [x] 1.1 Add `deactivated_at = models.DateTimeField(blank=True, null=True, editable=False)` to `QuizActiveMixin` (`src/shared/infrastructure/persistence/django/models.py`), mirroring `QuizSoftDeleteMixin`'s `deleted_at`
- [x] 1.2 Generate the `quiz` app migration for the mixin change — it touches `Quiz`, `Question`, `AnswerChoice`, `QuizUserResult`, `QuizUserResultHistory`
- [x] 1.3 Generate the `account` app migration — **it touches only `Tenant`**, not `UserTenant` as planned: `UserTenant` already declared its own `deactivated_at` (paired with `activated_at`), which Django allowed as an override of the abstract base's field. That local redeclaration was removed so the mixin is the single definition; it produced no migration, confirming the two were identical. So six models gained the column, not seven
- [x] 1.4 Confirm both migrations are additive nullable `ADD COLUMN` with no data step — existing inactive rows keep `deactivated_at = NULL`, meaning "deactivated at an unknown time", and must not be backfilled with a fabricated timestamp
- [x] 1.5 `ActivableAdminMixin.deactivate_instances` (`src/shared/presentation/admin/mixins.py`) also sets `deactivated_at=timezone.now()`; `activate_instances` clears it back to `None` — same shape as `SoftDeleteAdminMixin`

## 2. Domain: Area entity and invariants

- [x] 2.1 Create `src/quiz/domain/entities/area_entity.py` with `AreaEntity` as a `@dataclass(frozen=True)` and a `from_model` classmethod, per the project's entity convention
- [x] 2.2 `AreaEntity.__post_init__` enforces that an area is not its own parent
- [x] 2.3 Add the "a parent must itself be a root" rule as a pure domain function taking the prospective parent's own parent — it cannot live in `__post_init__` alone, since it needs to read another area
- [x] 2.4 Cover the update direction of the same rule: assigning a parent to an area that already has children must be rejected, or the two-level cap can be escaped by building bottom-up
- [x] 2.5 Add the area exceptions to `src/quiz/domain/exceptions.py` as `DomainError` subclasses, so a future mutation maps them to `ValidationErrorResponse` rather than `InternalErrorResponse`

## 3. Infrastructure: models and migration

- [x] 3.1 Create `src/quiz/infrastructure/persistence/django/models/area.py`: UUID PK, `name`, `parent = FK("self", null=True, blank=True, on_delete=PROTECT, related_name="children")`, `tenant`, `tenant_user`, inheriting `QuizTimeStampMixin` and `QuizActiveMixin` (no soft-delete mixin — deactivation is the lifecycle here)
- [x] 3.2 `Area.Meta.constraints`: `CheckConstraint` rejecting `parent_id == id`
- [x] 3.3 `Area.Meta.constraints`: unique on `(tenant, parent, name)` scoped to `is_active=True`, declared with `nulls_distinct=False` so two root areas cannot share a name — Postgres treats NULLs as distinct by default and would silently allow the duplicate
- [x] 3.4 Verified: Django **does** accept `nulls_distinct` together with `condition`, and emits `CREATE UNIQUE INDEX ... (tenant_id, parent_id, name) NULLS NOT DISTINCT WHERE is_active`, confirmed against real Postgres via `pg_indexes`. The two-partial-constraint fallback was not needed
- [x] 3.5 Create `src/quiz/infrastructure/persistence/django/models/quiz_area.py`: UUID PK, FK to `Quiz` and to `Area` (both `PROTECT`, with `related_name`), `tenant`, `tenant_user`, `QuizTimeStampMixin`, and a unique constraint on `(quiz, area)`
- [x] 3.6 Export `AreaModel` and `QuizAreaModel` from `src/quiz/infrastructure/persistence/django/models/__init__.py` and add them to `__all__`, following the existing aliasing style
- [x] 3.7 Generate the migration creating both tables; apply it and confirm in `psql` that the unique index on `area` reads `NULLS NOT DISTINCT`

## 4. Infrastructure: repositories

- [x] 4.1 Define the area repository port in `src/quiz/domain/repositories/` as an ABC with `async def` methods, per convention
- [x] 4.2 Implement `AreaRepositoryImpl` in `src/quiz/infrastructure/repositories/area_repository_imp.py` as sync `def` decorated with `@async_database()`
- [x] 4.3 The lookup that resolves an existing area by `(tenant, parent, name)` must filter `is_active=True`, matching the identity constraint — otherwise it returns rows the constraint does not consider to exist

## 5. Presentation: Django admin

- [x] 5.1 Create `src/quiz/presentation/admin/area.py` with `AreaAdmin`, using `ActivableAdminMixin` (not `CommonAdminActionsMixin` — `Area` has no soft-delete fields)
- [x] 5.2 `AreaAdmin` shows name, parent, tenant and active state; `list_filter` on active state; `readonly_fields` for `id`, `deactivated_at`, `created_at`, `updated_at`
- [x] 5.3 `AreaAdmin` form `clean()` re-asserts the domain invariants by calling into the domain functions from task group 2 — do not reimplement the rules in the form. The admin is the only creation path in this change, so this validation is load-bearing
- [x] 5.3b **Unplanned but required**: `tenant`/`tenant_user` are `editable=False` and NOT NULL, so a plain `ModelForm` omitted them and *every* admin save failed the constraint — meaning areas could not be created anywhere, since they have no mutation. `AreaAdminForm` reintroduces `tenant` as an explicit `forms.UUIDField` (the model field stays non-editable) validated through the existing `TenantLookupRepository` port rather than importing `account`'s models; `save_model` sets `tenant_user` from `request.user.id` on create only, so authorship is never rewritten on edit. Note `Quiz` has the same latent limitation — pre-existing, and harmless there because `create_quiz` supplies the tenant
- [x] 5.4 Restrict the `parent` choices in the admin form to active root areas of the same tenant, so the two-level cap is enforced by construction and not only by error message
- [x] 5.5 Create `src/quiz/presentation/admin/quiz_area.py` with `QuizAreaAdmin`; use `raw_id_fields` or an autocomplete for `quiz` and `area` so the change form does not load every row
- [x] 5.6 Register both in `src/quiz/presentation/admin/__init__.py` and add them to `__all__`

## 6. Tests

- [x] 6.1 Domain: an area cannot be its own parent; a root may be a parent; an area with a parent may not be a parent
- [x] 6.2 Domain: assigning a parent to an area that already has children is rejected
- [x] 6.3 Infrastructure: two root areas with the same name in the same tenant are rejected — this is the test that catches a `nulls_distinct` regression, so assert it against a real constraint violation rather than an application-level check
- [x] 6.4 Infrastructure: the same name is accepted under different parents, and in different tenants
- [x] 6.5 Infrastructure: deactivating an area frees its name for a new active area, and the deactivated row survives untouched
- [x] 6.6 Infrastructure: relating the same quiz and area twice is rejected; relating one quiz to two areas succeeds
- [x] 6.7 Admin: `deactivate_instances` stamps `deactivated_at`, `activate_instances` clears it
- [x] 6.8 Add area and quiz-area factories to `tests/fixtures/quiz_fixtures.py`, following the existing `make_*` closure style

## 7. Verification

- [x] 7.1 `make lint` — black/isort clean, no new flake8 violations. The target still exits non-zero on the same 24 pre-existing errors documented in `quiz-authoring-ordering` (E501 in `0001_initial` migrations, `F401` in the `apps.py` files)
- [x] 7.2 `make test` green, coverage of `src/` not below its current 94%
- [x] 7.3 `make migrations` produces no unexpected additional migration — confirms the models and the hand-checked migrations agree
- [x] 7.4 Apply all three migrations against a real database (`make migrate`) and confirm the seven mixin-affected tables gained a nullable `deactivated_at` without a table rewrite
- [x] 7.5 In the Django admin, build "Ciencias" → "Ciencias I", confirm a third level is refused, confirm a second root "Ciencias" is refused, then deactivate "Ciencias" and confirm the name can be reused
