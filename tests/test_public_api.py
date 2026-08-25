"""
tests/test_public_api.py

Tests for the public django-identifiers package API.
"""

from __future__ import annotations

import pytest

import django_identifiers


def test_public_api() -> None:
    assert django_identifiers.__all__ == (
        "AutoIdentifiersMixin",
        "IdentifierGenerationError",
        "assign_missing_identifiers",
        "bulk_create_with_identifiers",
        "generate_identifier",
        "generate_identifiers_batch",
        "generate_number",
        "generate_random_number",
        "generate_random_string",
        "safe_generate_identifier",
    )


def test_public_api_symbols_are_available() -> None:
    for name in django_identifiers.__all__:
        assert hasattr(django_identifiers, name)


def test_auto_identifiers_mixin_is_lazy_public_api() -> None:
    from django_identifiers.mixins import AutoIdentifiersMixin  # noqa: PLC0415

    assert django_identifiers.AutoIdentifiersMixin is AutoIdentifiersMixin


def test_unknown_public_attribute_raises_attribute_error() -> None:
    with pytest.raises(
        AttributeError,
        match="has no attribute 'missing'",
    ):
        django_identifiers.missing  # noqa: B018
