import pytest
from typing import Optional, List

from src.shared.presentation.schema.context import Info, Context
from src.shared.presentation.schema.permissions import (
    SessionPermissionEnum,
    IsAuthenticated,
    IsAdmin,
    IsStaff,
    IsOrganizationUser,
    validate_permissions,
    session_is_valid,
)
from src.shared.presentation.schema.types import UserSession


class MockRequest:
    """Mock HTTP request for testing."""

    def __init__(self):
        self.headers = {}


class MockContext:
    """Mock Context object that properly exposes user_session."""

    def __init__(self, user_session: Optional[UserSession] = None):
        self.request = MockRequest()
        self._user_session = user_session

    @property
    def user_session(self):
        return self._user_session


class MockInfo:
    """Mock Strawberry Info object for testing."""

    def __init__(self, user_session: Optional[UserSession] = None):
        self.context = MockContext(user_session)


# Fixtures

@pytest.fixture
def mock_info():
    """Create a basic mock Info without authentication."""
    return MockInfo(user_session=None)


@pytest.fixture
def authenticated_session():
    """Create a UserSession with only IS_AUTHENTICATED permission."""
    return UserSession(
        session_type="jwt",
        session_key="test-key",
        session_data={},
        session_permissions=[SessionPermissionEnum.IS_AUTHENTICATED.value],
        session_roles=["user"],
    )


@pytest.fixture
def collaborator_session():
    """Create a UserSession with IS_AUTHENTICATED and IS_COLLABORATOR."""
    return UserSession(
        session_type="jwt",
        session_key="test-key-collaborator",
        session_data={"user_id": "12345"},
        session_permissions=[
            SessionPermissionEnum.IS_AUTHENTICATED.value,
            SessionPermissionEnum.IS_COLLABORATOR.value,
        ],
        session_roles=["collaborator"],
    )


@pytest.fixture
def staff_session():
    """Create a UserSession with IS_AUTHENTICATED and IS_STAFF."""
    return UserSession(
        session_type="jwt",
        session_key="test-key-staff",
        session_data={"user_id": "67890"},
        session_permissions=[
            SessionPermissionEnum.IS_AUTHENTICATED.value,
            SessionPermissionEnum.IS_STAFF.value,
        ],
        session_roles=["staff"],
    )


@pytest.fixture
def admin_session():
    """Create a UserSession with IS_AUTHENTICATED and IS_ADMIN."""
    return UserSession(
        session_type="jwt",
        session_key="test-key-admin",
        session_data={"user_id": "admin-123"},
        session_permissions=[
            SessionPermissionEnum.IS_AUTHENTICATED.value,
            SessionPermissionEnum.IS_ADMIN.value,
        ],
        session_roles=["admin"],
    )


# Tests: session_is_valid()

class TestSessionIsValid:
    def test_none_session_is_invalid(self):
        assert session_is_valid(None) is False

    def test_session_without_permissions_is_invalid(self):
        session = UserSession(
            session_type="jwt",
            session_key="key",
            session_data={},
            session_permissions=None,
        )
        assert session_is_valid(session) is False

    def test_session_without_data_is_invalid(self):
        session = UserSession(
            session_type="jwt",
            session_key="key",
            session_data=None,  # type: ignore
            session_permissions=[SessionPermissionEnum.IS_AUTHENTICATED],
        )
        assert session_is_valid(session) is False

    def test_valid_session_is_valid(self, authenticated_session):
        assert session_is_valid(authenticated_session) is True


# Tests: validate_permissions()

class TestValidatePermissions:
    def test_unauthenticated_user_fails_all_checks(self):
        result = validate_permissions(
            None, must=[SessionPermissionEnum.IS_AUTHENTICATED]
        )
        assert result is False

    def test_authenticated_user_passes_authenticated_check(
        self, authenticated_session
    ):
        result = validate_permissions(
            authenticated_session, must=[SessionPermissionEnum.IS_AUTHENTICATED]
        )
        assert result is True

    def test_authenticated_user_fails_admin_check(self, authenticated_session):
        result = validate_permissions(
            authenticated_session,
            must=[
                SessionPermissionEnum.IS_AUTHENTICATED,
                SessionPermissionEnum.IS_ADMIN,
            ],
        )
        assert result is False

    def test_staff_fails_admin_check(self, staff_session):
        result = validate_permissions(
            staff_session,
            must=[
                SessionPermissionEnum.IS_AUTHENTICATED,
                SessionPermissionEnum.IS_ADMIN,
            ],
        )
        assert result is False

    def test_admin_passes_admin_check(self, admin_session):
        result = validate_permissions(
            admin_session,
            must=[
                SessionPermissionEnum.IS_AUTHENTICATED,
                SessionPermissionEnum.IS_ADMIN,
            ],
        )
        assert result is True

    def test_staff_passes_at_least_one_of_staff_or_admin(self, staff_session):
        result = validate_permissions(
            staff_session,
            must=[SessionPermissionEnum.IS_AUTHENTICATED],
            at_least_one=[
                SessionPermissionEnum.IS_STAFF,
                SessionPermissionEnum.IS_ADMIN,
            ],
        )
        assert result is True

    def test_collaborator_fails_at_least_one_of_staff_or_admin(
        self, collaborator_session
    ):
        result = validate_permissions(
            collaborator_session,
            must=[SessionPermissionEnum.IS_AUTHENTICATED],
            at_least_one=[
                SessionPermissionEnum.IS_STAFF,
                SessionPermissionEnum.IS_ADMIN,
            ],
        )
        assert result is False


# Tests: Permission Classes

class TestIsAuthenticatedPermission:
    def test_unauthenticated_user_denied(self, mock_info):
        permission = IsAuthenticated()
        assert permission.has_permission(None, mock_info) is False

    def test_authenticated_user_allowed(self, authenticated_session):
        info = MockInfo(user_session=authenticated_session)
        permission = IsAuthenticated()
        assert permission.has_permission(None, info) is True

    def test_collaborator_allowed(self, collaborator_session):
        info = MockInfo(user_session=collaborator_session)
        permission = IsAuthenticated()
        assert permission.has_permission(None, info) is True


class TestIsAdminPermission:
    """Admin: tenant admin. Staff > Admin > Collaborator hierarchy.

    Staff can access admin resources (staff is superior).
    Admin can only access admin resources (not staff).
    """
    def test_unauthenticated_user_denied(self, mock_info):
        permission = IsAdmin()
        assert permission.has_permission(None, mock_info) is False

    def test_authenticated_user_denied(self, authenticated_session):
        info = MockInfo(user_session=authenticated_session)
        permission = IsAdmin()
        assert permission.has_permission(None, info) is False

    def test_staff_user_allowed(self, staff_session):
        """Staff (system owner) CAN access admin resources."""
        info = MockInfo(user_session=staff_session)
        permission = IsAdmin()
        assert permission.has_permission(None, info) is True

    def test_admin_user_allowed(self, admin_session):
        """Admin (tenant admin) can access admin resources."""
        info = MockInfo(user_session=admin_session)
        permission = IsAdmin()
        assert permission.has_permission(None, info) is True

    def test_collaborator_denied(self, collaborator_session):
        info = MockInfo(user_session=collaborator_session)
        permission = IsAdmin()
        assert permission.has_permission(None, info) is False


class TestIsStaffPermission:
    """Staff: system owner (superior to admin).

    Only staff can access staff resources.
    Admin CANNOT access staff resources (admin < staff).
    """
    def test_unauthenticated_user_denied(self, mock_info):
        permission = IsStaff()
        assert permission.has_permission(None, mock_info) is False

    def test_authenticated_user_denied(self, authenticated_session):
        info = MockInfo(user_session=authenticated_session)
        permission = IsStaff()
        assert permission.has_permission(None, info) is False

    def test_staff_user_allowed(self, staff_session):
        """Staff (system owner) can access staff resources."""
        info = MockInfo(user_session=staff_session)
        permission = IsStaff()
        assert permission.has_permission(None, info) is True

    def test_admin_user_denied(self, admin_session):
        """Admin CANNOT access staff resources (admin < staff hierarchy)."""
        info = MockInfo(user_session=admin_session)
        permission = IsStaff()
        assert permission.has_permission(None, info) is False

    def test_collaborator_denied(self, collaborator_session):
        info = MockInfo(user_session=collaborator_session)
        permission = IsStaff()
        assert permission.has_permission(None, info) is False


class TestIsOrganizationUserPermission:
    def test_unauthenticated_user_denied(self, mock_info):
        permission = IsOrganizationUser()
        assert permission.has_permission(None, mock_info) is False

    def test_authenticated_user_denied(self, authenticated_session):
        """Only authenticated with a valid role can access org user resources."""
        info = MockInfo(user_session=authenticated_session)
        permission = IsOrganizationUser()
        assert permission.has_permission(None, info) is False

    def test_staff_user_allowed(self, staff_session):
        """Staff can access org user resources."""
        info = MockInfo(user_session=staff_session)
        permission = IsOrganizationUser()
        assert permission.has_permission(None, info) is True

    def test_admin_user_allowed(self, admin_session):
        """Admin can access org user resources."""
        info = MockInfo(user_session=admin_session)
        permission = IsOrganizationUser()
        assert permission.has_permission(None, info) is True

    def test_collaborator_allowed(self, collaborator_session):
        info = MockInfo(user_session=collaborator_session)
        permission = IsOrganizationUser()
        assert permission.has_permission(None, info) is True


# Integration tests: Access control matrix

class TestAccessControlMatrix:
    """
    Test matrix verifying that:
    - Unauthenticated: NO access to anything
    - Collaborator: Can access organization user resources only
    - Staff: Can access staff resources + organization user resources
    - Admin: Can access all resources
    """

    @pytest.mark.parametrize(
        "session,is_authenticated,is_admin,is_staff,is_org_user",
        [
            (None, False, False, False, False),  # Unauthenticated
            (
                "collaborator",
                True,  # Collaborator is authenticated
                False,  # Collaborator cannot access admin resources
                False,  # Collaborator cannot access staff resources
                True,   # Collaborator can access org_user resources
            ),  # Collaborator (lowest level)
            (
                "admin",
                True,   # Admin is authenticated
                True,   # Admin can access admin resources
                False,  # Admin CANNOT access staff resources (admin < staff)
                True,   # Admin can access org_user resources
            ),  # Admin (tenant admin, middle level)
            (
                "staff",
                True,   # Staff is authenticated
                True,   # Staff can access admin resources (staff > admin)
                True,   # Staff can access staff resources
                True,   # Staff can access org_user resources
            ),  # Staff (system owner, highest level)
        ],
        ids=["unauthenticated", "collaborator", "admin", "staff"],
    )
    def test_access_control_matrix(
        self,
        session,
        is_authenticated,
        is_admin,
        is_staff,
        is_org_user,
        authenticated_session,
        collaborator_session,
        staff_session,
        admin_session,
    ):
        """Verify access control matrix across all permission classes."""
        session_map = {
            "authenticated": authenticated_session,
            "collaborator": collaborator_session,
            "staff": staff_session,
            "admin": admin_session,
        }

        user_session = session_map.get(session) if session else None
        info = MockInfo(user_session=user_session)

        # Test each permission class
        is_auth_perm = IsAuthenticated()
        is_admin_perm = IsAdmin()
        is_staff_perm = IsStaff()
        is_org_user_perm = IsOrganizationUser()

        assert is_auth_perm.has_permission(None, info) is is_authenticated
        assert is_admin_perm.has_permission(None, info) is is_admin
        assert is_staff_perm.has_permission(None, info) is is_staff
        assert is_org_user_perm.has_permission(None, info) is is_org_user
