from src.shared.domain.exceptions import ApplicationError, NotFoundError


class InvalidCredentialsError(ApplicationError):
    """Email/password did not authenticate. Deliberately doesn't say which
    part was wrong — don't leak whether an email exists."""

    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class MembershipNotFoundError(NotFoundError):
    def __init__(self, tenant_id) -> None:
        super().__init__(f"No active membership found for tenant {tenant_id}")
        self.tenant_id = tenant_id


class TenantRequiredError(ApplicationError):
    """Raised when a non-staff user attempts to log in without a
    `tenant_id` — per specs/account/auth-session/spec.md, a session
    represents identity plus, unless the user is staff-only, one active
    tenant membership; a non-staff user has no meaning without one."""

    def __init__(self) -> None:
        super().__init__("tenant_id is required for a non-staff login")


class InvalidSessionError(ApplicationError):
    """Raised by refresh when the token's identity/signature itself is no
    longer valid (expired, tampered, or the user no longer exists) — distinct
    from a stale-but-otherwise-valid session, which is not an error at the
    domain layer (see `SessionStaleError`)."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Session is invalid: {reason}")


class SessionStaleError(ApplicationError):
    """Raised when a session's permission-version no longer matches the
    current one. Not a rejection of the request — the caller (middleware)
    maps this to the `SESSION_STALE` signal from
    specs/account/auth-session/spec.md, prompting a refresh rather than a
    login."""

    def __init__(self) -> None:
        super().__init__("Session permissions are stale")
