"""
src/django_identifiers/mixins.py

Model mixin for automatically generated and optionally immutable identifiers.
"""

from __future__ import annotations

from typing import Any, ClassVar

from django.db import IntegrityError, models, transaction

from .generators import generate_identifier


class AutoIdentifiersMixin(models.Model):
    """
    Generate configured identifier fields during model creation.

    Identifier configuration is declared per field::

        AUTO_IDENTIFIERS = {
            "code": {
                "pattern": "aaaaaaaaa",
                "immutable": True,
            },
        }

    Blank configured fields are generated on first save. Fields marked
    immutable cannot be changed after creation unless an explicit save escape
    hatch is provided.
    """

    AUTO_IDENTIFIERS: ClassVar[dict[str, dict[str, Any]]] = {}
    AUTO_IDENTIFIER_MAX_RETRIES: ClassVar[int] = 3

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Save the model while applying configured identifier behavior.

        ``_allow_identifier_change=True`` permits changes to every immutable
        identifier for the save operation.

        ``_allow_<field>_change=True`` permits a change to one immutable
        identifier.
        """
        allow_all = bool(kwargs.pop("_allow_identifier_change", False))
        fields = list(self.AUTO_IDENTIFIERS)

        if not fields:
            super().save(*args, **kwargs)
            return

        if self._state.adding:
            self._create_with_identifiers(fields, *args, **kwargs)
            return

        self._enforce_immutability(fields, allow_all, kwargs)
        super().save(*args, **kwargs)

    def _create_with_identifiers(
        self,
        fields: list[str],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Generate missing identifiers and retry failed create operations."""
        automatic_fields = [
            field for field in fields if self._is_blank(getattr(self, field, None))
        ]

        for _ in range(self.AUTO_IDENTIFIER_MAX_RETRIES):
            self._populate_identifiers(automatic_fields)

            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
            except IntegrityError:
                continue

            return

        self._populate_identifiers(automatic_fields)
        super().save(*args, **kwargs)

    def _populate_identifiers(self, fields: list[str]) -> None:
        """Generate and assign values for managed identifier fields."""
        for field in fields:
            setattr(
                self,
                field,
                generate_identifier(
                    model_class=self.__class__,
                    field_name=field,
                ),
            )

    def _enforce_immutability(
        self,
        fields: list[str],
        allow_all: bool,  # noqa: FBT001
        kwargs: dict[str, Any],
    ) -> None:
        """Reject changes to immutable identifier fields."""
        original = (
            self.__class__._default_manager.filter(  # noqa: SLF001
                pk=self.pk,
            )
            .values(*fields)
            .first()
            or {}
        )

        for field in fields:
            options = self.AUTO_IDENTIFIERS.get(field, {})
            if not options.get("immutable", False):
                continue

            allowed = allow_all or bool(
                kwargs.pop(f"_allow_{field}_change", False),
            )

            if getattr(self, field, None) != original.get(field) and not allowed:
                msg = f"The {field!r} field cannot be changed after creation."
                raise ValueError(msg)

    @staticmethod
    def _is_blank(value: Any) -> bool:
        """Return whether a value should receive an automatic identifier."""
        return value is None or value == ""
