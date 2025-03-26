"""Postgres specific code."""

from __future__ import annotations

try:
    from django.contrib.postgres.operations import CreateExtension as PGCreateExtension
except ImportError:  # pragma: no cover

    class PGCreateExtension:  # noqa: D101
        pass


__all__ = ("PGCreateExtension",)
