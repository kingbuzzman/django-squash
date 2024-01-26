import inspect
import os
import tempfile
from contextlib import ExitStack

from django.apps import apps
from django.conf import settings
from django.db.migrations.loader import MigrationLoader


class SquashMigrationLoader(MigrationLoader):
    def __init__(self, *args, **kwargs):
        original_migration_modules = settings.MIGRATION_MODULES.copy()
        project_path = os.path.abspath(os.curdir)

        with ExitStack() as stack:
            # Find each app that belongs to the user and are not in the site-packages. Create a fake temporary
            # directory inside each app that will tell django we don't have any migrations at all.
            for app_config in apps.get_app_configs():
                module = app_config.module
                app_path = os.path.dirname(os.path.abspath(inspect.getsourcefile(module)))

                if app_path.startswith(project_path):
                    temp_dir = stack.enter_context(tempfile.TemporaryDirectory(prefix='migrations_', dir=app_path))
                    # Need to make this directory a proper python module otherwise django will refuse to recognize it
                    open(os.path.join(temp_dir, '__init__.py'), 'a').close()
                    settings.MIGRATION_MODULES[app_config.label] = '%s.%s' % (app_config.module.__name__,
                                                                              os.path.basename(temp_dir))

            super().__init__(*args, **kwargs)

        settings.MIGRATION_MODULES = original_migration_modules
