"""
src/django_identifiers/__init__.py

Public API for django-identifiers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .bulk import (
    assign_missing_identifiers,
    bulk_create_with_identifiers,
    generate_identifiers_batch,
)
from .exceptions import IdentifierGenerationError
from .generators import (
    generate_identifier,
    generate_number,
    generate_random_number,
    generate_random_string,
    safe_generate_identifier,
)

if TYPE_CHECKING:
    from .mixins import AutoIdentifiersMixin

__all__ = (
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


def __getattr__(name: str) -> Any:
    """Lazily expose Django model-dependent public API members."""
    if name == "AutoIdentifiersMixin":
        from .mixins import AutoIdentifiersMixin  # noqa: PLC0415

        return AutoIdentifiersMixin

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
