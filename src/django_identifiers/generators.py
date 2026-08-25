"""
src/django_identifiers/generators.py

Core primitives for generating short, collision-resistant identifiers.
"""

from __future__ import annotations

import secrets
from typing import Any

from django.apps import apps
from django.db import IntegrityError, models, transaction

from .exceptions import IdentifierGenerationError

SAFE_UPPERCASE = "ABCDEFGHJKMNPQRSTUVWXYZ"
SAFE_LOWERCASE = "abcdefghjkmnpqrstuvwxyz"
SAFE_DIGITS = "23456789"

_PATTERN_CHARACTERS = {
    "L": SAFE_UPPERCASE,
    "l": SAFE_LOWERCASE,
    "N": SAFE_DIGITS,
    "a": SAFE_LOWERCASE + SAFE_DIGITS,
    "A": SAFE_UPPERCASE + SAFE_DIGITS,
}


def generate_random_number(length: int) -> str:
    """Generate a random numeric string using digits 2-9."""
    if length <= 0:
        msg = "length must be greater than 0"
        raise ValueError(msg)

    return "".join(secrets.choice(SAFE_DIGITS) for _ in range(length))


def generate_random_string(
    pattern: str | None = None,
    length: int = 7,
) -> str:
    """
    Generate a random string using a pattern or the default safe alphabet.

    Pattern tokens:
    - ``L``: uppercase letter
    - ``l``: lowercase letter
    - ``N``: digit 2-9
    - ``a``: lowercase letter or digit
    - ``A``: uppercase letter or digit

    Characters that are not recognized tokens are emitted literally.
    """
    if pattern is not None:
        return "".join(
            secrets.choice(_PATTERN_CHARACTERS.get(char, char)) for char in pattern
        )

    if length <= 0:
        msg = "length must be greater than 0"
        raise ValueError(msg)

    alphabet = SAFE_UPPERCASE + SAFE_DIGITS
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_identifier(
    *,
    model_class: type[models.Model] | str | None = None,
    field_name: str = "code",
    pattern: str | None = None,
    length: int = 7,
) -> str:
    """
    Generate an identifier.

    When a model is supplied, model field configuration is applied and
    existing database values are avoided on a best-effort basis.

    The database uniqueness constraint remains authoritative under
    concurrent writes.
    """
    if model_class is None:
        return generate_random_string(pattern=pattern, length=length)

    model = resolve_model_class(model_class)
    resolved_pattern, resolved_length = resolve_identifier_style(
        model_class=model,
        field_name=field_name,
        pattern=pattern,
        length=length,
    )

    while True:
        identifier = generate_random_string(
            pattern=resolved_pattern,
            length=resolved_length,
        )
        if not model._default_manager.filter(  # noqa: SLF001
            **{field_name: identifier},
        ).exists():
            return identifier


def generate_number(
    *,
    length: int = 7,
    model_class: type[models.Model] | str | None = None,
    field_name: str = "no",
) -> str:
    """
    Generate a numeric identifier using digits 2-9.

    When a model is supplied, existing database values are avoided on a
    best-effort basis.
    """
    if length <= 0:
        msg = "length must be greater than 0"
        raise ValueError(msg)

    if model_class is None:
        return generate_random_number(length)

    model = resolve_model_class(model_class)

    while True:
        identifier = generate_random_number(length)
        if not model._default_manager.filter(  # noqa: SLF001
            **{field_name: identifier},
        ).exists():
            return identifier


def safe_generate_identifier(
    instance: models.Model,
    *,
    field_name: str = "code",
    pattern: str | None = None,
    length: int = 7,
    max_attempts: int = 5,
) -> str:
    """
    Generate, assign, and save an identifier with collision retries.

    This helper is intended for scripts, factories, and other workflows where
    the helper owns the save operation.
    """
    if max_attempts <= 0:
        msg = "max_attempts must be greater than 0"
        raise ValueError(msg)

    model_class = instance.__class__

    for _ in range(max_attempts):
        identifier = generate_identifier(
            model_class=model_class,
            field_name=field_name,
            pattern=pattern,
            length=length,
        )
        setattr(instance, field_name, identifier)

        try:
            with transaction.atomic():
                instance.save()
        except IntegrityError:
            continue

        return identifier

    msg = (
        f"Failed to generate unique identifier for {field_name!r} "
        f"after {max_attempts} attempts"
    )
    raise IdentifierGenerationError(msg)


def resolve_model_class(
    model_class: type[models.Model] | str,
) -> type[models.Model]:
    """Resolve and validate a Django model class."""
    if isinstance(model_class, str):
        resolved = apps.get_model(model_class)

        if resolved is None:
            msg = f"Unknown Django model: {model_class}"
            raise LookupError(msg)

        model_class = resolved

    if not isinstance(model_class, type) or not issubclass(
        model_class,
        models.Model,
    ):
        msg = "model_class must be a Django model class"
        raise TypeError(msg)

    return model_class


def resolve_identifier_style(
    *,
    model_class: type[models.Model],
    field_name: str,
    pattern: str | None,
    length: int,
) -> tuple[str | None, int]:
    """
    Resolve the generation style for a model identifier field.

    Per-field options declared in ``AUTO_IDENTIFIERS`` take precedence over
    explicit function fallbacks.
    """
    configuration: dict[str, dict[str, Any]] = getattr(
        model_class,
        "AUTO_IDENTIFIERS",
        {},
    )
    options = configuration.get(field_name, {})

    resolved_pattern = options.get("pattern", pattern)
    resolved_length = int(options.get("length", length))

    if resolved_pattern is not None:
        pattern_value = str(resolved_pattern)
        return pattern_value, len(pattern_value)

    if resolved_length <= 0:
        msg = "identifier length must be greater than 0"
        raise ValueError(msg)

    return None, resolved_length
