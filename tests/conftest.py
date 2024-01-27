import pytest
import io
import os
import shutil
import tempfile
from importlib import import_module
from unittest import mock

from django.apps import apps
from django.core.management import call_command
from django.test.utils import extend_sys_path
from django.utils.module_loading import module_dir


@pytest.fixture
def migration_app_dir(request, settings):
    yield from _migration_app_dir("temporary_migration_module", request, settings)


@pytest.fixture
def migration_app2_dir(request, settings):
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

    with tempfile.TemporaryDirectory() as temp_dir:
        target_dir = tempfile.mkdtemp(dir=temp_dir)
        with open(os.path.join(target_dir, "__init__.py"), "w"):
            pass
        target_migrations_dir = os.path.join(target_dir, "migrations")

        if module is None:
            module = apps.get_app_config(app_label).name + ".migrations"

        try:
            source_migrations_dir = module_dir(import_module(module))
        except (ImportError, ValueError):
            pass
        else:
            shutil.copytree(source_migrations_dir, target_migrations_dir)

        with extend_sys_path(temp_dir):
            new_module = os.path.basename(target_dir) + ".migrations"
            modules = {app_label: new_module}
            if join:
                modules.update(settings.MIGRATION_MODULES)
            settings.MIGRATION_MODULES = modules
            yield target_migrations_dir


@pytest.fixture(autouse=True)
def _clean_model(monkeypatch):
    """
    Django registers models in the apps cache, this is a helper to remove them, otherwise django throws warnings
    that this model already exists.
    """
    mock_register_model = mock.Mock(wraps=apps.register_model)
    monkeypatch.setattr(apps, "register_model", mock_register_model)

    yield

    for call in mock_register_model.call_args_list:
        app_label, model = call.args
        model_name = model._meta.model_name
        app_models = apps.all_models[app_label]
        app_models.pop(model_name)
        apps.clear_cache()


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
