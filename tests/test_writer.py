from __future__ import annotations

import pytest

from django_squash.db.migrations import writer


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize(
    "response_hash, throws_warning",  # noqa: PT006
    (
        ("bad_hash", True),
        (writer.SUPPORTED_DJANGO_WRITER[0], False),
    ),
)
def test_check_django_migration_hash(response_hash, throws_warning, monkeypatch):
    monkeypatch.setattr("django_squash.db.migrations.writer.utils.file_hash", lambda _: response_hash)
    if throws_warning:
        with pytest.warns(Warning):
            writer.check_django_migration_hash()
    else:
        writer.check_django_migration_hash()
