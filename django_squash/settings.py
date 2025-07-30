from __future__ import annotations

from django.conf import settings as global_settings
from django.utils.functional import lazy

DJANGO_SQUASH_IGNORE_APPS = lazy(lambda: getattr(global_settings, "DJANGO_SQUASH_IGNORE_APPS", None) or [], list)()
DJANGO_SQUASH_MIGRATION_NAME = lazy(
    lambda: getattr(global_settings, "DJANGO_SQUASH_MIGRATION_NAME", None) or "squashed", str
)()
DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION = lazy(
    lambda: getattr(global_settings, "DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION", None) or "", str
)()
