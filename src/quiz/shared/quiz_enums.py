from src.shared.domain.enums import EnumChoices


class QuizTypeEnum(EnumChoices):
    FINAL_ASSESSMENT = "FINAL_ASSESSMENT"
    KNOWLEDGE_CHECK = "KNOWLEDGE_CHECK"
    PRACTICE = "PRACTICE"


class QuestionResponseTypeEnum(EnumChoices):
    SINGLE = "SINGLE"
    MULTIPLE = "MULTIPLE"
    DEFINITION = "DEFINITION"


class OrderStrategyEnum(EnumChoices):
    """How a quiz presents its questions and answer choices to a taker.

    One enum serves both `QuizConfiguration.question_order` and
    `.answer_order`: the two answer the same question about different
    collections, and splitting them would duplicate the members without
    ever letting them diverge.
    """

    AS_AUTHORED = "AS_AUTHORED"
    RANDOM = "RANDOM"


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
