import pytest

from django_squash.db.migrations import writer


def test_check_django_migration_hash_bad(monkeypatch):
    monkeypatch.setattr("django_squash.db.migrations.writer.utils.file_hash", lambda _: "bad_hash")
    with pytest.raises(Warning):
        writer.check_django_migration_hash()


def test_check_django_migration_hash_all_good(monkeypatch):
    valid_hash = writer.SUPPORTED_DJANGO_WRITER[0]
    monkeypatch.setattr("django_squash.db.migrations.writer.utils.file_hash", lambda _: valid_hash)
    writer.check_django_migration_hash()
