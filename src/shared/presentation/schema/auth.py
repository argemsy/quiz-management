# Third-party Libraries
from typing import Optional

import jwt

from main.project_settings import settings
from src.shared.infrastructure.logging import get_logger

# Own Libraries
from src.shared.presentation.schema.types import UserSession

logger = get_logger(__name__)

JWT_ALGORITHMS = ["HS256"]


def authorize(authorization_header: str) -> Optional[UserSession]:
    if not authorization_header:
        return None

    bearer, jwt_encode = authorization_header.split(" ")
    logger.debug("authorization_header", bearer=bearer, token=jwt_encode)

    try:
        if bearer == "Bearer" and jwt_encode:
            jwt_decode = jwt.decode(
                jwt_encode,
                settings.SECURITY.jwt_secret_key.get_secret_value(),
                algorithms=JWT_ALGORITHMS,
            )

            logger.debug("jwt_decode: %s", jwt_decode)

            session_type = jwt_decode["session_type"]
            session_key = jwt_decode["session_key"]
            session_data = jwt_decode["session_data"]
            session_permissions = jwt_decode["session_permissions"]
            application_roles = jwt_decode.get("application_roles", [])
            feature_flags = jwt_decode.get("feature_flags", None)

            return UserSession(
                session_data=session_data,
                session_type=session_type,
                session_key=session_key,
                session_permissions=session_permissions,
                application_roles=application_roles,
                feature_flags=feature_flags,
            )
    except KeyError as exp:
        logger.error("KeyError in jwt_decode", exception=str(exp))
        return None
    except jwt.DecodeError as exp:
        logger.error("JWT DecodeError", exception=str(exp))
        return None
