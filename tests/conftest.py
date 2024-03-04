import io
import os
import shutil
import sys
import tempfile
from collections import defaultdict
from contextlib import ExitStack
from importlib import import_module
from types import ModuleType

import pytest
from django.apps import apps
from django.conf import settings as django_settings
from django.core.management import call_command
from django.test.utils import extend_sys_path
from django.db.models.options import Options
from django.apps.registry import Apps
from django.utils.module_loading import import_string, module_dir

INSTALLED_APPS = django_settings.INSTALLED_APPS.copy()


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
    mark = next(request.node.iter_markers(marker_name))

    app_label = mark.kwargs["app_label"]
    module = mark.kwargs.get("module")
    join = mark.kwargs.get("join") or False

    # with tempfile.TemporaryDirectory() as temp_dir:
    #     target_dir = tempfile.mkdtemp(dir=temp_dir)
    #     with open(os.path.join(target_dir, "__init__.py"), "w"):
    #         pass
    #     target_migrations_dir = os.path.join(target_dir, "migrations")

    #     if module is None:
    #         module = apps.get_app_config(app_label).name + ".migrations"

    #     try:
    #         source_migrations_dir = module_dir(import_module(module))
    #     except (ImportError, ValueError):
    #         pass
    #     else:
    #         shutil.copytree(source_migrations_dir, target_migrations_dir)

    #     with extend_sys_path(temp_dir):
    #         new_module = os.path.basename(target_dir) + ".migrations"
    #         modules = {app_label: new_module}
    #         if join:
    #             modules.update(settings.MIGRATION_MODULES)
    #         settings.MIGRATION_MODULES = modules
    #         yield target_migrations_dir

    source_module_path = module_dir(import_module(module))
    target_module = import_module(settings.MIGRATION_MODULES[app_label])
    target_module_path = module_dir(target_module)
    shutil.rmtree(target_module_path)
    shutil.copytree(source_module_path, target_module_path)
    yield target_module_path


# @pytest.fixture(autouse=True)
# def _set_missing_migration_app_dir(settings):
#     for settings.INSTALLED_APPS

class BidirectionalProxy:
    def __init__(self, primary_target, secondary_target, *attrs_to_proxy):
        super().__setattr__('_primary_target', primary_target)
        super().__setattr__('_secondary_target', secondary_target)
        super().__setattr__('_attrs_to_proxy', set(attrs_to_proxy))

    def __getattr__(self, name):
        if name in self._attrs_to_proxy:
            return getattr(self._primary_target, name)
        else:
            return super().__getattribute__(name)

    def __setattr__(self, name, value):
        if name in self._attrs_to_proxy:
            setattr(self._primary_target, name, value)
            setattr(self._secondary_target, name, value)
        else:
            super().__setattr__(name, value)

    def __delattr__(self, name):
        if name in self._attrs_to_proxy:
            delattr(self._primary_target, name)
            delattr(self._secondary_target, name)
        else:
            super().__delattr__(name)


@pytest.fixture(autouse=True)
def isolated_apps(settings, monkeypatch, request):
    """
    Django registers models in the apps cache, this is a helper to remove them, otherwise django throws warnings
    that this model already exists.
    """
    with ExitStack() as stack: #, isolate_apps(*INSTALLED_APPS) as new_apps:
        # monkeypatch.setattr("django_squash.management.commands.squash_migrations.apps", new_apps)
        # monkeypatch.setattr("django.test.utils.apps", new_apps)
        # monkeypatch.setattr("django.db.models.base.apps", new_apps)
        # monkeypatch.setattr("django.contrib.auth.django_apps", new_apps)
        # monkeypatch.setattr("django.db.migrations.loader.apps", new_apps)
        # monkeypatch.setattr("django.db.migrations.writer.apps", new_apps)

        # new_apps = Apps()
        # print('models', Options.default_apps.all_models)
        # print('app_configs', Options.default_apps.app_configs)
        # print('stored_app_configs', Options.default_apps.stored_app_configs)
        original_apps = Options.default_apps
        original_all_models = original_apps.all_models
        original_app_configs = original_apps.app_configs
        new_all_models = defaultdict(dict)
        new_app_configs = {}

        # monkeypatch.setattr(Options, "default_apps", new_apps)
        # monkeypatch.setattr("django.apps.apps", new_apps.all_models)
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
        _installed_app.remove('django.contrib.auth')
        _installed_app.remove('django.contrib.contenttypes')
        original_apps.populate(_installed_app)

        for app_label in {'auth', 'contenttypes'}:
            new_all_models[app_label] = original_all_models[app_label]
            new_app_configs[app_label] = original_app_configs[app_label]

        temp_dir = tempfile.TemporaryDirectory()
        stack.enter_context(temp_dir)
        stack.enter_context(extend_sys_path(temp_dir.name))
        with open(os.path.join(temp_dir.name, "__init__.py"), "w"):
            pass

        for app_label in installed_app:
            target_dir = tempfile.mkdtemp(prefix=f"{app_label}_", dir=temp_dir.name)
            with open(os.path.join(target_dir, "__init__.py"), "w"):
                pass
            migration_path = os.path.join(target_dir, "migrations")
            os.mkdir(migration_path)
            with open(os.path.join(migration_path, "__init__.py"), "w"):
                pass
            module_name = f"{os.path.basename(target_dir)}.migrations"

            settings.MIGRATION_MODULES[app_label] = module_name
            stack.enter_context(extend_sys_path(target_dir))

        yield original_apps

    return
    # from unittest import mock
    # mock_ = mock.Mock()
    # monkeypatch.setattr("django.apps.registry.apps.get_model", mock_)

    # # Reset App variables
    # apps.all_models = defaultdict(dict)
    # apps.app_configs = {}
    # apps.stored_app_configs = []
    # apps.apps_ready = apps.models_ready = apps.ready = False
    # apps.loading = False
    # apps._pending_operations = defaultdict(list)
    # # Start fresh
    # apps.populate(INSTALLED_APPS)

    import itertools

    print(list(itertools.chain.from_iterable(apps.all_models.values())))

    yield

    print(list(itertools.chain.from_iterable(apps.all_models.values())))


@pytest.fixture
def call_squash_migrations():
    """
    Returns a function that calls squashmigrations.
    """
    output = io.StringIO()

    def _call_squash_migrations(*args, **kwargs):
        kwargs["verbosity"] = kwargs.get("verbosity", 1)
        kwargs["stdout"] = kwargs.get("stdout", output)
        kwargs["no_color"] = kwargs.get("no_color", True)

        call_command("squash_migrations", *args, **kwargs)

    yield _call_squash_migrations
