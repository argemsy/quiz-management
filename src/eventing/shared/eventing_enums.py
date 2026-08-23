from src.shared.domain.enums import EnumChoices


class FailedEventStatus(EnumChoices):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    ABANDONED = "ABANDONED"


class IdempotencyKeyStatus(EnumChoices):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED_TERMINAL = "FAILED_TERMINAL"


class AuditLogContentTypeEnum(EnumChoices):
    """Every model, across bounded contexts, that AuditLog can record changes for."""

    TENANT = "TENANT"
    TENANT_USER = "TENANT_USER"
    USER = "USER"
    QUIZ = "QUIZ"
    QUESTION = "QUESTION"
    ANSWER_CHOICE = "ANSWER_CHOICE"
    QUIZ_FORM = "QUIZ_FORM"
    QUIZ_QUESTION_RESPONSE = "QUIZ_QUESTION_RESPONSE"
    QUIZ_USER_RESULT = "QUIZ_USER_RESULT"
    QUIZ_USER_RESULT_HISTORY = "QUIZ_USER_RESULT_HISTORY"


class AuditLogActionEnum(EnumChoices):
    ADDITION = "ADDITION"
    CHANGE = "CHANGE"
    DELETION = "DELETION"


class AuditLogSourceEnum(EnumChoices):
    API = "API"  # API REST - GRAPHQL - ETC
    ADMIN = "ADMIN"  # Django Admin
    COMMAND = "COMMAND"  # Django management command
    MIGRATION = "MIGRATION"
