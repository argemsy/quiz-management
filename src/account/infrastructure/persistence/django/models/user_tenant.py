import uuid

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

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
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
    # `deactivated_at` is not declared here: `QuizActiveMixin` now provides
    # it, and a local redeclaration would shadow the mixin's with an
    # identical field that has to be kept in sync by hand.
    activated_at = models.DateTimeField(blank=True, null=True, editable=False)

    def __str__(self):
        return self.user.email

    class Meta:
        db_table = "user_tenant"
        verbose_name = "User Tenant"
        verbose_name_plural = "User Tenants"
