"""
Postgres specific code
"""

try:
    from django.contrib.postgres.operations import CreateExtension as PGCreateExtension
except ImportError:  # pragma: no cover

    class PGCreateExtension:
        pass


__all__ = ("PGCreateExtension",)
