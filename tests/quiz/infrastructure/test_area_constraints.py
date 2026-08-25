import uuid

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from src.quiz.infrastructure.persistence.django.models import AreaModel, QuizAreaModel

pytestmark = pytest.mark.django_db


def test_two_active_root_areas_cannot_share_a_name(make_area):
    """The NULLS NOT DISTINCT case.

    Postgres treats NULLs as distinct in a unique index by default, so
    without that clause this insert would succeed and the tenant would end
    up with two "Ciencias" roots — the exact duplication the constraint
    exists to prevent, failing silently. Asserted against a real
    IntegrityError rather than an application-level check for that reason.
    """
    first = make_area(name="Ciencias")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AreaModel.objects.create(
                name="Ciencias",
                parent=None,
                tenant=first.tenant,
                tenant_user=uuid.uuid4(),
            )


def test_same_name_is_allowed_under_different_parents(make_area):
    ciencias = make_area(name="Ciencias")
    matematica = make_area(
        name="Matemática", tenant=ciencias.tenant, tenant_user=ciencias.tenant_user
    )

    make_area(name="General", parent=ciencias)
    make_area(name="General", parent=matematica)

    assert AreaModel.objects.filter(name="General").count() == 2


def test_same_name_is_allowed_in_different_tenants(make_area):
    make_area(name="Ciencias")
    make_area(name="Ciencias", tenant=uuid.uuid4(), tenant_user=uuid.uuid4())

    assert AreaModel.objects.filter(name="Ciencias").count() == 2


def test_two_children_of_the_same_parent_cannot_share_a_name(make_area):
    ciencias = make_area(name="Ciencias")
    make_area(name="Ciencias I", parent=ciencias)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AreaModel.objects.create(
                name="Ciencias I",
                parent=ciencias,
                tenant=ciencias.tenant,
                tenant_user=ciencias.tenant_user,
            )


def test_a_different_author_in_the_same_tenant_cannot_duplicate_an_area(make_area):
    """An area belongs to its organization, not to whoever created it — so
    `tenant_user` takes no part in identity."""
    existing = make_area(name="Ciencias")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AreaModel.objects.create(
                name="Ciencias",
                parent=None,
                tenant=existing.tenant,
                tenant_user=uuid.uuid4(),
            )


def test_deactivating_an_area_frees_its_name(make_area):
    original = make_area(name="Ciencias")
    original.is_active = False
    original.deactivated_at = timezone.now()
    original.save(update_fields=["is_active", "deactivated_at"])

    replacement = AreaModel.objects.create(
        name="Ciencias",
        parent=None,
        tenant=original.tenant,
        tenant_user=original.tenant_user,
    )

    original.refresh_from_db()
    assert replacement.is_active
    assert not original.is_active
    assert original.deactivated_at is not None


def test_an_area_cannot_be_its_own_parent_at_the_database_level(make_area):
    """The one hierarchy rule expressible as a check constraint — the rest
    need to read another row and live in the domain instead."""
    area = make_area(name="Ciencias")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AreaModel.objects.filter(pk=area.pk).update(parent_id=area.pk)


def test_a_quiz_and_area_cannot_be_related_twice(make_quiz_area):
    relation = make_quiz_area()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            QuizAreaModel.objects.create(
                quiz=relation.quiz,
                area=relation.area,
                tenant=relation.tenant,
                tenant_user=relation.tenant_user,
            )


def test_a_quiz_may_cover_several_areas(make_quiz, make_area, make_quiz_area):
    quiz = make_quiz()
    ciencias = make_area(
        name="Ciencias", tenant=quiz.tenant, tenant_user=quiz.tenant_user
    )
    matematica = make_area(
        name="Matemática", tenant=quiz.tenant, tenant_user=quiz.tenant_user
    )

    make_quiz_area(quiz=quiz, area=ciencias)
    make_quiz_area(quiz=quiz, area=matematica)

    assert quiz.quiz_areas.count() == 2


def test_a_quiz_may_be_related_to_a_root_area(make_quiz, make_area, make_quiz_area):
    """The relation points at whichever level applies — a single foreign key,
    not a polymorphic pair."""
    quiz = make_quiz()
    root = make_area(name="Ciencias", tenant=quiz.tenant, tenant_user=quiz.tenant_user)
    make_area(name="Ciencias I", parent=root)

    relation = make_quiz_area(quiz=quiz, area=root)

    assert relation.area.parent_id is None


def test_a_quiz_with_no_areas_is_valid(make_quiz):
    quiz = make_quiz()

    assert quiz.quiz_areas.count() == 0
