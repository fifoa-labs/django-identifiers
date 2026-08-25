"""
tests/test_generators.py

Tests for identifier generation primitives.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from django.db import models

from django_identifiers import (
    IdentifierGenerationError,
    generate_identifier,
    generate_number,
    generate_random_number,
    generate_random_string,
    generators,
    safe_generate_identifier,
)


class GeneratorModel(models.Model):  # noqa: DJ008
    """Test model used for generator behavior."""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=64, unique=True, blank=True)
    number = models.CharField(max_length=64, unique=True, blank=True)

    AUTO_IDENTIFIERS: ClassVar[dict[str, dict[str, object]]] = {
        "code": {
            "pattern": "LNNNNN",
        },
    }

    class Meta:
        app_label = "tests"
        managed = False


def test_generate_random_number() -> None:
    result = generate_random_number(12)

    assert len(result) == 12
    assert set(result) <= set("23456789")


@pytest.mark.parametrize("length", [0, -1])
def test_generate_random_number_rejects_invalid_length(length: int) -> None:
    with pytest.raises(ValueError, match="length must be greater than 0"):
        generate_random_number(length)


def test_generate_random_string_without_pattern() -> None:
    result = generate_random_string(length=12)

    assert len(result) == 12
    assert set(result) <= set("ABCDEFGHJKMNPQRSTUVWXYZ23456789")


def test_generate_random_string_with_pattern() -> None:
    result = generate_random_string("LlN-aa-AA")

    assert len(result) == 9

    assert result[0] in "ABCDEFGHJKMNPQRSTUVWXYZ"
    assert result[1] in "abcdefghjkmnpqrstuvwxyz"
    assert result[2] in "23456789"
    assert result[3] == "-"
    assert result[6] == "-"


def test_generate_random_string_preserves_literals() -> None:
    result = generate_random_string("ID-NNN")

    assert result.startswith("ID-")
    assert set(result[3:]) <= set("23456789")


def test_generate_random_string_rejects_invalid_length() -> None:
    with pytest.raises(ValueError, match="length must be greater than 0"):
        generate_random_string(length=0)


def test_generate_identifier_without_model_uses_pattern() -> None:
    result = generate_identifier(pattern="LNNN")

    assert len(result) == 4
    assert result[0] in "ABCDEFGHJKMNPQRSTUVWXYZ"


def test_generate_identifier_uses_model_field_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class QuerySet:
        @staticmethod
        def exists() -> bool:
            return False

    monkeypatch.setattr(
        GeneratorModel._default_manager,  # noqa: SLF001
        "filter",
        lambda **_kwargs: QuerySet(),
    )

    result = generate_identifier(
        model_class=GeneratorModel,
        field_name="code",
    )

    assert len(result) == 6
    assert result[0] in "ABCDEFGHJKMNPQRSTUVWXYZ"
    assert set(result[1:]) <= set("23456789")


def test_generate_identifier_retries_existing_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = iter(["DUP", "GOOD"])

    class QuerySet:
        def __init__(self, exists: bool) -> None:  # noqa: FBT001
            self._exists = exists

        def exists(self) -> bool:
            return self._exists

    def fake_filter(**kwargs: object) -> QuerySet:
        return QuerySet(kwargs["code"] == "DUP")

    monkeypatch.setattr(
        GeneratorModel._default_manager,  # noqa: SLF001
        "filter",
        fake_filter,
    )
    monkeypatch.setattr(
        generators,
        "generate_random_string",
        lambda **_kwargs: next(values),
    )

    result = generate_identifier(
        model_class=GeneratorModel,
        field_name="code",
        pattern="aaa",
    )

    assert result == "GOOD"


def test_generate_number_without_model() -> None:
    result = generate_number(length=8)

    assert len(result) == 8
    assert set(result) <= set("23456789")


def test_generate_number_rejects_invalid_length() -> None:
    with pytest.raises(ValueError, match="length must be greater than 0"):
        generate_number(length=0)


def test_resolve_model_class_rejects_non_model() -> None:
    with pytest.raises(TypeError, match="must be a Django model class"):
        generators.resolve_model_class(object)  # type: ignore[arg-type]


def test_resolve_identifier_style_uses_length() -> None:
    pattern, length = generators.resolve_identifier_style(
        model_class=GeneratorModel,
        field_name="number",
        pattern=None,
        length=11,
    )

    assert pattern is None
    assert length == 11


def test_resolve_identifier_style_rejects_invalid_length() -> None:
    with pytest.raises(
        ValueError,
        match="identifier length must be greater than 0",
    ):
        generators.resolve_identifier_style(
            model_class=GeneratorModel,
            field_name="number",
            pattern=None,
            length=0,
        )


def test_safe_generate_identifier_rejects_invalid_attempts() -> None:
    instance = GeneratorModel(name="test")

    with pytest.raises(ValueError, match="max_attempts must be greater than 0"):
        safe_generate_identifier(instance, max_attempts=0)


@pytest.mark.django_db(transaction=True)
def test_safe_generate_identifier_raises_after_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = GeneratorModel(name="test")

    monkeypatch.setattr(
        generators,
        "generate_identifier",
        lambda **_kwargs: "DUP",
    )

    def fail_save(*_args: object, **_kwargs: object) -> None:
        from django.db import IntegrityError  # noqa: PLC0415

        msg = "duplicate"
        raise IntegrityError(msg)

    monkeypatch.setattr(instance, "save", fail_save)

    with pytest.raises(
        IdentifierGenerationError,
        match="Failed to generate unique identifier",
    ):
        safe_generate_identifier(
            instance,
            max_attempts=2,
        )


def test_generate_identifier_accepts_string_model_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class QuerySet:
        @staticmethod
        def exists() -> bool:
            return False

    monkeypatch.setattr(
        GeneratorModel._default_manager,  # noqa: SLF001
        "filter",
        lambda **_kwargs: QuerySet(),
    )
    monkeypatch.setattr(
        "django_identifiers.generators.apps.get_model",
        lambda _label: GeneratorModel,
    )

    result = generate_identifier(
        model_class="tests.GeneratorModel",
        field_name="code",
    )

    assert len(result) == 6


def test_generate_number_with_model_retries_existing_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = iter(["22222", "33333"])

    class QuerySet:
        def __init__(self, exists: bool) -> None:  # noqa: FBT001
            self._exists = exists

        def exists(self) -> bool:
            return self._exists

    def fake_filter(**kwargs: object) -> QuerySet:
        return QuerySet(kwargs["number"] == "22222")

    monkeypatch.setattr(
        GeneratorModel._default_manager,  # noqa: SLF001
        "filter",
        fake_filter,
    )
    monkeypatch.setattr(
        generators,
        "generate_random_number",
        lambda _length: next(values),
    )

    result = generate_number(
        length=5,
        model_class=GeneratorModel,
        field_name="number",
    )

    assert result == "33333"


@pytest.mark.django_db(transaction=True)
def test_safe_generate_identifier_saves_successfully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = GeneratorModel(name="test")
    saved = {"called": False}

    monkeypatch.setattr(
        generators,
        "generate_identifier",
        lambda **_kwargs: "ABC234",
    )

    def fake_save(*_args: object, **_kwargs: object) -> None:
        saved["called"] = True

    monkeypatch.setattr(instance, "save", fake_save)

    result = safe_generate_identifier(instance)

    assert result == "ABC234"
    assert instance.code == "ABC234"
    assert saved["called"] is True


def test_resolve_model_class_accepts_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "django_identifiers.generators.apps.get_model",
        lambda _label: GeneratorModel,
    )

    result = generators.resolve_model_class("tests.GeneratorModel")

    assert result is GeneratorModel


def test_resolve_model_class_rejects_unknown_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "django_identifiers.generators.apps.get_model",
        lambda _label: None,
    )

    with pytest.raises(LookupError, match="Unknown Django model"):
        generators.resolve_model_class("tests.Missing")


def test_resolve_identifier_style_uses_explicit_pattern() -> None:
    pattern, length = generators.resolve_identifier_style(
        model_class=GeneratorModel,
        field_name="number",
        pattern="NN-NN",
        length=99,
    )

    assert pattern == "NN-NN"
    assert length == 5
