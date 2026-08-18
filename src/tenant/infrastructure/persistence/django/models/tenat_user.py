from django.db import models

from src.shared.infrastructure.persistence.django.models import (
    QuizActiveMixin,
    QuizSoftDeleteMixin,
    QuizTimeStampMixin,
)
from src.tenant.shared.tenant_enums import TenantUserRoleEnum


class TenantUser(QuizTimeStampMixin, QuizActiveMixin, QuizSoftDeleteMixin):
    user = models.UUIDField(editable=False)
    tenant = models.ForeignKey(
        "Tenant", on_delete=models.PROTECT, related_name="user_tenants"
    )
    role = models.CharField(
        max_length=30,
        choices=TenantUserRoleEnum.choices(),
        default=TenantUserRoleEnum.COLLABORATOR.value,
    )
    activated_at = models.DateTimeField(blank=True, null=True, editable=False)
    deactivated_at = models.DateTimeField(blank=True, null=True, editable=False)

    class Meta:
        db_table = "tenant_user"
        verbose_name = "Tenant User"
        verbose_name_plural = "Tenant Users"
