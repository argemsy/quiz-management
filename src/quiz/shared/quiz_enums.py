from src.shared.domain.enums import EnumChoices


class QuizTypeEnum(EnumChoices):
    FINAL_ASSESSMENT = "FINAL_ASSESSMENT"
    KNOWLEDGE_CHECK = "KNOWLEDGE_CHECK"
    PRACTICE = "PRACTICE"


class QuestionResponseTypeEnum(EnumChoices):
    SINGLE = "SINGLE"
    MULTIPLE = "MULTIPLE"
    DEFINITION = "DEFINITION"


class QuizFormStatusEnum(EnumChoices):
    """Represent the lifecycle status of a quiz form."""

    NOT_STARTED = "NOT_STARTED"
    OPEN = "OPEN"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class QuizResultStatusEnum(EnumChoices):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
