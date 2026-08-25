"""
src/django_identifiers/exceptions.py

Exceptions raised by django-identifiers.
"""

from __future__ import annotations


class IdentifierGenerationError(Exception):
    """Raised when identifier generation fails after all attempts."""
