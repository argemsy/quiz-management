from main.project_settings import settings
from src.shared.infrastructure.auth.token_service import TokenService


def get_token_service() -> TokenService:
    return TokenService(
        secret_key=settings.SECURITY.jwt_secret_key.get_secret_value(),
        exp_minutes=settings.SECURITY.jwt_exp_minutes,
    )
