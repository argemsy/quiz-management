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

    #: Admin selections aren't bounded to what's on screen — Django admin's
    #: "select all N matching your search" can put 100k+ objects in one
    #: `queryset`. Streaming reads (`.iterator(chunk_size=...)`) and
    #: batching the audit writes (`bulk_create` via `execute_many`, one
    #: event per chunk instead of one per object) keep this from becoming
    #: N single-row inserts and an N-object list held in memory at once —
    #: same convention as `QuestionRepositoryImpl.bulk_create` and this
    #: project's ADR on chunked bulk processing.
    _BULK_AUDIT_CHUNK_SIZE = 1000

    def _bulk_update_with_audit(
        self, request, queryset, *, action_type, message: str, **update_fields
    ) -> None:
        """Shared by every bulk admin action this mixin audits — same shape
        as the plain `queryset.update(...)` actions in `CommonAdminActionsMixin`
        (`ActivableAdminMixin`/`SoftDeleteAdminMixin`), except it captures a
        per-object before/after state and publishes it for auditing instead
        of a silent bulk write. `update_fields` are evaluated once by the
        caller (e.g. a shared `timezone.now()`), so every object in the
        batch gets the same timestamp, matching what
        `queryset.update(**update_fields)` itself does in one SQL statement.

        Previous-state capture must happen before the `UPDATE` (there's
        nothing left to read after); current-state is derived by merging
        rather than re-querying, so this needs exactly one read pass and
        one write pass over the queryset, not two per chunk.
        """
        json_safe_fields = json.loads(json.dumps(update_fields, cls=DjangoJSONEncoder))
        user_id = getattr(request.user, "id", None)

        batch: list[dict] = []
        for obj in queryset.iterator(chunk_size=self._BULK_AUDIT_CHUNK_SIZE):
            previous_state = _json_safe_state(obj)
            batch.append(
                {
                    "object_id": obj.pk,
                    "object_repr": str(obj),
                    "tenant": self._resolve_audit_tenant(obj),
                    "previous_state": previous_state,
                    "current_state": {**previous_state, **json_safe_fields},
                }
            )
            if len(batch) >= self._BULK_AUDIT_CHUNK_SIZE:
                self._publish_bulk_audit_event(
                    action_type=action_type, user_id=user_id, records=batch
                )
                batch = []
        if batch:
            self._publish_bulk_audit_event(
                action_type=action_type, user_id=user_id, records=batch
            )

        updated = queryset.update(**update_fields)
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

    def _publish_bulk_audit_event(
        self, *, action_type, user_id: uuid.UUID | None, records: list[dict]
    ) -> None:
        """One event per chunk carrying many records (`data["records"]`) —
        `handle_account_entity_changed` routes this shape to
        `RecordAuditLogUseCase.execute_many()`, one `bulk_create()` per
        chunk instead of one `publish()`/INSERT per object."""
        content_type_label = self.audit_content_type.name.lower()
        action_label = action_type.name.lower()
        get_event_bus().publish(
            EventBusMessage(
                channel=AccountEventChannel.ENTITY_CHANGED,
                resource_name=f"{content_type_label}_{action_label}_bulk",
                data={
                    "records": [
                        {
                            "object_id": record["object_id"],
                            "object_repr": record["object_repr"],
                            "content_type": self.audit_content_type,
                            "source_type": AuditLogSourceEnum.ADMIN,
                            "action_type": action_type,
                            "user": user_id,
                            "tenant": record["tenant"],
                            "previous_state": record["previous_state"],
                            "current_state": record["current_state"],
                        }
                        for record in records
                    ]
                },
            )
        )
