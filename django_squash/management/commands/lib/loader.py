from django.db.migrations.loader import MigrationLoader
from django.apps import apps
import os
import inspect, copy
import tempfile
from contextlib import ExitStack
from django.conf import settings


class SquashMigrationLoader(MigrationLoader):
    pass
    # def load_disk(self):
    #     project_path = os.path.abspath(os.curdir)
    #     original_migration_modules = settings.MIGRATION_MODULES.copy()
    #
    #     with ExitStack() as stack:
    #         for app_config in apps.get_app_configs():
    #             module = app_config.module
    #             app_path = inspect.getsourcefile(module)
    #             if app_path.startswith(project_path):
    #                 temp_dir = stack.enter_context(tempfile.TemporaryDirectory())
    #                 settings.MIGRATION_MODULES[app_config.label] = temp_dir
    #                 # # If there is no __init__.py django refuses to pick it up or even attempt to write to it.
    #                 # open(os.path.join(temp_dir, '__init__.py'), 'a').close()
    #
    #         super().load_disk()
    #
    #     settings.MIGRATION_MODULES = original_migration_modules
