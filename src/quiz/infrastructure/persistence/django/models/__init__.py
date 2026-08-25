from src.quiz.infrastructure.persistence.django.models.answer_choice import (
    AnswerChoice as AnswerChoiceModel,
)
from src.quiz.infrastructure.persistence.django.models.area import Area as AreaModel
from src.quiz.infrastructure.persistence.django.models.question import (
    Question as QuestionModel,
)
from src.quiz.infrastructure.persistence.django.models.quiz import Quiz as QuizModel
from src.quiz.infrastructure.persistence.django.models.quiz_form import (
    QuizForm as QuizFormModel,
)
from src.quiz.infrastructure.persistence.django.models.quiz_area import (
    QuizArea as QuizAreaModel,
)
from src.quiz.infrastructure.persistence.django.models.quiz_question_response import (
    QuizQuestionResponse as QuizQuestionResponseModel,
)
from src.quiz.infrastructure.persistence.django.models.quiz_user_result import (
    QuizUserResult as QuizUserResultModel,
)
from src.quiz.infrastructure.persistence.django.models.quiz_user_result import (
    QuizUserResultHistory as QuizUserResultHistoryModel,
)

__all__ = [
    "QuizModel",
    "QuestionModel",
    "AnswerChoiceModel",
    "AreaModel",
    "QuizAreaModel",
    "QuizFormModel",
    "QuizQuestionResponseModel",
    "QuizUserResultModel",
    "QuizUserResultHistoryModel",
]
