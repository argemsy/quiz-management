from django.db import models

from src.account.shared.account_enums import UserTenantRoleEnum
from src.shared.infrastructure.persistence.django.models import (
    QuizActiveMixin,
    QuizSoftDeleteMixin,
    QuizTimeStampMixin,
)


class UserTenant(QuizTimeStampMixin, QuizActiveMixin, QuizSoftDeleteMixin):
    """A user's membership in a tenant.

    Attributes:
        user: The member. `PROTECT`ed so a user with active memberships
            can't be deleted out from under this record; membership must
            be removed explicitly first.
        tenant: The organization the user belongs to. `PROTECT`ed for the
            same reason.
    """

    user = models.ForeignKey(
        "MyUser", on_delete=models.PROTECT, related_name="user_tenants"
    )
    tenant = models.ForeignKey(
        "Tenant", on_delete=models.PROTECT, related_name="user_tenants"
    )
    role = models.CharField(
        max_length=30,
        choices=UserTenantRoleEnum.choices(),
        default=UserTenantRoleEnum.COLLABORATOR.value,
    )
    activated_at = models.DateTimeField(blank=True, null=True, editable=False)
    deactivated_at = models.DateTimeField(blank=True, null=True, editable=False)

    class Meta:
        db_table = "user_tenant"
        verbose_name = "User Tenant"
        verbose_name_plural = "User Tenants"
