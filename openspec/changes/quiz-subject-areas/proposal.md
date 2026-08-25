## Why

A quiz today has no subject. `QuizModel` carries `code`, `quiz_type`, `configuration`,
`tenant` and `tenant_user` and nothing that says what the exam is *about*. Every question a
tenant will eventually ask of this system — "how do our students do in Ciencias?", "show me
the Onboarding assessments", "which areas have no published quiz?" — is unanswerable, and
stays unanswerable no matter how many quizzes are created, because the classifying dimension
does not exist.

The classification cannot be a fixed enum: the vocabulary belongs to the tenant, not to the
system. A school classifies by subject (Ciencias, Matemática); a company classifies by
department (Tecnología, Recursos Humanos). Both need the same mechanism — a tenant-defined
set of named areas — and neither can be served by a list the system hardcodes.

It also cannot be a single flat name. Tenants distinguish variants of the same area: Ciencias I
and Ciencias II in a school, Backend and Data under Tecnología in a company. Encoding that as a
free-text qualifier (`"I"`, `"II"`) puts a second, unvalidated dimension inside a string:
`"I"`, `"i"` and `"1"` become three different variants that nothing reconciles, and "everything
under Ciencias" is not answerable without parsing. Making the variant a row instead gives it
identity — it can be renamed, deactivated, and joined.

## What Changes

- Add an `Area` model to the `quiz` app: UUID primary key, `name`, an optional self-referencing
  `parent`, `tenant`, `tenant_user`, timestamps, and the active flag from `QuizActiveMixin`.
  It lives in `quiz` rather than `account` because `QuizArea` must foreign-key to both `Quiz`
  and `Area`, and mandatory pattern #2 forbids an app from importing another app's models.
- **The area hierarchy is capped at two levels**: a root area has no parent, and an area with a
  parent may not itself be a parent. This is what makes data cycles unrepresentable — a cycle
  of any length requires some node to be both a child and a parent, which the rule forbids.
  Reinforced at the database level by a check constraint rejecting a row that is its own parent.
- Areas are owned by the organization, not by the person who created them: an area's identity
  is `(tenant, parent, name)`, unique among active areas. `tenant_user` records **authorship
  only** — who added it — and does not participate in identity. Two teachers in the same school
  who both reach for "Ciencias" land on the same row, so organization-wide reporting by area
  does not fragment.
  - `parent` is nullable, and Postgres treats NULLs as distinct in a unique index by default,
    which would let two root areas share a name. The constraint must therefore be declared with
    NULLs treated as equal (`nulls_distinct=False`, requiring Postgres 15 and Django 5+ — both
    already in use here), or split into two partial constraints covering the null and non-null
    cases separately.
- Add a `QuizArea` model to the `quiz` app relating a quiz to an area: UUID primary key, foreign
  keys to both, `tenant`, `tenant_user`, timestamps, and a unique constraint on
  `(quiz, area)`. **A quiz may belong to several areas** — an integrative exam can cover both
  Ciencias and Matemática. A relation restricted to one area would be a foreign key on `Quiz`
  with extra steps; the separate model exists precisely to allow more than one.
- `QuizArea` references an area at whichever level it sits — a root or a child. Because the
  hierarchy is one table, this stays a single foreign key rather than a polymorphic pair.
- Add `deactivated_at` to `QuizActiveMixin`, making it symmetric with `QuizSoftDeleteMixin`'s
  `is_deleted`/`deleted_at` pair. **This touches every model using the mixin: seven models
  across two apps** — `Quiz`, `Question`, `AnswerChoice`, `QuizUserResult`,
  `QuizUserResultHistory` in `quiz`, plus `Tenant` and `UserTenant` in `account` — so it needs
  a migration in each app. The alternative, defining the field only on `Area`, was rejected
  because it leaves the mixin asymmetric and duplicates the field the moment a second model
  needs it.
- `ActivableAdminMixin`'s bulk actions stamp `deactivated_at` when deactivating and clear it
  when reactivating, mirroring what `SoftDeleteAdminMixin` already does for `deleted_at`.
- Django admin for both new models, with areas filtered and grouped by parent.

### Not in scope

GraphQL surface for areas — no `createArea` mutation, no area field on the quiz payload, no
querying quizzes by area. The root `Query` type is still empty
(`src/shared/presentation/schema/schema.py:15`), so a read API for areas has nowhere to attach
yet; this change establishes the model, the invariants and the admin. Reporting and analytics
by area, which is the eventual motivation, likewise depend on a read layer that does not exist.

Also out of scope: relaxing the two-level cap, moving areas to a shared/global catalog across
tenants, and backfilling any area onto existing quizzes — quizzes created before this change
simply have no area until someone assigns one.

## Capabilities

### New Capabilities
- `quiz/subject-areas`: the tenant-defined classification of quizzes — what an area is, the
  two-level parent/child structure and the cycle-freedom it guarantees, area identity and
  ownership within an organization, deactivation, and how a quiz is related to one or more
  areas.

### Modified Capabilities
(none — `quiz/tenant-scoping` requires that tenant-affiliated interactions match the quiz's
tenant, which areas follow but do not change; `quiz/question-response`, `quiz/attempt-result`,
`quiz/question-ordering` and `quiz/quiz-composition` make no claim about classification)

## Impact

- `src/shared/infrastructure/persistence/django/models.py` (`QuizActiveMixin` gains
  `deactivated_at`)
- Migrations in **both** `src/quiz/` and `src/account/` for the mixin change — seven tables
- `src/quiz/infrastructure/persistence/django/models/{area,quiz_area}.py` (new) and the package
  `__init__.py` export list
- `src/quiz/domain/entities/area_entity.py` (new — carries the "a parent must be a root"
  invariant, which cannot be a database check because it must read another row)
- `src/quiz/domain/repositories/` and `src/quiz/infrastructure/repositories/` (area lookup and
  persistence, following the existing ABC + `*RepositoryImpl` + `@async_database()` convention)
- `src/quiz/presentation/admin/{area,quiz_area}.py` (new) and the admin package exports
- `src/shared/presentation/admin/mixins.py` (`ActivableAdminMixin` stamps/clears
  `deactivated_at`)
- `tests/fixtures/quiz_fixtures.py` (area factories) plus new domain and infrastructure tests
- No GraphQL schema change, so no snapshot refresh
