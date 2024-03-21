import os
import shutil
import tempfile
from collections import defaultdict
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import connections
from django.db.models.options import Options
from django.test.utils import extend_sys_path
from django.utils.module_loading import module_dir

from django_squash.db.migrations.utils import get_custom_rename_function
from tests import utils


class MigrationPath(Path):
    """
    A subclass of Path that provides a method to list migration files.
    """

    if utils.is_pyvsupported("3.11"):
        try:
            from pathlib import _PosixFlavour, _WindowsFlavour

            # TODO: delete after python 3.11 is no longer supported
            _flavour = _PosixFlavour() if os.name == "posix" else _WindowsFlavour()
        except ImportError:
            pass
    else:
        raise Exception("Remove this whole block please!")

    def migration_files(self):
        """
        Returns a list of migration files in this directory.
        """
        return sorted(p.name for p in self.glob("*.py"))


@pytest.fixture
def migration_app_dir(request, isolated_apps, settings):
    yield from _migration_app_dir("temporary_migration_module", request, settings)


@pytest.fixture
def migration_app2_dir(request, isolated_apps, settings):
    yield from _migration_app_dir("temporary_migration_module2", request, settings)


def _migration_app_dir(marker_name, request, settings):
    """
    Allows testing management commands in a temporary migrations module.
    Wrap all invocations to makemigrations and squashmigrations with this
    context manager in order to avoid creating migration files in your
    source tree inadvertently.
    Takes the application label that will be passed to makemigrations or
    squashmigrations and the Python path to a migrations module.
    The migrations module is used as a template for creating the temporary
    migrations module. If it isn't provided, the application's migrations
    module is used, if it exists.
    Returns the filesystem path to the temporary migrations module.
    """
    marks = list(request.node.iter_markers(marker_name))
    if len(marks) != 1:
        raise ValueError(f"Expected exactly one {marker_name!r} marker")
    mark = marks[0]

    app_label = mark.kwargs["app_label"]
    module = mark.kwargs.get("module")

    source_module_path = module_dir(import_module(module))
    target_module = import_module(settings.MIGRATION_MODULES[app_label])
    target_module_path = module_dir(target_module)
    shutil.rmtree(target_module_path)
    shutil.copytree(source_module_path, target_module_path)
    yield MigrationPath(target_module_path)


@pytest.fixture(autouse=True)
def isolated_apps(settings, monkeypatch):
    """
    Django registers models in the apps cache, this is a helper to remove them, otherwise django throws warnings
    that this model already exists.
    """
    with ExitStack() as stack:
        original_apps = Options.default_apps
        original_all_models = original_apps.all_models
        original_app_configs = original_apps.app_configs
        new_all_models = defaultdict(dict)
        new_app_configs = {}

        monkeypatch.setattr("django.apps.apps.all_models", new_all_models)
        monkeypatch.setattr("django.apps.apps.app_configs", new_app_configs)
        monkeypatch.setattr("django.apps.apps.stored_app_configs", [])
        monkeypatch.setattr("django.apps.apps.apps_ready", False)
        monkeypatch.setattr("django.apps.apps.models_ready", False)
        monkeypatch.setattr("django.apps.apps.ready", False)
        monkeypatch.setattr("django.apps.apps.loading", False)
        monkeypatch.setattr("django.apps.apps._pending_operations", defaultdict(list))
        installed_app = settings.INSTALLED_APPS.copy()
        _installed_app = installed_app.copy()
        _installed_app.remove("django.contrib.auth")
        _installed_app.remove("django.contrib.contenttypes")
        original_apps.populate(_installed_app)

        for app_label in {"auth", "contenttypes"}:
            new_all_models[app_label] = original_all_models[app_label]
            new_app_configs[app_label] = original_app_configs[app_label]

        temp_dir = tempfile.TemporaryDirectory()
        stack.enter_context(temp_dir)
        stack.enter_context(extend_sys_path(temp_dir.name))
        with (Path(temp_dir.name) / "__init__.py").open("w"):
            pass

        for app_label in installed_app:
            target_dir = tempfile.mkdtemp(prefix=f"{app_label}_", dir=temp_dir.name)
            with (Path(target_dir) / "__init__.py").open("w"):
                pass
            migration_path = os.path.join(target_dir, "migrations")
            os.mkdir(migration_path)
            with (Path(migration_path) / "__init__.py").open("w"):
                pass
            module_name = f"{os.path.basename(target_dir)}.migrations"

            settings.MIGRATION_MODULES[app_label] = module_name
            stack.enter_context(extend_sys_path(target_dir))

        yield original_apps


@pytest.fixture
def call_squash_migrations():
    """
    Returns a function that calls squashmigrations.
    """
    def _call_squash_migrations(*args, **kwargs):
        kwargs["verbosity"] = kwargs.get("verbosity", 1)
        kwargs["no_color"] = kwargs.get("no_color", True)

        call_command("squash_migrations", *args, **kwargs)

    yield _call_squash_migrations


@pytest.fixture(autouse=True)
def clear_get_custom_rename_function_cache():
    """
    To ensure that this function doesn't get cached with the wrong value and breaks tests,
    we always clear it before and after each test.
    """
    get_custom_rename_function.cache_clear()
    yield
    get_custom_rename_function.cache_clear()


@pytest.fixture
def clean_db(django_db_blocker):
    """
    Clean the database after each test. As in a new database.

    Usage:

        @pytest.mark.usefixtures("clean_db")
        @pytest.mark.django_db(transaction=True)
        def test_something():
            ...
    """
    with django_db_blocker.unblock():
        # Because we're using an in memory sqlite database, we can just reset the connection
        # When the connection is reestablished, the database will be empty
        connections["default"].connection.close()
        del connections["default"]

        with connections["default"].cursor() as c:
            # make sure the database is of any tables
            assert connections["default"].introspection.get_table_list(c) == []

        yield
