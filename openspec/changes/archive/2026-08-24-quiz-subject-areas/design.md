## Context

See `proposal.md` - Why for motivation. The constraints that shape the approach:

- **Mandatory pattern #2** forbids an app from importing another app's Django models. `QuizArea`
  needs foreign keys to both `Quiz` and `Area`, so `Area` cannot live in `account` even though
  a tenant-scoped taxonomy would otherwise feel at home there. Both models go in `quiz`.
- **`QuizActiveMixin` is shared across two apps.** Seven models use it: five in `quiz`, plus
  `Tenant` and `UserTenant` in `account`. Adding a field to it is a two-app migration.
- **Postgres 15 and Django 6.1**, so `UniqueConstraint(nulls_distinct=False)` is available —
  relevant because the identity constraint spans a nullable column.
- **No read layer.** The root `Query` type is empty and no GraphQL mutation for areas is in
  scope, so the Django admin is the only way areas get created. Invariants must therefore hold
  at the model/admin layer, not only in a use case that nothing calls yet.

## Goals / Non-Goals

**Goals:**

- Make data cycles in the area hierarchy structurally unrepresentable rather than merely
  validated against.
- Keep `QuizArea` pointing at exactly one foreign key regardless of which level of the
  hierarchy it classifies against.
- Establish the models and invariants so a later read layer has something correct to expose.

**Non-Goals:**

- Arbitrary-depth taxonomies. See Decisions.
- A cross-tenant global catalog of areas.
- Any GraphQL surface, backfill of areas onto existing quizzes, or reporting.

## Decisions

### Self-referencing `Area` rather than two tables

**Alternative considered and rejected:** separate `Area` and `SubArea` models, which makes
cycles impossible at the schema level with no application rule at all. Rejected because of what
it does to `QuizArea`: a relation that must be able to point at either level becomes either a
polymorphic pair of nullable foreign keys plus a check constraint enforcing exactly one — every
query against it then branches — or a forced rule that quizzes only ever attach to sub-areas,
obliging every tenant to invent a filler child ("Tecnología / General") whether they want
levels or not. Splitting the table does not remove complexity; it relocates it into the
relation and makes it worse.

**Alternative considered and rejected:** a free-text qualifier on `QuizArea` (`"I"`, `"II"`).
This was the original shape of the idea. Rejected because it hides a second classifying
dimension inside an unvalidated string — `"I"`, `"i"` and `"1"` do not reconcile — and because
it is a field that only school-like tenants would ever populate, leaving it permanently empty
for the department-style tenants the model must serve equally.

### Two levels, enforced as "a parent must be a root"

The cap is not primarily a convenience. It is what makes cycles unrepresentable: a cycle of any
length requires at least one node that is simultaneously someone's child and someone's parent,
and the rule forbids exactly that. Depth and cycle-freedom are the same guarantee here, which
is why the cap is stated as an invariant rather than as a limit.

Enforcement is layered, because no single mechanism covers it:

- `CheckConstraint(~Q(parent=F("id")))` in the database catches the degenerate self-parent case,
  which is expressible without reading another row.
- The "a parent must itself be a root" rule requires looking at the prospective parent's own
  parent, so it cannot be a check constraint. It lives in the domain entity's `__post_init__`
  and is re-asserted in the admin form's `clean()`, since the admin is the only creation path
  in this change.
- The symmetric case — giving a parent to an area that already has children — must be checked
  on update as well, or the cap can be escaped by building bottom-up.

Raising the cap later means relaxing a validation, with no data migration. Lowering it after
arbitrary depth exists would mean restructuring live data, which is why the restrictive
direction is the default.

### Area identity spans a nullable column, so NULLs must compare equal

Identity is `(tenant, parent, name)` among active rows. `parent` is NULL for root areas, and
Postgres treats NULLs as distinct in a unique index by default — so the obvious constraint
would happily allow two root areas named "Ciencias" in the same tenant, which is precisely the
duplication the requirement exists to prevent. This is silent: the constraint appears to be
there and simply does not fire.

Resolved with `UniqueConstraint(..., nulls_distinct=False)`. Whether Django permits combining
`nulls_distinct` with `condition` (needed to scope the constraint to active rows, matching the
project's partial-constraint style) must be verified during implementation; if it does not, the
fallback is two partial constraints, one covering `parent__isnull=True` and one covering
`parent__isnull=False`, which is equivalent and portable.

### `tenant_user` is authorship, not identity

The user's first instinct was to scope identity by author, letting two teachers each own a
"Ciencias". Reconsidered and rejected: it fragments every organization-wide question by area,
which is the reason the model exists. `tenant_user` is retained on both models as a record of
who added the row — consistent with how `Quiz`, `Question` and `AnswerChoice` already carry it
— but takes no part in uniqueness.

### Deactivation frees the name

The identity constraint is scoped to active rows, so deactivating "Ciencias" lets a new
"Ciencias" be created. The deactivated row keeps its quizzes and its history. The alternative —
a global unique constraint — would mean a name is burned forever by a single mistaken creation,
with renaming the only escape.

`deactivated_at` goes on `QuizActiveMixin` rather than on `Area` alone, making it symmetric with
`QuizSoftDeleteMixin`'s existing `is_deleted`/`deleted_at`. The cost is a two-app migration
across seven tables for a field six of them do not yet need; the benefit is that
`ActivableAdminMixin.deactivate_instances`, which is shared by all of them, can stamp the field
in one place instead of every model growing its own variant later.

## Risks / Trade-offs

- **The mixin change touches seven tables in two apps, including `Tenant` and `UserTenant`.** →
  It is an additive nullable column with no default backfill, so the migration is a metadata-only
  `ADD COLUMN` in Postgres and does not rewrite the tables. Still, it must land as two
  migrations and be reviewed as a change to `account`, not only to `quiz`.
- **Existing rows have `is_active=False` with no `deactivated_at`.** → The field is nullable and
  stays NULL for them; "deactivated at an unknown time" is represented honestly rather than
  backfilled with a fabricated timestamp. Any consumer must treat NULL as "unknown", not as
  "never deactivated".
- **The two-level cap is enforced in application code, not fully in the database.** → A direct
  SQL insert or a migration could build a third level. Accepted: the same is already true of
  every other invariant this project enforces in entities, and the admin is the only write path
  today.
- **The admin is the sole creation path, so admin form validation is load-bearing** in a way it
  usually is not here. → The invariant lives in the domain entity and the admin calls into it,
  so a later GraphQL mutation inherits the same rule rather than reimplementing it.
- **Deactivating a parent leaves its children active**, pointing at an inactive parent. → Not
  resolved by this change; listing areas must decide whether to hide children of inactive
  parents. Flagged in Open Questions rather than guessed at, since no read layer exists to
  make the choice concrete.

## Migration Plan

1. `src/shared/.../models.py`: add `deactivated_at` to `QuizActiveMixin`.
2. Generate and apply one migration per affected app — `quiz` (five tables) and `account` (two).
   Additive nullable column; no data step.
3. Add `Area` and `QuizArea` with their constraints in a `quiz` migration. Verify the generated
   unique constraint actually emits NULLS NOT DISTINCT before applying it — if Django silently
   drops it when combined with `condition`, switch to the two-partial-constraint form.
4. Rollback: dropping the two new tables loses only area assignments; no existing table's data
   is modified by this change, and reversing the mixin migration drops a column nothing else
   reads.

## Open Questions

- Whether listing a tenant's areas should hide the children of a deactivated parent, or show
  them as orphaned. Both are defensible and the choice does not change any model, constraint,
  or task here — it is a presentation rule that becomes concrete once a read layer exists.
- Whether a quiz should be required to have at least one area before it can be exposed to a
  student, which would connect this capability to `quiz/quiz-composition`'s publishability rule.
  Deliberately left unlinked for now: coupling them would mean every existing quiz becomes
  unpublishable the moment this ships.
