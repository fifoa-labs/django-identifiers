"""
tests/test_mixins.py

Tests for automatic model identifier generation and immutability.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest
from django.db import IntegrityError, connection, models

from django_identifiers import AutoIdentifiersMixin, mixins

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.django_db(transaction=True)


class Thing(AutoIdentifiersMixin, models.Model):  # noqa: DJ008
    """Test model exercising identifier lifecycle behavior."""

    sku = models.CharField(max_length=64, unique=True, blank=True)
    code = models.CharField(max_length=64, unique=True, blank=True)

    AUTO_IDENTIFIERS: ClassVar[dict[str, dict[str, object]]] = {
        "sku": {
            "pattern": "LNNNNN",
            "immutable": True,
        },
        "code": {
            "pattern": "aaaaaa",
            "immutable": False,
        },
    }

    class Meta:
        app_label = "tests"
        managed = False


@pytest.fixture(autouse=True)
def thing_table() -> Iterator[None]:
    """Create and remove the test model table around each test."""
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(Thing)

    try:
        yield
    finally:
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(Thing)


def test_autogenerates_blank_identifiers() -> None:
    thing = Thing()

    thing.save()

    assert thing.sku
    assert thing.code
    assert len(thing.sku) == 6
    assert len(thing.code) == 6


def test_preserves_explicit_values() -> None:
    thing = Thing(
        sku="SKU-EXPLICIT",
        code="CODE-EXPLICIT",
    )

    thing.save()

    assert thing.sku == "SKU-EXPLICIT"
    assert thing.code == "CODE-EXPLICIT"


def test_immutable_identifier_cannot_change() -> None:
    thing = Thing()
    thing.save()

    original = thing.sku
    thing.sku = "NEW-SKU"

    with pytest.raises(
        ValueError,
        match="'sku' field cannot be changed",
    ):
        thing.save()

    thing.refresh_from_db()

    assert thing.sku == original


def test_mutable_identifier_can_change() -> None:
    thing = Thing()
    thing.save()

    thing.code = "NEW-CODE"
    thing.save()
    thing.refresh_from_db()

    assert thing.code == "NEW-CODE"


def test_allow_all_identifier_change() -> None:
    thing = Thing()
    thing.save()

    thing.sku = "NEW-SKU"
    thing.save(_allow_identifier_change=True)
    thing.refresh_from_db()

    assert thing.sku == "NEW-SKU"


def test_allow_specific_identifier_change() -> None:
    thing = Thing()
    thing.save()

    thing.sku = "NEW-SKU"
    thing.save(_allow_sku_change=True)
    thing.refresh_from_db()

    assert thing.sku == "NEW-SKU"


def test_mixin_without_configuration_uses_normal_save() -> None:
    class PlainThing(AutoIdentifiersMixin, models.Model):  # noqa: DJ008
        name = models.CharField(max_length=64)

        class Meta:
            app_label = "tests"
            managed = False

    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(PlainThing)

    try:
        thing = PlainThing(name="plain")
        thing.save()

        assert thing.pk is not None
    finally:
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(PlainThing)


def test_create_retries_identifier_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Thing(sku="DUP", code="existing").save()

    values = iter(
        [
            "DUP",
            "first-code",
            "GOOD",
            "second-code",
        ],
    )

    monkeypatch.setattr(
        mixins,
        "generate_identifier",
        lambda **_kwargs: next(values),
    )

    thing = Thing()
    thing.save()

    assert thing.sku == "GOOD"
    assert thing.code == "second-code"


def test_create_bubbles_integrity_error_after_retry_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Thing(sku="DUP", code="existing").save()

    monkeypatch.setattr(
        mixins,
        "generate_identifier",
        lambda **_kwargs: "DUP",
    )

    thing = Thing()

    with pytest.raises(IntegrityError):
        thing.save()
