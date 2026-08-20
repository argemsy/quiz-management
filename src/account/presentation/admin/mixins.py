import json
import uuid

from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from src.account.shared.account_event_channels import AccountEventChannel
from src.eventing.shared.eventing_enums import (
    AuditLogActionEnum,
    AuditLogContentTypeEnum,
    AuditLogSourceEnum,
)
from src.shared.infrastructure.event_bus import EventBusMessage, get_event_bus


def _json_safe_state(obj) -> dict:
    """`model_to_dict` returns raw Python values (UUID, datetime, ...) that
    `AuditLog.metadata` (a plain `JSONField`, no custom encoder) can't store
    as-is — round-tripping through `DjangoJSONEncoder` normalizes them."""
    return json.loads(json.dumps(model_to_dict(obj), cls=DjangoJSONEncoder))


class AuditableAdminMixin:
    """Publishes an `AccountEventChannel.ENTITY_CHANGED` event — consumed by
    `eventing` to record an `AuditLog` row — for every add, edit, and every
    bulk action from `CommonAdminActionsMixin` (soft-delete, restore,
    activate, deactivate) made through this `ModelAdmin`.

    Subclasses set `audit_content_type` and, if the audited object isn't
    itself the tenant, override `_resolve_audit_tenant`.
    """

    audit_content_type: AuditLogContentTypeEnum

    def save_model(self, request, obj, form, change):
        previous_state = {}
        if change:
            previous_state = _json_safe_state(type(obj).objects.get(pk=obj.pk))

        super().save_model(request, obj, form, change)

        action_type = (
            AuditLogActionEnum.CHANGE if change else AuditLogActionEnum.ADDITION
        )
        self._publish_audit_event(
            request,
            obj,
            action_type=action_type,
            previous_state=previous_state,
            current_state=_json_safe_state(obj),
        )

    @admin.action(description=_("Delete selected (soft delete)"))
    def soft_delete_instances(self, request, queryset):
        self._bulk_update_with_audit(
            request,
            queryset,
            action_type=AuditLogActionEnum.DELETION,
            message="{count} instance(s) soft-deleted.",
            is_deleted=True,
            deleted_at=timezone.now(),
        )

    @admin.action(description=_("Restore selected"))
    def restore_instances(self, request, queryset):
        self._bulk_update_with_audit(
            request,
            queryset,
            action_type=AuditLogActionEnum.CHANGE,
            message="{count} instance(s) restored.",
            is_deleted=False,
            deleted_at=None,
        )

    @admin.action(description=_("Activate selected"))
    def activate_instances(self, request, queryset):
        self._bulk_update_with_audit(
            request,
            queryset,
            action_type=AuditLogActionEnum.CHANGE,
            message="{count} instance(s) activated.",
            is_active=True,
        )

    @admin.action(description=_("Deactivate selected"))
    def deactivate_instances(self, request, queryset):
        self._bulk_update_with_audit(
            request,
            queryset,
            action_type=AuditLogActionEnum.CHANGE,
            message="{count} instance(s) deactivated.",
            is_active=False,
        )

    def _bulk_update_with_audit(
        self, request, queryset, *, action_type, message: str, **update_fields
    ) -> None:
        """Shared by every bulk admin action this mixin audits — same shape
        as the plain `queryset.update(...)` actions in `CommonAdminActionsMixin`
        (`ActivableAdminMixin`/`SoftDeleteAdminMixin`), except it captures a
        per-object before/after state and publishes one audit event per
        object instead of a single unaudited bulk write. `update_fields` are
        evaluated once by the caller (e.g. a shared `timezone.now()`), so
        every object in the batch gets the same timestamp, matching what
        `queryset.update(**update_fields)` itself does in one SQL statement.
        """
        objects = list(queryset)
        previous_states = {obj.pk: _json_safe_state(obj) for obj in objects}

        updated = queryset.update(**update_fields)

        json_safe_fields = json.loads(json.dumps(update_fields, cls=DjangoJSONEncoder))
        for obj in objects:
            current_state = {**previous_states[obj.pk], **json_safe_fields}
            self._publish_audit_event(
                request,
                obj,
                action_type=action_type,
                previous_state=previous_states[obj.pk],
                current_state=current_state,
            )
        self.message_user(request, message.format(count=updated))

    def _resolve_audit_tenant(self, obj) -> uuid.UUID | None:
        return obj.pk

    def _publish_audit_event(
        self, request, obj, *, action_type, previous_state, current_state
    ) -> None:
        content_type_label = self.audit_content_type.name.lower()
        action_label = action_type.name.lower()
        get_event_bus().publish(
            EventBusMessage(
                channel=AccountEventChannel.ENTITY_CHANGED,
                resource_name=f"{content_type_label}_{action_label}",
                data={
                    "object_id": obj.pk,
                    "object_repr": str(obj),
                    "content_type": self.audit_content_type,
                    "source_type": AuditLogSourceEnum.ADMIN,
                    "action_type": action_type,
                    "user": getattr(request.user, "id", None),
                    "tenant": self._resolve_audit_tenant(obj),
                    "previous_state": previous_state,
                    "current_state": current_state,
                },
            )
        )
