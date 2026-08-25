## Context

See `proposal.md` - Why for motivation. The constraints that actually shape the approach:

- **Question creation is asynchronous.** `CreateQuizUseCase` saves the `Quiz` under an
  idempotency reservation, then publishes `QUESTIONS_REQUESTED`; `handle_questions_requested`
  runs `CreateQuestionsUseCase` outside the request cycle. So any validation that must be able
  to reject the whole mutation has to run **before** the `Quiz` row is written — after that
  point the only failure channel is a dead letter. `_validate_questions` already exists for
  exactly this reason and its docstring says so.
- **`QuizConfiguration` is a frozen dataclass hydrated from raw JSON.**
  `QuizEntity._build_configuration` calls `QuizConfiguration(**data)` on whatever is in
  `Quiz.configuration`, and falls back to `QuizConfiguration()` when it's empty. Any field
  added is therefore both a Python default and a tolerated absence in existing rows.
- **Soft delete is pervasive.** `QuizSoftDeleteMixin` + `QuizActiveMixin` on `Question` and
  `AnswerChoice`, and every partial constraint in the app already conditions on
  `is_active=True, is_deleted=False`. Any counting rule that ignored that predicate would
  contradict the schema's own notion of what exists.
- **There is no delivery flow.** `QuizForm`, `QuizQuestionResponse` and `QuizUserResult` have
  models and constraints but zero use cases, and the root `Query` type is empty. The ordering
  strategy and the publishability rule have no production caller yet.

## Goals / Non-Goals

**Goals:**

- Land ordering and composition as **pure domain functions** with their own tests, so they are
  fully specified and verified before the delivery flow exists to call them.
- Make the authored order a total order at the database level, so no read is ever
  non-deterministic — including for rows created before this change.
- Keep the GraphQL surface strictly additive.

**Non-Goals:**

- Wiring ordering or publishability into a request path. Nothing serves a quiz to a taker yet.
- A `QuestionRepository.reorder()` or any write path for changing positions after creation.
  The Django admin's `list_editable` covers the author's need until editing mutations exist.
- Any stored `status` on `Quiz`. Publishability is derived; see Decisions.

## Decisions

### `total_questions_allowed` keeps its name and its role as the upper bound

**Alternative considered and rejected:** rename it to `max_questions_allowed` and introduce
`min_questions_allowed` as its symmetric partner. Cleaner naming, but it renames a field that
is already persisted in every `Quiz.configuration` JSON blob, forcing a data migration of the
JSONField for purely cosmetic gain.

**Also considered and rejected:** keep `total_questions_allowed` as "how many questions an
attempt delivers" and add a separate `max_questions_allowed` as "how many the quiz holds",
with the surplus acting as a replacement pool when a question is deleted. This is a coherent
and arguably richer model, but it introduces two similarly-named limits with no way for an
author to tell which governs, and it presupposes a selection algorithm that this change
explicitly does not build. Rejected as premature.

So: one upper bound (`total_questions_allowed`, unchanged), one new lower bound
(`min_questions_allowed`), one new per-question bound (`max_answers_allowed`).

### Upper bounds gate creation; the lower bound gates publication

The two limits answer different questions and fail at different times. Exceeding an upper
bound is an author error at submission — reject the mutation, write nothing. Falling under the
lower bound is a **state** a quiz can drift into long after creation, by soft-deleting a
question, and there is no request to reject at that moment. Treating both as creation-time
validation would make it impossible to delete a question from a minimally-sized quiz; treating
both as derived state would let an author create a 5000-question quiz.

Consequence, accepted: a quiz created below `min_questions_allowed` is permanently
unpublishable, because no mutation can add questions to an existing quiz. Fixing that belongs
to the editing change, not here.

### Publishability is derived, never stored

**Alternative considered and rejected:** a `Quiz.status` column (`DRAFT`/`PUBLISHED`) kept in
sync by signals or admin hooks. Rejected because it introduces a value that can disagree with
reality: soft-deleting a question through `SoftDeleteAdminMixin`'s bulk action is a plain
`queryset.update()` that fires no model signals, so a stored status would silently go stale
exactly in the case that matters most. A count evaluated on demand cannot drift.

The cost is a `COUNT(*)` per check. In the admin list this must be an annotated queryset
(`annotate(Count("questions", filter=Q(is_active=True, is_deleted=False)))`), never a per-row
count — a per-row count is an N+1 over the changelist and would violate mandatory pattern #1
in spirit.

### No unique constraint on `order`; a total order via `("order", "created_at")`

Django raises `ValueError: UniqueConstraint with conditions cannot be deferred`, so the
project's established partial-constraint style cannot be combined with `deferrable`. A
non-deferrable partial unique on `(quiz, order)` would abort any two-position swap halfway
through the `UPDATE`, forcing either an offset dance through temporary values or a deferred
constraint that Django won't build.

Chosen instead: an index for lookups, `Meta.ordering = ("order", "created_at")` for a total
order, and density (`1..N`, no gaps) guaranteed by the application at creation. Duplicate
positions are then a benign anomaly — the `created_at` tie-break keeps every read
deterministic — rather than an error the database must prevent. Reordering is a single-author
operation with no concurrency pressure, so the constraint buys little.

### `order` is derived from list position, not accepted as input

`QuizQuestionInput` is already a `list`; its order is the author's intent. Accepting an
explicit `order` field would create two sources of truth for the same fact and immediately
raise questions the spec would have to answer (what if they conflict? what if they're sparse?
what if two are equal?). Deriving via `enumerate(..., start=1)` in `CreateQuestionsUseCase`
guarantees density by construction and keeps the API unchanged.

Assignment lives in the **application** layer, not the repository: the entity that reaches
`QuestionRepositoryImpl.bulk_create` is already complete, so the repository stays a dumb
persister and the ordering rule stays testable without a database.

### Shuffling is seeded, not stored

**Alternative considered and rejected:** persist the resolved sequence of question ids on
`QuizForm` alongside `quiz_configuration_snapshot`. Explicit and trivially auditable, but adds
an unbounded JSON array per attempt for information that is fully determined by the attempt's
identity.

Chosen: `random.Random(seed)` with the seed derived from the `QuizForm` id, and from
`(quiz_form_id, question_id)` for answer choices, so each question's answer order is
independent and reproducible regardless of iteration order.

> **`hash()` must not be used to build the seed.** `PYTHONHASHSEED` randomizes `str` hashing
> per process, so a seed derived from `hash()` would produce a different order after every
> restart, breaking both the reload-stability and the audit-reproducibility requirements. The
> seed string is passed to `random.Random` directly, which is stable across processes and
> releases.

This pins us to the reproducibility of `random.Random`'s Mersenne Twister for a given seed —
a documented, stable property across processes and CPython releases. It is explicitly **not**
cryptographic: the shuffle is predictable to anyone who knows the attempt id, so it must never
be relied on to conceal anything, and never repurposed for a security-sensitive draw.

### The per-attempt freeze reuses `quiz_configuration_snapshot`

`QuizForm.quiz_configuration_snapshot` already exists and is documented as *"Immutable quiz
configuration captured when the form started"*. The ordering strategies live inside
`QuizConfiguration`, so they are captured by that snapshot for free — no new column, and the
"a started attempt is unaffected by later reordering" requirement is satisfied by a mechanism
already in place.

Authored positions are a different matter: they live on the `Question` rows, not in the
configuration, so an author reordering questions mid-attempt *would* be visible to an
in-progress attempt under the authored-order strategy. Fully isolating that needs the delivery
flow to resolve and hold its sequence at attempt start. The requirement is specified here; the
mechanism lands with that flow.

## Risks / Trade-offs

- **The data migration renumbers every existing question and answer choice.** → It runs inside
  the migration's transaction, orders deterministically by `created_at`, and uses a single
  `bulk_update()` per table rather than per-row saves. `pytest.ini` runs with `--nomigrations`,
  so the test suite does **not** exercise it — it must be verified by hand against a real
  database before deploying.
- **`Meta.ordering` changes the default sort of every existing query** against `Question` and
  `AnswerChoice`, including in the admin and in any implicit iteration. → This is the intended
  effect and the current implicit ordering is unspecified, so nothing can regress from a
  defined order to a worse one. Worth watching for queries that assumed insertion order.
- **Two ordering-strategy fields and two limit fields join four existing config fields that
  nothing reads.** → Mitigated by landing both rules as tested pure functions rather than as
  inert values: `validate_composition` runs in production from day one, and `is_publishable`
  is surfaced in the admin. `time_limit_minutes`, `allow_review` and `allowed_attempts` remain
  unread; this change does not make that worse but does not fix it either.
- **Admin inlines can insert rows that bypass `validate_composition`.** An author can add a
  seventh answer choice through `AnswerChoiceInline` even when `max_answers_allowed` is 5,
  because the limit is enforced in the create-quiz use case, not at the model layer. →
  Accepted for now: the admin is a staff-only tool and the alternative is duplicating domain
  rules into `ModelForm.clean()`. Recorded as a known asymmetry rather than silently ignored.
- **A quiz created below `min_questions_allowed` can never become publishable.** → Accepted
  and documented; resolved by the add-question mutation in the editing change.

## Migration Plan

1. Deploy the schema migration: add `order` to both tables (defaulting to `0`), renumber
   existing rows to a dense `1..N` per group ordered by `created_at` in a single `bulk_update`
   per table, then add the indexes and the `Meta.ordering` alteration. One migration file,
   forward-only in practice.
2. No JSONField migration. Quizzes predating this change have configurations without the four
   new keys; `QuizConfiguration`'s defaults cover them on read, which the specs require
   explicitly.
3. Rollback: reversing the migration drops the `order` columns and the indexes and restores the
   previous unspecified ordering. Because no data outside those columns is touched and the new
   configuration keys are simply ignored by the prior code, a rollback loses only the authored
   positions — it cannot corrupt quizzes, questions, or responses.

## Open Questions

- Whether the delivery flow should resolve and freeze the full question sequence at attempt
  start (isolating in-progress attempts from authored-position edits) or recompute it per
  request from the frozen strategy. Both satisfy the specs as written; the choice depends on
  how that flow handles resumption and does not change anything in this change's tasks.
