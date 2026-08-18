import strawberry

from src.quiz.application.create_quiz_use_case.dto import (
    CreateQuizDTO,
)
from src.quiz.application.create_quiz_use_case.use_case import CreateQuizUseCase
from quiz.application.create_quiz_use_case.quiz_service import QuizService
from quiz.application.create_quiz_use_case.tenant_validation_service import (
    TenantValidationService,
)
from src.quiz.infrastructure.repositories.quiz_repository_imp import QuizRepositoryImpl
from src.quiz.infrastructure.repositories.tenant_lookup_repository_imp import (
    TenantLookupRepositoryImpl,
)
from src.quiz.presentation.schema.inputs.create_quiz_input import CreateQuizInput
from src.quiz.presentation.schema.responses.create_quiz_response import (
    CreateQuizPayload,
    CreateQuizResponse,
)
from src.quiz.presentation.schema.types.quiz_type import QuizType
from src.shared.infrastructure.event_bus import get_event_bus
from src.shared.presentation.schema.context import Info
from src.shared.presentation.schema.permissions import IsStaff
from src.shared.presentation.decorators import handle_mutations_exceptions


@strawberry.type
class QuizAdminMutation:

    @strawberry.mutation(permission_classes=[IsStaff])
    @handle_mutations_exceptions
    async def create_quiz(
        self, info: Info, input: CreateQuizInput
    ) -> CreateQuizResponse:
        operation_id = info.context.operation_id
        input_kwargs = strawberry.asdict(input)
        dto = CreateQuizDTO.model_validate(input_kwargs)
        use_case = CreateQuizUseCase(
            QuizService(QuizRepositoryImpl()),
            TenantValidationService(TenantLookupRepositoryImpl()),
            get_event_bus(),
        )
        quiz_entity = await use_case.execute(dto, operation_id)

        return CreateQuizPayload(
            operation_id=operation_id,
            payload=QuizType(value=quiz_entity),
        )
