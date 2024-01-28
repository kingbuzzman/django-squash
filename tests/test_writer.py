import os
from unittest import mock

import pytest

from django_squash.db.migrations import writer


@pytest.fixture
def in_dev_mode(monkeypatch):
    """function dev_mode() returns True."""
    mock_importlib = mock.Mock()
    mock_importlib.util.find_spec().submodule_search_locations = [os.path.dirname(__file__)]
    monkeypatch.setattr("django_squash.db.migrations.utils.importlib", mock_importlib)


@pytest.fixture
def in_prod_mode(monkeypatch):
    mock_importlib = mock.Mock()
    mock_importlib.util.find_spec().submodule_search_locations = ["path"]
    monkeypatch.setattr("django_squash.db.migrations.utils.importlib", mock_importlib)


@pytest.mark.usefixtures("in_prod_mode")
def test_check_django_migration_hash_bad(monkeypatch):
    monkeypatch.setattr("django_squash.db.migrations.writer.utils.file_hash", lambda _: "bad_hash")
    with pytest.warns(Warning):
        writer.check_django_migration_hash()


@pytest.mark.usefixtures("in_prod_mode")
def test_check_django_migration_hash_all_good(monkeypatch):
    valid_hash = writer.SUPPORTED_DJANGO_WRITER[0]
    monkeypatch.setattr("django_squash.db.migrations.writer.utils.file_hash", lambda _: valid_hash)
    writer.check_django_migration_hash()
