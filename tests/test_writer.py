import pytest

from django_squash.db.migrations import writer


def test_check_django_migration_hash(monkeypatch):
    monkeypatch.setattr("django_squash.db.migrations.writer.utils.file_hash", lambda _: "bad_hash")
    with pytest.raises(Warning):
        writer.check_django_migration_hash()
