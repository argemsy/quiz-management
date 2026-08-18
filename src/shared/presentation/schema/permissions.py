from typing import Any, Optional

import strawberry
from strawberry.permission import BasePermission

from src.shared.domain.enums import EnumChoices
from src.shared.presentation.schema.context import Info
from src.shared.presentation.schema.types import UserSession


class SessionPermissionEnum(EnumChoices):
    IS_AUTHENTICATED = "IS_AUTHENTICATED"
    IS_STAFF = "IS_STAFF"
    IS_ADMIN = "IS_ADMIN"
    IS_COLLABORATOR = "IS_COLLABORATOR"


def session_is_valid(user_session: Optional[UserSession] = None) -> bool:
    """This function will validate the minimum required params for
    this session object to be valid
    """
    if (
        not user_session
        or not user_session.session_permissions
        or user_session.session_data is None
    ):
        return False

    return True


def validate_permissions(
    session: Optional[UserSession],
    must: Optional[list[SessionPermissionEnum]] = None,
    at_least_one: Optional[list[SessionPermissionEnum]] = None,
) -> bool:
    """This function will validate that:
    - Session_object is valid
    - All permissions in the `must` parameter exists
    - At least one of the permissions in `at_least_one` exists

    Args:
        session: session_object
        must: list of permissions that need to be present
        at_least_one: at least one of this permissions need to be present

    Returns:

    """
    must = must or []
    at_least_one = at_least_one or []

    if not session_is_valid(session):
        return False

    session_perms = session.session_permissions or []  # type: ignore

    # Validating obligatory permissions
    for perm in must:
        perm_value = perm.value if isinstance(perm, SessionPermissionEnum) else perm
        if perm_value not in session_perms:
            return False

    # All obligatory permissions are present!
    if not at_least_one:
        return True

    # Validating "OR" permissions
    for perm in at_least_one:
        perm_value = perm.value if isinstance(perm, SessionPermissionEnum) else perm
        if perm_value in session_perms:
            return True
    else:
        # None of the "OR" permissions are present
        return False


class IsAuthenticated(BasePermission):
    message = "AuthenticationError: User is not authenticated"
    must = [SessionPermissionEnum.IS_AUTHENTICATED]

    # This method can also be async!
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user_session = info.context.user_session
        return validate_permissions(user_session, self.must)


class IsAdmin(BasePermission):
    message = "AuthenticationError: User does not have 'Admin' Role"
    must = [
        SessionPermissionEnum.IS_AUTHENTICATED,
        SessionPermissionEnum.IS_ADMIN,
    ]

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user_session = info.context.user_session
        return validate_permissions(user_session, self.must)


class IsStaff(BasePermission):
    message = "AuthenticationError: User does not have 'Staff' Role"
    must = [
        SessionPermissionEnum.IS_AUTHENTICATED,
    ]
    at_least_one = [
        SessionPermissionEnum.IS_ADMIN,
        SessionPermissionEnum.IS_STAFF,
    ]

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user_session = info.context.user_session
        return validate_permissions(user_session, self.must, self.at_least_one)


class IsOrganizationUser(BasePermission):
    message = "AuthenticationError: User does not have 'OrganizationUser' or 'OrganizationAdmin' Role"

    must = [
        SessionPermissionEnum.IS_AUTHENTICATED,
    ]
    at_least_one = [
        SessionPermissionEnum.IS_ADMIN,
        SessionPermissionEnum.IS_COLLABORATOR,
    ]

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user_session = info.context.user_session
        return validate_permissions(user_session, self.must, self.at_least_one)
