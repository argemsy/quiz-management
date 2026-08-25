import time

import jwt

from src.shared.infrastructure.auth.session_claims import SessionClaims

JWT_ALGORITHM = "HS256"


class TokenExpiredError(Exception):
    pass


class TokenInvalidError(Exception):
    pass


class TokenService:
    """Encodes/decodes `SessionClaims` into a signed JWT. Generalizes what
    `src/shared/presentation/schema/auth.py::authorize` used to do inline
    for decoding only — this also encodes, so the account use cases
    (login, switch-tenant, refresh) and the auth middleware share one
    implementation instead of each calling `jwt.encode`/`jwt.decode`
    directly.
    """

    def __init__(self, secret_key: str, exp_minutes: int) -> None:
        self.secret_key = secret_key
        self.exp_minutes = exp_minutes

    def encode(self, claims: SessionClaims) -> str:
        payload = claims.model_dump(mode="json")
        payload["exp"] = int(time.time()) + self.exp_minutes * 60
        return jwt.encode(payload, self.secret_key, algorithm=JWT_ALGORITHM)

    def decode(self, token: str) -> SessionClaims:
        """Raises `TokenExpiredError`/`TokenInvalidError` rather than
        returning None — unlike the old `authorize()`, the caller needs to
        distinguish "no session" from "expired" from "tampered" (the
        middleware treats the first as anonymous, refresh treats the
        latter two as an outright rejection per
        specs/account/auth-session/spec.md).
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError() from exc
        except jwt.InvalidTokenError as exc:
            raise TokenInvalidError(str(exc)) from exc

        payload.pop("exp", None)
        return SessionClaims.model_validate(payload)
