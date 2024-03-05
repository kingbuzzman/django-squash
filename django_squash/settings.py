from django.conf import settings as global_settings

DJANGO_SQUASH_IGNORE_APPS = getattr(global_settings, "DJANGO_SQUASH_IGNORE_APPS", None) or []
DJANGO_SQUASH_MIGRATION_NAME = getattr(global_settings, "DJANGO_SQUASH_MIGRATION_NAME", None) or "squashed"
DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION = getattr(global_settings, "DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION", None)
