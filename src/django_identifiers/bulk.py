"""
src/django_identifiers/bulk.py

Bulk identifier generation and model creation helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, TypeVar

from django.db import IntegrityError, models, transaction

from .exceptions import IdentifierGenerationError
from .generators import (
    generate_random_string,
    resolve_identifier_style,
    resolve_model_class,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

ModelT = TypeVar("ModelT", bound=models.Model)

_DEFAULT_GENERATION_FACTOR: Final[int] = 3


def generate_identifiers_batch(  # noqa: PLR0913
    *,
    model_class: type[models.Model] | str,
    count: int,
    field_name: str = "code",
    pattern: str | None = None,
    length: int = 7,
    max_rounds: int = 10,
    db_check: bool = True,
) -> list[str]:
    """
    Generate unique identifier candidates for bulk operations.

    Returned identifiers are unique within the batch. When ``db_check`` is
    enabled, existing database values are filtered in one query per generation
    round.

    Database uniqueness constraints remain authoritative under concurrent
    writes.
    """
    if count <= 0:
        msg = "count must be greater than 0"
        raise ValueError(msg)

    if max_rounds <= 0:
        msg = "max_rounds must be greater than 0"
        raise ValueError(msg)

    model = resolve_model_class(model_class)
    resolved_pattern, resolved_length = resolve_identifier_style(
        model_class=model,
        field_name=field_name,
        pattern=pattern,
        length=length,
    )

    identifiers: list[str] = []
    seen: set[str] = set()

    for _ in range(max_rounds):
        remaining = count - len(identifiers)
        if remaining <= 0:
            return identifiers

        candidates: list[str] = []
        generation_count = remaining * _DEFAULT_GENERATION_FACTOR

        for _ in range(generation_count):
            candidate = generate_random_string(
                pattern=resolved_pattern,
                length=resolved_length,
            )
            if candidate in seen:
                continue

            seen.add(candidate)
            candidates.append(candidate)

        if db_check and candidates:
            existing = set(
                model._default_manager.filter(  # noqa: SLF001
                    **{f"{field_name}__in": candidates},
                ).values_list(field_name, flat=True),
            )
            candidates = [
                candidate for candidate in candidates if candidate not in existing
            ]

        identifiers.extend(candidates[:remaining])

    if len(identifiers) == count:
        return identifiers

    msg = (
        f"Failed to generate {count} unique identifiers for "
        f"{model._meta.label}.{field_name} after {max_rounds} rounds"  # noqa: SLF001
    )
    raise IdentifierGenerationError(msg)


def assign_missing_identifiers(  # noqa: PLR0913
    *,
    model_class: type[models.Model] | str,
    instances: list[ModelT],
    field_name: str = "code",
    pattern: str | None = None,
    length: int = 7,
    db_check: bool = True,
) -> None:
    """Assign identifiers in memory to instances whose target field is blank."""
    if not instances:
        return

    missing = [
        instance for instance in instances if _is_blank(getattr(instance, field_name))
    ]
    if not missing:
        return

    identifiers = generate_identifiers_batch(
        model_class=model_class,
        count=len(missing),
        field_name=field_name,
        pattern=pattern,
        length=length,
        db_check=db_check,
    )

    for instance, identifier in zip(missing, identifiers, strict=True):
        setattr(instance, field_name, identifier)


def bulk_create_with_identifiers(
    *,
    model_class: type[models.Model] | str,
    instances: list[ModelT],
    field_name: str = "code",
    batch_size: int = 1000,
    max_retries: int = 5,
) -> int:
    """
    Bulk-create instances with generated identifiers.

    Missing identifiers are populated before insertion. Failed batches are
    regenerated and retried. Persistently failing multi-row batches are split
    recursively so a failing row can ultimately surface its IntegrityError.
    """
    if not instances:
        return 0

    if batch_size <= 0:
        msg = "batch_size must be greater than 0"
        raise ValueError(msg)

    if max_retries <= 0:
        msg = "max_retries must be greater than 0"
        raise ValueError(msg)

    model = resolve_model_class(model_class)
    created = 0

    for chunk in _chunked(instances, batch_size):
        created += _bulk_create_chunk(
            model_class=model,
            instances=chunk,
            field_name=field_name,
            max_retries=max_retries,
        )

    return created


def _bulk_create_chunk(
    *,
    model_class: type[models.Model],
    instances: list[ModelT],
    field_name: str,
    max_retries: int,
) -> int:
    """Create one resilient bulk-insert chunk."""
    assign_missing_identifiers(
        model_class=model_class,
        instances=instances,
        field_name=field_name,
    )

    for attempt in range(1, max_retries + 1):  # pragma: no branch
        try:
            with transaction.atomic():
                model_class._default_manager.bulk_create(  # noqa: SLF001
                    instances,
                    batch_size=len(instances),
                )
        except IntegrityError:
            _regenerate_identifiers(
                model_class=model_class,
                instances=instances,
                field_name=field_name,
            )

            if attempt == max_retries:
                if len(instances) == 1:
                    raise

                midpoint = len(instances) // 2
                return _bulk_create_chunk(
                    model_class=model_class,
                    instances=instances[:midpoint],
                    field_name=field_name,
                    max_retries=max_retries,
                ) + _bulk_create_chunk(
                    model_class=model_class,
                    instances=instances[midpoint:],
                    field_name=field_name,
                    max_retries=max_retries,
                )
        else:
            return len(instances)

    # max_retries is validated as positive by the public entry point, and each
    # final attempt either returns, raises, or recursively returns.
    msg = "unreachable"  # pragma: no cover
    raise AssertionError(msg)  # pragma: no cover


def _regenerate_identifiers(
    *,
    model_class: type[models.Model],
    instances: list[ModelT],
    field_name: str,
) -> None:
    """Replace identifiers for every instance in a failed chunk."""
    identifiers = generate_identifiers_batch(
        model_class=model_class,
        count=len(instances),
        field_name=field_name,
    )

    for instance, identifier in zip(
        instances,
        identifiers,
        strict=True,
    ):
        setattr(instance, field_name, identifier)


def _is_blank(value: Any) -> bool:
    """Return whether a value should receive an automatic identifier."""
    return value is None or value == ""


def _chunked(
    instances: list[ModelT],
    size: int,
) -> Iterator[list[ModelT]]:
    """Yield fixed-size chunks from a list of model instances."""
    for index in range(0, len(instances), size):
        yield instances[index : index + size]
