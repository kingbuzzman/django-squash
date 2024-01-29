import pytest

from django_squash.db.migrations import writer


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize(
    "hash, throws_warning",
    (
        ("bad_hash", True),
        (writer.SUPPORTED_DJANGO_WRITER[0], False),
    ),
)
def test_check_django_migration_hash(hash, throws_warning, monkeypatch):
    monkeypatch.setattr("django_squash.db.migrations.writer.utils.file_hash", lambda _: hash)
    if throws_warning:
        with pytest.warns(Warning):
            writer.check_django_migration_hash()
    else:
        writer.check_django_migration_hash()
