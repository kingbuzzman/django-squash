import io
import os
import shutil
import tempfile
from contextlib import contextmanager
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import connections, models
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import extend_sys_path
from django.utils.module_loading import module_dir


class MigrationTestBase(TransactionTestCase):

    def tearDown(self):
        # Reset applied-migrations state.
        for db in connections:
            recorder = MigrationRecorder(connections[db])

    def assertTableExists(self, table, using='default'):
        with connections[using].cursor() as cursor:
            self.assertIn(table, connections[using].introspection.table_names(cursor))

    def assertTableNotExists(self, table, using='default'):
        with connections[using].cursor() as cursor:
            self.assertNotIn(table, connections[using].introspection.table_names(cursor))

    @contextmanager
    def temporary_migration_module(self, app_label='app', module=None, join=False):
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
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = tempfile.mkdtemp(dir=temp_dir)
            with open(os.path.join(target_dir, '__init__.py'), 'w'):
                pass
            target_migrations_dir = os.path.join(target_dir, 'migrations')

            if module is None:
                module = apps.get_app_config(app_label).name + '.migrations'

            try:
                source_migrations_dir = module_dir(import_module(module))
            except (ImportError, ValueError):
                pass
            else:
                shutil.copytree(source_migrations_dir, target_migrations_dir)

            with extend_sys_path(temp_dir):
                new_module = os.path.basename(target_dir) + '.migrations'
                modules = {app_label: new_module}
                if join:
                    modules.update(settings.MIGRATION_MODULES)
                with self.settings(MIGRATION_MODULES=modules):
                    yield target_migrations_dir


class MigrationTest(MigrationTestBase):
    available_apps = ['app', 'app2', 'django_squash']
    # databases = {'default'}

    # @override_settings(MIGRATION_MODULES={'app': 'app.test_simple_migrations'})
    # def test_normal_migration(self):
    #     # No tables are created
    #     self.assertTableNotExists('app_person')
    #
    #     stdout = io.StringIO()
    #     call_command('migrate', 'app', verbosity=1, stdout=stdout, no_color=True)
    #     self.assertTableExists('app_person')

    # @override_settings(MIGRATION_MODULES={'app': 'app.test_simple_migrations'})
    def test_squashing_migration(self):
        class Person(models.Model):
            name = models.CharField(max_length=10)
            dob = models.DateField()
            # place_of_birth = models.CharField(max_length=100, blank=True)

            class Meta:
                app_label = "app"

        # class Address(models.Model):
        #     person = models.ForeignKey('app.Person', on_delete=models.deletion.CASCADE)
        #     address1 = models.CharField(max_length=100)
        #     address2 = models.CharField(max_length=100)
        #     city = models.CharField(max_length=50)
        #     postal_code = models.CharField(max_length=50)
        #     province = models.CharField(max_length=50)
        #     country = models.CharField(max_length=50)
        #
        #     class Meta:
        #         app_label = "app2"

        out = io.StringIO()
        with self.temporary_migration_module(module="app.test_simple_migrations", app_label='app') as xx: #, \
             # self.temporary_migration_module(module="app2.test_foreignKey_migrations", app_label='app2', join=True) as yy:
            # call_command("makemigrations", "app", interactive=False, stdout=out)
            call_command('squash_migrations', verbosity=1, stdout=out, no_color=True)
