from unittest import mock

import pytest

from django_squash.db.migrations import writer


@pytest.fixture
def in_dev_mode(monkeypatch):
    """function dev_mode() returns True."""
    mock_site_packages = mock.Mock(return_value=False)
    monkeypatch.setattr("django_squash.db.migrations.utils.is_code_in_site_packages", mock_site_packages)
    yield


@pytest.fixture
def in_prod_mode(monkeypatch):
    """function dev_mode() returns False."""
    mock_site_packages = mock.Mock(return_value=True)
    monkeypatch.setattr("django_squash.db.migrations.utils.is_code_in_site_packages", mock_site_packages)
    yield


@pytest.mark.usefixtures("in_prod_mode")
@pytest.mark.parametrize(
    "hash, throws_warning",
    (
        ("bad_hash", True),
        (writer.SUPPORTED_DJANGO_WRITER[0], False),
    ),
)
def test_check_django_migration_hash_prod(hash, throws_warning, monkeypatch):
    monkeypatch.setattr("django_squash.db.migrations.writer.utils.file_hash", lambda _: hash)
    if throws_warning:
        with pytest.warns(Warning):
            writer.check_django_migration_hash()
    else:
        writer.check_django_migration_hash()


@pytest.mark.usefixtures("in_dev_mode")
@pytest.mark.parametrize(
    "hash",
    (
        ("bad_hash",),
        (writer.SUPPORTED_DJANGO_WRITER[0],),
    ),
)
def test_check_django_migration_hash_dev(hash, monkeypatch):
    monkeypatch.setattr("django_squash.db.migrations.writer.utils.file_hash", lambda _: hash)
    writer.check_django_migration_hash()
