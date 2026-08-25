## 1. Domain: enums and configuration

- [x] 1.1 Add `OrderStrategyEnum(EnumChoices)` with `AS_AUTHORED` / `RANDOM` to `src/quiz/shared/quiz_enums.py` — one enum reused by both configuration fields, not two parallel enums
- [x] 1.2 `QuizConfiguration` (`src/quiz/domain/entities/quiz_entity.py`) gains `question_order` and `answer_order`, both `OrderStrategyEnum = AS_AUTHORED`
- [x] 1.3 `QuizConfiguration` gains `min_questions_allowed: int = 1` and `max_answers_allowed: int = 5`; `total_questions_allowed` is **not** renamed or otherwise touched (design.md - Decisions)
- [x] 1.4 `QuizConfiguration.__post_init__` adds the coherence checks alongside the existing two: `min_questions_allowed > 0`, `min_questions_allowed <= total_questions_allowed`, `max_answers_allowed > 0`
- [x] 1.5 `QuizConfiguration.__post_init__` coerces `question_order`/`answer_order` from `str` to `OrderStrategyEnum` — required because `QuizEntity._build_configuration` calls `QuizConfiguration(**data)` on raw JSON. The dataclass is `frozen=True`, so the coercion must go through `object.__setattr__`
- [x] 1.6 `QuizConfiguration.to_primitive()` emits all four new fields, with `.value` for the two enums
- [x] 1.7 Verify no JSONField data migration is needed: a stored configuration lacking the four new keys must hydrate to the defaults via `QuizConfiguration(**data)` without raising

## 2. Domain: entities, exceptions, pure rules

- [x] 2.1 Add `order: int = 0` to `QuestionEntity` and `AnswerChoiceEntity` (`src/quiz/domain/entities/question_entity.py`)
- [x] 2.2 Add `QuestionLimitExceededError(DomainError)` and `AnswerChoiceLimitExceededError(DomainError)` to `src/quiz/domain/exceptions.py`, alongside `InvalidQuestionError` — `DomainError` subclasses so `@handle_mutations_exceptions` maps them to `ValidationErrorResponse`, not `InternalErrorResponse`
- [x] 2.3 Create `src/quiz/domain/ordering.py` — pure, no I/O, no Django import: `resolve_question_order(questions, strategy, quiz_form_id)` and `resolve_answer_order(choices, strategy, quiz_form_id, question_id)`. `AS_AUTHORED` sorts by `(order, created_at)`-equivalent; `RANDOM` shuffles a copy via `random.Random(seed)`
- [x] 2.4 Build the `RANDOM` seed from the identifiers as a string passed directly to `random.Random(...)`. **Never via `hash()`** — `PYTHONHASHSEED` randomizes `str` hashing per process and would break the reload-stability and audit-reproducibility requirements (design.md - Decisions)
- [x] 2.5 Create `src/quiz/domain/composition.py` — pure, no I/O: `validate_composition(configuration, questions)` raising the two new errors, and `is_publishable(active_question_count, configuration) -> bool`
- [x] 2.6 `validate_composition` must pass at exactly the limit and fail at limit + 1, for both the question count and each question's answer-choice count

## 3. Domain: repository port

- [x] 3.1 Add `count_active_questions(quiz_id: uuid.UUID) -> int` to the `QuizRepository` ABC (`src/quiz/domain/repositories/quiz_repository.py`), `async def` per the project's port convention

## 4. Infrastructure: models and migration

- [x] 4.1 Add `order = models.PositiveIntegerField(default=0, ...)` to `QuestionModel` and `AnswerChoiceModel`
- [x] 4.2 Add `Meta.ordering = ("order", "created_at")` to both models — the `created_at` tie-break is what makes the order total; do not omit it
- [x] 4.3 Add indexes on `(quiz, order)` and `(question, order)` respectively. Add **no** `UniqueConstraint` on `order` (design.md - Decisions: Django forbids `condition` + `deferrable`)
- [x] 4.4 Generate migration `0003_*` and hand-edit it to carry the data step: renumber existing questions to a dense `1..N` per quiz and existing answer choices to `1..N` per question, ordered by `created_at`
- [x] 4.5 The data step accumulates instances and calls `bulk_update()` **once per table** — no `.save()` in a loop (mandatory pattern #1)
- [x] 4.6 `QuizRepositoryImpl.count_active_questions` (`src/quiz/infrastructure/repositories/quiz_repository_imp.py`), sync `def` with `@async_database()`, filtering `is_active=True, is_deleted=False`
- [x] 4.7 `QuestionRepositoryImpl.bulk_create` (`question_repository_imp.py`) persists `question.order` and `choice.order`; the two `bulk_create` calls stay exactly two — no new queries
- [x] 4.8 `QuestionRepositoryImpl.bulk_create`'s return mapping carries `order` back onto the returned entities

## 5. Application

- [x] 5.1 `CreateQuestionsUseCase.execute` (`src/quiz/application/create_questions_use_case/use_case.py`) assigns `order` via `enumerate(dto.questions, start=1)` and `enumerate(question.answer_choices, start=1)` — density `1..N` originates here
- [x] 5.2 `CreateQuizUseCase._validate_questions` also calls `validate_composition(configuration, dto.questions)`, keeping its existing entity-invariant loop. It must still run **before** `tenant_validation` and before any write
- [x] 5.3 Confirm `QuestionDTO` / `AnswerChoiceDTO` are unchanged — order is positional and does not travel as a field

## 6. Presentation: GraphQL

- [x] 6.1 Add the strawberry enum for `OrderStrategyEnum` in `src/quiz/presentation/schema/quiz_enums.py`, following the `StrawberryQuizTypeEnum` pattern
- [x] 6.2 `QuizConfigurationInput` (`src/quiz/presentation/schema/inputs/quiz_input.py`) gains `question_order`, `answer_order`, `min_questions_allowed`, `max_answers_allowed`, each with a default matching `QuizConfiguration` — additive only, so existing clients keep working unchanged
- [x] 6.3 Verify the `create_quiz` resolver needs no change: `strawberry.asdict(input)` already flattens the configuration into `CreateQuizDTO.configuration`

## 7. Presentation: Django admin

- [x] 7.1 `QuestionAdmin`: `order` in `list_display` (not first — the first column is the change link), `list_editable = ("order",)`, `ordering = ("quiz", "order")`
- [x] 7.2 `AnswerChoiceAdmin`: same treatment, `ordering = ("question", "order")`
- [x] 7.3 Add `AnswerChoiceInline` (`TabularInline`, `extra=0`) to `QuestionAdmin` and `QuestionInline` to `QuizAdmin`
- [x] 7.4 Both inlines override `save_formset` to propagate `tenant`/`tenant_user` from the parent object — both fields are `editable=False` and NOT NULL, so an insert from an inline fails with `IntegrityError` otherwise
- [x] 7.5 `QuizAdmin` shows a derived `is_publishable` column, resolved through `get_queryset().annotate(Count("questions", filter=Q(is_active=True, is_deleted=False)))` — **never** a per-row count, which would be an N+1 across the changelist

## 8. Tests

- [x] 8.1 `tests/quiz/domain/test_ordering.py`: `AS_AUTHORED` returns authored order; `RANDOM` with the same attempt id returns an identical sequence twice; two different attempt ids are resolved independently; each question's answer order is independent of iteration order
- [x] 8.2 Reproducibility across processes: assert the `RANDOM` sequence for a fixed id matches a hardcoded expected sequence, so a regression to `hash()`-derived seeding fails the suite under a different `PYTHONHASHSEED`
- [x] 8.3 `tests/quiz/domain/test_composition.py`: `validate_composition` passes at the limit, raises `QuestionLimitExceededError` at limit + 1 questions, raises `AnswerChoiceLimitExceededError` at limit + 1 choices; `is_publishable` is true at exactly the minimum and false below it
- [x] 8.4 `tests/quiz/domain/test_quiz_entity.py`: `QuizConfiguration` rejects `min_questions_allowed > total_questions_allowed`, `min_questions_allowed <= 0`, and `max_answers_allowed <= 0`; `to_primitive()` → `_build_configuration()` round-trips the enums; a legacy dict without the four new keys hydrates to defaults
- [x] 8.5 Infrastructure test: `bulk_create` assigns `1..N` to questions and choices, and a re-read returns them in that order
- [x] 8.6 Infrastructure test: `count_active_questions` excludes soft-deleted and inactive questions
- [x] 8.7 Presentation test: `create_quiz` with too many questions, and with a question having too many answer choices, each returns `ValidationErrorResponse` (not `InternalErrorResponse`) and creates no `Quiz` row
- [x] 8.8 Update `tests/fixtures/quiz_fixtures.py` so `make_question` / `make_answer_choice` set a sensible default `order`
- [x] 8.9 ~~Refresh the schema snapshot~~ — **not needed, assumption was wrong**: `test_create_quiz_snapshot.py` pins the create_quiz *response* shape, not the schema SDL, and the response carries no configuration. It passes unchanged. Coverage of the new input fields comes from `test_create_quiz_composition_limits.py` instead

## 9. Verification

- [x] 9.1 `make lint` — black/isort clean. flake8 still reports 24 pre-existing errors (E501 in `0001_initial` migrations, `F401` in the three `apps.py` files, `schema.py:37`), verified against a clean stash to be untouched by this change. No new violations introduced; the target failed before this work too
- [x] 9.2 `make test` green, coverage of `src/` not below its current 94%
- [x] 9.3 Migration verified against a real database: rolled back to `0002`, seeded questions and choices through raw SQL (the `order` column does not exist at that point, so the ORM cannot be used), migrated forward. Rows were seeded with names deliberately out of alphabetical order and ascending `created_at` — the result renumbered `zeta/alpha/mid` to `1/2/3` by creation time, dense per group, confirming the ordering key is `created_at` and not id or insertion order. Seed data removed afterwards
- [ ] 9.4 End-to-end via GraphQL on `:8500` with `X-Correlation-ID` and `X-Operation-ID`, reusing `tests/graphql/mutations/create_quiz.graphql`: create a quiz with 3 questions of 4 choices each and confirm the persisted `order` values follow the submitted sequence
- [ ] 9.5 In the Django admin on `:8000`, reorder questions from the `QuizAdmin` inline, save, and confirm the list re-reads in the new order; soft-delete questions until the quiz falls below its minimum and confirm the `is_publishable` column flips
