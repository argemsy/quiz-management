import strawberry


@strawberry.input
class QuizAnswerChoiceInput:
    text: str
    is_correct: bool
