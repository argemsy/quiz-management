## Why

A modeling review of `src/quiz` (done before any migration was ever applied — the schema is still fully open to change) found three data-integrity gaps that the current Django models cannot catch: `QuizQuestionResponse` has no way to represent a `MULTIPLE`-choice answer, and the uniqueness constraints on `QuizUserResult`/`QuizUserResultHistory` silently stop working for users with no `tenant_user` (SQL treats `NULL != NULL`) and don't scope attempt numbers per quiz. A fourth gap — no enforced link between a `QuizForm`'s optional `tenant_user` and the tenant that owns the `Quiz` being answered — was also identified. Fixing these now, before the first migration, avoids a backfill/migration later.

## What Changes

- `QuizQuestionResponse` gains a denormalized `response_type` field, snapshotted from `Question.response_type` when the response row is created. Its single `UniqueConstraint(quiz_form, question)` is replaced by two partial constraints: one row max per `(quiz_form, question)` when `response_type` is `SINGLE`/`DEFINITION`, and one row per selected `answer_choice` (no duplicates) when `response_type` is `MULTIPLE`. This is what makes `MULTIPLE` answers representable at all — today they are not.
- `QuizUserResult.uq_quiz_user_result_tenant_user_quiz` (`user`, `tenant_user`, `quiz`) is replaced by two partial `UniqueConstraint`s split on `tenant_user IS NULL` / `IS NOT NULL`, so a user with no tenant affiliation is still capped at one current result per quiz.
- `QuizUserResultHistory.uq_result_history_tenant_user_attempt` (`user`, `tenant_user`, `attempt_number`) gains `quiz` in the tuple — `attempt_number` resets per quiz, so without `quiz` two different quizzes for the same user collide on `attempt_number=1` — and gets the same `tenant_user`-null split as `QuizUserResult`.
- New domain invariant (documented, enforced at the application layer — not DB-enforceable, same cross-table limitation already documented in ADR-001): when `QuizForm.tenant_user` is set, `QuizForm.tenant_user.tenant_id` must equal `QuizForm.quiz.tenant_id`.
- ADR-004 gets amended (its stated uniqueness rule was missing `quiz`); two new ADRs get added documenting the response-cardinality rule and the tenant-scoping invariant, since neither was written down anywhere before this review.

None of this is **BREAKING** in the data-migration sense — no migration has been generated or applied against these models yet.

## Capabilities

### New Capabilities
- `quiz/question-response`: recording rules for `QuizQuestionResponse` — cardinality per `Question.response_type` (`SINGLE`/`DEFINITION` → single row, `MULTIPLE` → multi-row, one per choice), enforced via a `response_type` snapshot plus partial DB constraints.
- `quiz/attempt-result`: uniqueness rules for `QuizUserResult` (current) and `QuizUserResultHistory` (append-only), correctly scoped for both tenant-affiliated and unaffiliated users, and scoped per quiz for attempt numbering.
- `quiz/tenant-scoping`: consistency invariant between a user-interaction record's optional `tenant_user` and the `tenant` that owns the `Quiz` being interacted with.

### Modified Capabilities
- (none — these are the first specs written for the `quiz` module)

## Impact

- Models: `src/quiz/infrastructure/persistence/django/models/quiz_question_response.py`, `src/quiz/infrastructure/persistence/django/models/quiz_user_result.py`.
- No migrations exist yet for `quiz`, so this reshapes the first migration rather than adding a corrective one.
- Docs: `openspec/adrs/ADR-004-...md` (amend), two new ADRs (response cardinality, tenant scoping).
- No use cases/domain services exist yet for creating `QuizForm`/`QuizQuestionResponse` — the `tenant_user.tenant_id == quiz.tenant_id` check and the `response_type`-snapshot-on-create logic are noted as required behavior for whichever use case eventually creates these rows, since they can't be written into non-existent application code today.
