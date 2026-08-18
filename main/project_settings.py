from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, model_validator

from src.shared.infrastructure.logging import get_logger

logger = get_logger("QuizManagement Settings")

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


class _GroupSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

class SecuritySettings(_GroupSettings):
    secret_key: SecretStr = Field(
        default=SecretStr("*"), validation_alias="SECRET_KEY"
    )
    jwt_secret_key: SecretStr = Field(
        default=SecretStr("insecure-jwt-secret-key"),
        validation_alias="JWT_SECRET_KEY",
    )

class DatabaseSettings(_GroupSettings):
    url: SecretStr = Field(
        default=SecretStr("sqlite:///db.sqlite3"),
        validation_alias="DATABASE_URL",
    )
    conn_max_age: int = Field(default=60, validation_alias="DB_CONN_MAX_AGE")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ENVIRONMENT: str = Field(default="local")
    DATABASE: DatabaseSettings = Field(default_factory=DatabaseSettings)
    SECURITY: SecuritySettings = Field(default_factory=SecuritySettings)



    @model_validator(mode="after")
    def _reject_placeholder_secret_outside_local(self) -> "Settings":
        """Fail fast if SECRET_KEY is still the insecure placeholder outside local/qa."""
        if (
            self.ENVIRONMENT not in {"local", "qa"}
            and self.SECURITY.secret_key.get_secret_value() == "*"
        ):
            raise ValueError(
                "SECRET_KEY is still the insecure placeholder '*' for "
                f"ENVIRONMENT={self.ENVIRONMENT!r}. Set a real value."
            )
        return self


settings = Settings()
logger.debug("settings_loaded", environment=settings.ENVIRONMENT)