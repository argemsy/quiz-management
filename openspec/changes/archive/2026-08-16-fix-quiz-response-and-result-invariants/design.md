## Context

See `proposal.md` for motivation. Relevant current state: `src/quiz/infrastructure/persistence/django/models/quiz_question_response.py` and `quiz_user_result.py` (models `QuizUserResult` + `QuizUserResultHistory`) have no migrations generated yet. `ADR-001` already established the precedent this design leans on twice: an invariant that spans two tables (e.g. `Question.tenant_id == Quiz.tenant_id`) cannot be expressed as a single-table Django `CheckConstraint`/`UniqueConstraint` — Postgres constraints only see the row being written (or, for `UNIQUE`, other rows in the same table on the indexed columns). `ADR-006` already established the fix for that class of problem where the value that must be compared is a business fact worth freezing at write time: snapshot it onto the row itself.

## Goals / Non-Goals

**Goals:**
- Make the three uniqueness/cardinality gaps DB-enforced wherever a single-table constraint can express them.
- Document, as an explicit invariant, the one case that genuinely cannot be DB-enforced (`QuizForm.tenant_user.tenant_id == QuizForm.quiz.tenant_id`) so it is not silently forgotten once use cases are written.

**Non-Goals:**
- Implementing the `QuizForm`/`QuizQuestionResponse` creation use cases themselves — they do not exist yet in `src/quiz/application/`. This change only fixes the models these future use cases will write to, and records the validation those use cases must perform.
- Revisiting `Question`/`AnswerChoice`/`Quiz` — out of scope, no gaps found there.
- Introducing DB triggers, composite foreign keys, or row-level security — ADR-001 already ruled these out as non-goals for this project; this design stays consistent with that.

## Decisions

### 1. Snapshot `response_type` onto `QuizQuestionResponse`, then use partial unique constraints for cardinality

Considered leaving cardinality enforcement entirely in the application layer (the option floated first in review). Rejected: it requires every write path to remember and re-derive `Question.response_type` correctly, forever, with no backstop — the exact class of risk ADR-002 already rejected ("Application-level checks... are insufficient as the only protection... two concurrent requests can both observe that a question does not exist"). Denormalizing `response_type` onto the response row converts the check from cross-table to single-table, so Postgres can own it:

```python
response_type = models.CharField(
    max_length=20,
    choices=QuestionResponseTypeEnum.choices(),
    editable=False,
    help_text="Snapshot of Question.response_type at the time this response was recorded.",
)

class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=("quiz_form", "question"),
            condition=models.Q(response_type__in=["SINGLE", "DEFINITION"]),
            name="uq_response_single_definition_one_row",
        ),
        models.UniqueConstraint(
            fields=("quiz_form", "question", "answer_choice"),
            condition=models.Q(response_type="MULTIPLE", answer_choice__isnull=False),
            name="uq_response_multiple_per_choice",
        ),
        models.CheckConstraint(  # unchanged
            condition=(
                models.Q(answer_choice__isnull=False, definition__isnull=True)
                | models.Q(answer_choice__isnull=True, definition__isnull=False)
            ),
            name="ck_response_exactly_one_answer",
        ),
    ]
```

The single remaining trust requirement — that `response_type` is copied correctly at creation — is the same shape of write-time responsibility ADR-006 already accepted for `quiz_configuration_snapshot`, not a new kind of risk.

### 2. Split `QuizUserResult`/`QuizUserResultHistory` uniqueness on `tenant_user IS NULL`

Considered keeping a single `UniqueConstraint` including the nullable `tenant_user` column. Rejected: SQL unique constraints treat `NULL != NULL`, so rows where `tenant_user IS NULL` are never compared against each other and the constraint silently stops protecting unaffiliated users — exactly the "street survey" case confirmed as a real, supported scenario. Splitting into two partial constraints (one scoped `tenant_user IS NOT NULL`, one scoped `tenant_user IS NULL` and omitting the column) closes the gap for both cases:

```python
# QuizUserResult.Meta.constraints
models.UniqueConstraint(
    fields=("user", "tenant_user", "quiz"),
    condition=models.Q(tenant_user__isnull=False),
    name="uq_quiz_user_result_user_tenant_user_quiz",
),
models.UniqueConstraint(
    fields=("user", "quiz"),
    condition=models.Q(tenant_user__isnull=True),
    name="uq_quiz_user_result_user_quiz_no_tenant",
),
```

```python
# QuizUserResultHistory.Meta.constraints — same split, plus `quiz` added to the tuple
models.UniqueConstraint(
    fields=("user", "tenant_user", "quiz", "attempt_number"),
    condition=models.Q(tenant_user__isnull=False),
    name="uq_result_history_user_tenant_user_quiz_attempt",
),
models.UniqueConstraint(
    fields=("user", "quiz", "attempt_number"),
    condition=models.Q(tenant_user__isnull=True),
    name="uq_result_history_user_quiz_attempt_no_tenant",
),
```

`quiz` is added to the history tuple because `attempt_number` resets per quiz (confirmed against the flow described in ADR-004: "Attempt 1 → QuizForm #1"); without it, attempt 1 of one quiz collides with attempt 1 of any other quiz for the same user.

### 3. `tenant_user.tenant_id == quiz.tenant_id` stays a documented, application-layer invariant

Same reasoning as ADR-001's `Question.tenant_id == Quiz.tenant_id`: this compares a value on `TenantUser` (via `QuizForm.tenant_user`) against a value on `Quiz` (via `QuizForm.quiz`) — two tables neither of which is `QuizForm` itself, so no single-table constraint can express it, and denormalizing a whole `tenant_id` onto `QuizForm` was already decided against for the interaction models (see the admin-config vs. user-interaction tenant-scoping rule, to be written up as its own ADR — `tenant_user` alone is sufficient there by design). This must be validated by whichever use case creates a `QuizForm`, before the row is written.

## Risks / Trade-offs

- **[Risk]** A write path that bypasses the future use case layer (bulk import, a fixed-in-a-hurry admin action, raw SQL) could write an incorrect `response_type` snapshot or an out-of-tenant `QuizForm` and neither would be caught by the DB. → **Mitigation**: keep both checks centralized in one place each (a single "create response" and a single "create quiz form" entry point) once those use cases are written; note this explicitly in their eventual docstrings, same convention ADR-001 already uses for `Question.clean()`.
- **[Risk]** Two new ADRs and one amendment add documentation overhead. → **Mitigation**: scoped to exactly the three decisions made in this change; no speculative content.

## Migration Plan

No migrations exist yet for `quiz`. Applying the model edits (tasks below) and then running `makemigrations` produces a single, correct initial migration — there is no prior migration to correct or backfill.

## Open Questions

None — the four corrections were confirmed with the user during review; nothing here is deferred.
