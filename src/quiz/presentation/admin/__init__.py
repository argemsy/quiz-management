from src.quiz.presentation.admin.answer_choice import AnswerChoiceAdmin  # noqa: F401
from src.quiz.presentation.admin.area import AreaAdmin  # noqa: F401
from src.quiz.presentation.admin.question import QuestionAdmin  # noqa: F401
from src.quiz.presentation.admin.quiz import QuizAdmin  # noqa: F401
from src.quiz.presentation.admin.quiz_area import QuizAreaAdmin  # noqa: F401
from src.quiz.presentation.admin.quiz_form import QuizFormAdmin  # noqa: F401
from src.quiz.presentation.admin.quiz_question_response import (  # noqa: F401
    QuizQuestionResponseAdmin,
)
from src.quiz.presentation.admin.quiz_user_result import (  # noqa: F401
    QuizUserResultAdmin,
    QuizUserResultHistoryAdmin,
)

__all__ = [
    "QuizAdmin",
    "QuestionAdmin",
    "AnswerChoiceAdmin",
    "AreaAdmin",
    "QuizAreaAdmin",
    "QuizFormAdmin",
    "QuizQuestionResponseAdmin",
    "QuizUserResultAdmin",
    "QuizUserResultHistoryAdmin",
]
