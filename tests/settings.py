"""
tests/settings.py

Minimal Django settings for the django-identifiers test suite.
"""

from __future__ import annotations

SECRET_KEY = "django-identifiers-tests"  # noqa: S105

INSTALLED_APPS: list[str] = []

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
