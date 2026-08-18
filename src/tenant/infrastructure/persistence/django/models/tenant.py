import uuid

from django.db import models

from src.shared.infrastructure.persistence.django.models import (
    QuizActiveMixin,
    QuizSoftDeleteMixin,
    QuizTimeStampMixin,
)
from src.tenant.shared.tenant_enums import TenantTypeEnum


class Tenant(QuizTimeStampMixin, QuizActiveMixin, QuizSoftDeleteMixin):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    tenant_type = models.CharField(
        db_column="type",
        max_length=30,
        choices=TenantTypeEnum.choices(),
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, editable=False)
    address = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "tenant"
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"

        constraints = [
            models.UniqueConstraint(
                fields=["tenant_type", "name"],
                name="uq_tenant_type_name",
            ),
        ]
