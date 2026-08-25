## 1. QuizQuestionResponse — response cardinality per response type

- [x] 1.1 Add `response_type` field to `QuizQuestionResponse` (`CharField`, `choices=QuestionResponseTypeEnum.choices()`, `editable=False`), documented as a snapshot of `Question.response_type` at creation time.
- [x] 1.2 Replace `uq_question_response_form_question` with `uq_response_single_definition_one_row` (`quiz_form`, `question`; condition `response_type__in=["SINGLE", "DEFINITION"]`) and `uq_response_multiple_per_choice` (`quiz_form`, `question`, `answer_choice`; condition `response_type="MULTIPLE"`, `answer_choice__isnull=False`).
- [x] 1.3 Leave `ck_response_exactly_one_answer` and `idx_question_response_form` unchanged.

## 2. QuizUserResult / QuizUserResultHistory — tenant-null-safe, quiz-scoped uniqueness

- [x] 2.1 Replace `QuizUserResult.uq_quiz_user_result_tenant_user_quiz` with `uq_quiz_user_result_user_tenant_user_quiz` (`user`, `tenant_user`, `quiz`; condition `tenant_user__isnull=False`) and `uq_quiz_user_result_user_quiz_no_tenant` (`user`, `quiz`; condition `tenant_user__isnull=True`).
- [x] 2.2 Replace `QuizUserResultHistory.uq_result_history_tenant_user_attempt` with `uq_result_history_user_tenant_user_quiz_attempt` (`user`, `tenant_user`, `quiz`, `attempt_number`; condition `tenant_user__isnull=False`) and `uq_result_history_user_quiz_attempt_no_tenant` (`user`, `quiz`, `attempt_number`; condition `tenant_user__isnull=True`).
- [x] 2.3 Leave existing indexes on both models unchanged.

## 3. Migrations and verification

- [x] 3.1 Run `makemigrations` for `quiz` (no prior migration exists yet — this produces the first one, already correct).
- [x] 3.2 Run `manage.py check` and `migrate` against local sqlite to confirm the constraints apply cleanly.
- [x] 3.3 Add/extend model-level tests (or a scratch shell check) exercising each rejected scenario from `specs/quiz/question-response/spec.md` and `specs/quiz/attempt-result/spec.md`: duplicate SINGLE/DEFINITION response, duplicate MULTIPLE choice, duplicate current result for an unaffiliated user, colliding attempt numbers across two different quizzes.

## 4. Documentation

- [x] 4.1 Amend `openspec/adrs/ADR-004-separate-current-quiz-result-from-historical-results.md`: the stated uniqueness tuple for `QuizUserResultHistory` was missing `quiz`; update the "Decision" section to match `uq_result_history_user_tenant_user_quiz_attempt` / `uq_result_history_user_quiz_attempt_no_tenant`.
- [x] 4.2 Write a new ADR documenting the response-cardinality-per-response-type rule (capability `quiz/question-response`) and the `response_type` snapshot decision, referencing ADR-002 and ADR-006 as precedent. → `ADR-008-response-cardinality-by-question-response-type.md`
- [x] 4.3 Write a new ADR documenting the two-tier tenant-scoping rule (admin-configured models always carry explicit `tenant`/`tenant_user`; user-interaction models carry `user` always and `tenant_user` only when affiliated) and the `tenant_user.tenant_id == quiz.tenant_id` invariant (capability `quiz/tenant-scoping`), referencing ADR-001 as precedent for why the check is application-layer only. → `ADR-009-tenant-scoping-for-user-interaction-models.md`

## 5. Follow-up not covered by this change

- [x] 5.1 Note (no action here): the `tenant_user.tenant_id == quiz.tenant_id` check and the `response_type` snapshot-on-create must be implemented in the `QuizForm`/`QuizQuestionResponse` creation use cases once those exist in `src/quiz/application/` — out of scope until that application layer is built.
