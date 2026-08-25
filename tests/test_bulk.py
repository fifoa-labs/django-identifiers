"""
tests/test_bulk.py

Tests for bulk identifier generation and creation helpers.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from django.db import IntegrityError, models

from django_identifiers import (
    IdentifierGenerationError,
    assign_missing_identifiers,
    bulk,
    bulk_create_with_identifiers,
    generate_identifiers_batch,
)


class BulkModel(models.Model):  # noqa: DJ008
    """Test model used for bulk identifier behavior."""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=64, unique=True, blank=True)

    AUTO_IDENTIFIERS: ClassVar[dict[str, dict[str, object]]] = {
        "code": {
            "pattern": "aaaaaa",
        },
    }

    class Meta:
        app_label = "tests"
        managed = False


def test_generate_identifiers_batch_returns_unique_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = iter(
        [
            "aaaaaa",
            "aaaaaa",
            "bbbbbb",
            "cccccc",
            "dddddd",
            "eeeeee",
            "ffffff",
            "gggggg",
            "hhhhhh",
        ],
    )

    monkeypatch.setattr(
        bulk,
        "generate_random_string",
        lambda **_kwargs: next(values),
    )

    identifiers = generate_identifiers_batch(
        model_class=BulkModel,
        count=3,
        db_check=False,
    )

    assert identifiers == [
        "aaaaaa",
        "bbbbbb",
        "cccccc",
    ]


@pytest.mark.parametrize("count", [0, -1])
def test_generate_identifiers_batch_rejects_invalid_count(count: int) -> None:
    with pytest.raises(ValueError, match="count must be greater than 0"):
        generate_identifiers_batch(
            model_class=BulkModel,
            count=count,
        )


def test_generate_identifiers_batch_rejects_invalid_rounds() -> None:
    with pytest.raises(ValueError, match="max_rounds must be greater than 0"):
        generate_identifiers_batch(
            model_class=BulkModel,
            count=1,
            max_rounds=0,
        )


def test_generate_identifiers_batch_raises_when_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bulk,
        "generate_random_string",
        lambda **_kwargs: "same",
    )

    with pytest.raises(
        IdentifierGenerationError,
        match="Failed to generate",
    ):
        generate_identifiers_batch(
            model_class=BulkModel,
            count=2,
            max_rounds=1,
            db_check=False,
        )


def test_assign_missing_identifiers_only_fills_blanks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances = [
        BulkModel(name="one", code=""),
        BulkModel(name="two", code="existing"),
        BulkModel(name="three", code=""),
    ]

    monkeypatch.setattr(
        bulk,
        "generate_identifiers_batch",
        lambda **_kwargs: ["first", "second"],
    )

    assign_missing_identifiers(
        model_class=BulkModel,
        instances=instances,
    )

    assert instances[0].code == "first"
    assert instances[1].code == "existing"
    assert instances[2].code == "second"


def test_assign_missing_identifiers_handles_empty_list() -> None:
    assign_missing_identifiers(
        model_class=BulkModel,
        instances=[],
    )


def test_bulk_create_with_identifiers_handles_empty_list() -> None:
    result = bulk_create_with_identifiers(
        model_class=BulkModel,
        instances=[],
    )

    assert result == 0


def test_bulk_create_with_identifiers_rejects_invalid_batch_size() -> None:
    with pytest.raises(ValueError, match="batch_size must be greater than 0"):
        bulk_create_with_identifiers(
            model_class=BulkModel,
            instances=[BulkModel()],
            batch_size=0,
        )


def test_bulk_create_with_identifiers_rejects_invalid_retries() -> None:
    with pytest.raises(ValueError, match="max_retries must be greater than 0"):
        bulk_create_with_identifiers(
            model_class=BulkModel,
            instances=[BulkModel()],
            max_retries=0,
        )


@pytest.mark.django_db(transaction=True)
def test_bulk_create_chunk_retries_integrity_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances = [
        BulkModel(name="one"),
        BulkModel(name="two"),
    ]
    calls = {"count": 0}

    monkeypatch.setattr(
        bulk,
        "assign_missing_identifiers",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        bulk,
        "_regenerate_identifiers",
        lambda **_kwargs: None,
    )

    def fake_bulk_create(
        _instances: list[BulkModel],
        batch_size: int,
    ) -> None:
        calls["count"] += 1

        if calls["count"] == 1:
            msg = "duplicate"
            raise IntegrityError(msg)

        assert batch_size == 2

    monkeypatch.setattr(
        BulkModel._default_manager,  # noqa: SLF001
        "bulk_create",
        fake_bulk_create,
    )

    result = bulk._bulk_create_chunk(  # noqa: SLF001
        model_class=BulkModel,
        instances=instances,
        field_name="code",
        max_retries=2,
    )

    assert result == 2
    assert calls["count"] == 2


@pytest.mark.django_db(transaction=True)
def test_bulk_create_chunk_bubbles_single_row_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances = [BulkModel(name="one")]

    monkeypatch.setattr(
        bulk,
        "assign_missing_identifiers",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        bulk,
        "_regenerate_identifiers",
        lambda **_kwargs: None,
    )

    def fail_bulk_create(*_args: object, **_kwargs: object) -> None:
        msg = "duplicate"
        raise IntegrityError(msg)

    monkeypatch.setattr(
        BulkModel._default_manager,  # noqa: SLF001
        "bulk_create",
        fail_bulk_create,
    )

    with pytest.raises(IntegrityError):
        bulk._bulk_create_chunk(  # noqa: SLF001
            model_class=BulkModel,
            instances=instances,
            field_name="code",
            max_retries=1,
        )


def test_chunked() -> None:
    instances = [BulkModel(name=str(index)) for index in range(5)]

    chunks = list(bulk._chunked(instances, 2))  # noqa: SLF001

    assert [len(chunk) for chunk in chunks] == [2, 2, 1]


def test_generate_identifiers_batch_filters_existing_database_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = iter(
        [
            "existing",
            "first",
            "second",
            "third",
            "fourth",
            "fifth",
        ],
    )

    class QuerySet:
        @staticmethod
        def values_list(
            _field_name: str,
            *,
            flat: bool,
        ) -> list[str]:
            assert flat is True
            return ["existing"]

    monkeypatch.setattr(
        BulkModel._default_manager,  # noqa: SLF001
        "filter",
        lambda **_kwargs: QuerySet(),
    )
    monkeypatch.setattr(
        bulk,
        "generate_random_string",
        lambda **_kwargs: next(values),
    )

    identifiers = generate_identifiers_batch(
        model_class=BulkModel,
        count=2,
        db_check=True,
    )

    assert identifiers == ["first", "second"]


def test_assign_missing_identifiers_returns_when_nothing_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances = [
        BulkModel(name="one", code="existing-one"),
        BulkModel(name="two", code="existing-two"),
    ]

    def unexpected_generation(**_kwargs: object) -> list[str]:
        pytest.fail("generation should not run")

    monkeypatch.setattr(
        bulk,
        "generate_identifiers_batch",
        unexpected_generation,
    )

    assign_missing_identifiers(
        model_class=BulkModel,
        instances=instances,
    )

    assert instances[0].code == "existing-one"
    assert instances[1].code == "existing-two"


def test_bulk_create_with_identifiers_processes_multiple_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances = [BulkModel(name=str(index)) for index in range(5)]
    chunks: list[int] = []

    def fake_create_chunk(
        *,
        model_class: type[models.Model],
        instances: list[BulkModel],
        field_name: str,
        max_retries: int,
    ) -> int:
        assert model_class is BulkModel
        assert field_name == "code"
        assert max_retries == 5

        chunks.append(len(instances))
        return len(instances)

    monkeypatch.setattr(
        bulk,
        "_bulk_create_chunk",
        fake_create_chunk,
    )

    result = bulk_create_with_identifiers(
        model_class=BulkModel,
        instances=instances,
        batch_size=2,
    )

    assert result == 5
    assert chunks == [2, 2, 1]


@pytest.mark.django_db(transaction=True)
def test_bulk_create_chunk_splits_persistent_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances = [
        BulkModel(name="one"),
        BulkModel(name="two"),
    ]

    monkeypatch.setattr(
        bulk,
        "assign_missing_identifiers",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        bulk,
        "_regenerate_identifiers",
        lambda **_kwargs: None,
    )

    calls: list[int] = []

    def fake_bulk_create(
        objects: list[BulkModel],
        *,
        batch_size: int,
    ) -> None:
        calls.append(len(objects))

        if len(objects) > 1:
            msg = "forced multi-row failure"
            raise IntegrityError(msg)

        assert batch_size == 1

    monkeypatch.setattr(
        BulkModel._default_manager,  # noqa: SLF001
        "bulk_create",
        fake_bulk_create,
    )

    result = bulk._bulk_create_chunk(  # noqa: SLF001
        model_class=BulkModel,
        instances=instances,
        field_name="code",
        max_retries=1,
    )

    assert result == 2
    assert calls == [2, 1, 1]


def test_regenerate_identifiers_replaces_all_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances = [
        BulkModel(name="one", code="old-one"),
        BulkModel(name="two", code="old-two"),
    ]

    monkeypatch.setattr(
        bulk,
        "generate_identifiers_batch",
        lambda **_kwargs: ["new-one", "new-two"],
    )

    bulk._regenerate_identifiers(  # noqa: SLF001
        model_class=BulkModel,
        instances=instances,
        field_name="code",
    )

    assert instances[0].code == "new-one"
    assert instances[1].code == "new-two"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, True),
        ("", True),
        ("value", False),
        (0, False),
    ],
)
def test_is_blank(value: object, expected: bool) -> None:  # noqa: FBT001
    assert bulk._is_blank(value) is expected  # noqa: SLF001


def test_generate_identifiers_batch_db_check_filters_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated = iter(
        [
            "existing",
            "first",
            "second",
            "third",
            "fourth",
            "fifth",
        ],
    )

    class QuerySet:
        @staticmethod
        def values_list(
            _field_name: str,
            *,
            flat: bool,
        ) -> list[str]:
            assert flat is True
            return ["existing"]

    def fake_filter(**kwargs: object) -> QuerySet:
        assert "code__in" in kwargs
        return QuerySet()

    monkeypatch.setattr(
        BulkModel._default_manager,  # noqa: SLF001
        "filter",
        fake_filter,
    )
    monkeypatch.setattr(
        bulk,
        "generate_random_string",
        lambda **_kwargs: next(generated),
    )

    identifiers = generate_identifiers_batch(
        model_class=BulkModel,
        count=2,
        field_name="code",
        max_rounds=1,
        db_check=True,
    )

    assert identifiers == ["first", "second"]


def test_generate_identifiers_batch_can_finish_on_final_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated = iter(["first", "second", "third"])

    monkeypatch.setattr(
        bulk,
        "generate_random_string",
        lambda **_kwargs: next(generated),
    )

    identifiers = generate_identifiers_batch(
        model_class=BulkModel,
        count=1,
        max_rounds=1,
        db_check=False,
    )

    assert identifiers == ["first"]
