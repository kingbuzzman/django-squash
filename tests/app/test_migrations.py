import importlib.util
import io
import os
import shutil
import tempfile
from contextlib import contextmanager
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import connections, migrations as migrations_module, models
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from django.test.utils import extend_sys_path
from django.utils.module_loading import module_dir


class MigrationTestBase(TransactionTestCase):
    """
    Partial copy from the django source, can't subclass it
    https://github.com/django/django/blob/b9cf764be62e77b4777b3a75ec256f6209a57671/tests/migrations/test_base.py#L15
    """

    def tearDown(self):
        # Reset applied-migrations state.
        for db in connections:
            MigrationRecorder(connections[db])

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


def load_migration_module(path):
    spec = importlib.util.spec_from_file_location("__module__", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pretty_operation(operation):
    kwargs = {}
    if isinstance(operation, migrations_module.RunSQL):
        sql = operation.sql.strip()
        kwargs['sql'] = sql[:10] + '..' if len(sql) > 10 else sql
        if operation.reverse_sql:
            reverse_sql = operation.reverse_sql.strip()
            kwargs['reverse_sql'] = reverse_sql[:10] + '..' if len(reverse_sql) > 10 else reverse_sql
        kwargs['elidable'] = operation.elidable
    elif isinstance(operation, migrations_module.RunPython):
        kwargs['code'] = operation.code.__name__
        if operation.reverse_code:
            kwargs['reverse_code'] = operation.reverse_code.__name__
        kwargs['elidable'] = operation.elidable
    return '%s(%s)' % (type(operation).__name__, ', '.join('%s=%s' % (k, v) for k, v in kwargs.items()))


class SquashMigrationTest(MigrationTestBase):
    available_apps = ['app', 'app2', 'app3', 'django_squash']

    def test_squashing_elidable_migration_simple(self):
        class Person(models.Model):
            name = models.CharField(max_length=10)
            dob = models.DateField()

            class Meta:
                app_label = "app"

        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(module="app.test_elidable_migrations", app_label='app')
        with patch_app_migrations as migration_app_dir:
            call_command('squash_migrations', verbosity=1, stdout=out, no_color=True)

            files_in_app = os.listdir(migration_app_dir)
            self.assertIn('0004_squashed.py', files_in_app)

            app_squash = load_migration_module(os.path.join(migration_app_dir, '0004_squashed.py'))

        # Test imports
        self.assertTrue(hasattr(app_squash, 'randrange'))
        self.assertTrue(hasattr(app_squash, 'itertools'))

        self.assertEqual(app_squash.create_admin_MUST_ALWAYS_EXIST.__doc__,
                         '\n    This is a test doc string\n    ')

        self.assertEqual(app_squash.rollback_admin_MUST_ALWAYS_EXIST.__doc__, 'Single comments')

        self.assertEqual(app_squash.Migration.replaces, [('app', '0001_initial'),
                                                         ('app', '0002_person_age'),
                                                         ('app', '0003_add_dob')])

        actual = [pretty_operation(migration) for migration in app_squash.Migration.operations]
        self.assertEqual(actual, ['CreateModel()',
                                  ('RunPython(code=create_admin_MUST_ALWAYS_EXIST, '
                                   'reverse_code=rollback_admin_MUST_ALWAYS_EXIST, elidable=False)'),
                                  'RunSQL(sql=select 1, reverse_sql=select 2, elidable=False)'])

    def test_squashing_migration_simple(self):
        class Person(models.Model):
            name = models.CharField(max_length=10)
            dob = models.DateField()
            # place_of_birth = models.CharField(max_length=100, blank=True)

            class Meta:
                app_label = "app"

        class Address(models.Model):
            person = models.ForeignKey('app.Person', on_delete=models.deletion.CASCADE)
            address1 = models.CharField(max_length=100)
            address2 = models.CharField(max_length=100)
            city = models.CharField(max_length=50)
            postal_code = models.CharField(max_length=50)
            province = models.CharField(max_length=50)
            country = models.CharField(max_length=50)

            class Meta:
                app_label = "app2"

        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(module="app.test_simple_migrations", app_label='app')
        patch_app2_migrations = self.temporary_migration_module(module="app2.test_foreignKey_migrations",
                                                                app_label='app2', join=True)
        with patch_app_migrations as migration_app_dir, patch_app2_migrations as migration_app2_dir:
            call_command('squash_migrations', verbosity=1, stdout=out, no_color=True)

            files_in_app = os.listdir(migration_app_dir)
            files_in_app2 = os.listdir(migration_app2_dir)
            self.assertIn('0004_squashed.py', files_in_app)
            self.assertIn('0002_squashed.py', files_in_app2)

            app_squash = load_migration_module(os.path.join(migration_app_dir, '0004_squashed.py'))
            app2_squash = load_migration_module(os.path.join(migration_app2_dir, '0002_squashed.py'))

            self.assertEqual(app_squash.Migration.replaces, [('app', '0001_initial'),
                                                             ('app', '0002_person_age'),
                                                             ('app', '0003_auto_20190518_1524')])

            self.assertEqual(app2_squash.Migration.replaces, [('app2', '0001_initial')])

    def test_squashing_migration_empty(self):
        class Person(models.Model):
            name = models.CharField(max_length=10)
            dob = models.DateField()

            class Meta:
                app_label = "app"

        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(module="app.test_empty", app_label='app')
        catch_error = self.assertRaisesMessage(CommandError, "There are no migrations to squash.")
        with patch_app_migrations, catch_error:
            call_command('squash_migrations', verbosity=1, stdout=out, no_color=True)

    def test_invalid_apps(self):
        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(module="app.test_empty", app_label='app')
        catch_error = self.assertRaisesMessage(CommandError, "The following apps are not valid: a, b")
        with patch_app_migrations, catch_error:
            call_command('squash_migrations', verbosity=1, stdout=out, no_color=True, ignore_app=['a', 'b'])

    def test_simple_delete_squashing_migrations_noop(self):
        class Person(models.Model):
            name = models.CharField(max_length=10)
            dob = models.DateField()

            class Meta:
                app_label = "app"

        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(module="app.test_elidable_migrations", app_label='app')
        with patch_app_migrations as migration_app_dir:
            call_command('squash_migrations', verbosity=1, stdout=out, no_color=True)

            files_in_app = sorted(file for file in os.listdir(migration_app_dir) if file.endswith('.py'))
        expected = ['0001_initial.py', '0002_person_age.py', '0003_add_dob.py', '0004_squashed.py', '__init__.py']
        self.assertEqual(files_in_app, expected)

    def test_simple_delete_squashing_migrations(self):
        class Person(models.Model):
            name = models.CharField(max_length=10)
            dob = models.DateField()

            class Meta:
                app_label = "app"

        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(module="app.test_delete_replaced_migrations",
                                                               app_label='app')
        with patch_app_migrations as migration_app_dir:
            original_app_squash = load_migration_module(os.path.join(migration_app_dir, '0004_squashed.py'))
            self.assertEqual(original_app_squash.Migration.replaces, [('app', '0001_initial'),
                                                                      ('app', '0002_person_age'),
                                                                      ('app', '0003_add_dob')])

            call_command('squash_migrations', verbosity=1, stdout=out, no_color=True)

            files_in_app = sorted(file for file in os.listdir(migration_app_dir) if file.endswith('.py'))
            old_app_squash = load_migration_module(os.path.join(migration_app_dir, '0004_squashed.py'))
            new_app_squash = load_migration_module(os.path.join(migration_app_dir, '0005_squashed.py'))

        # We altered an existing file, and removed all the "replaces" items
        self.assertEqual(old_app_squash.Migration.replaces, [])
        # The new squashed migration replaced the old one now
        self.assertEqual(new_app_squash.Migration.replaces, [('app', '0004_squashed')])
        self.assertEqual(files_in_app, ['0004_squashed.py', '0005_squashed.py', '__init__.py'])

    def test_empty_models_migrations(self):
        """
        If apps are moved but migrations remain, a fake migration must be made that does nothing and replaces the
        existing migrations, that way django doesn't throw errors when trying to do the same work again.
        """
        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(module="app3.test_moved_migrations",
                                                               app_label='app3')
        with patch_app_migrations as migration_app_dir:
            call_command('squash_migrations', verbosity=1, stdout=out, no_color=True)
            files_in_app = sorted(file for file in os.listdir(migration_app_dir) if file.endswith('.py'))
            self.assertIn('0004_squashed.py', files_in_app)
            app_squash = load_migration_module(os.path.join(migration_app_dir, '0004_squashed.py'))
        expected_files = ['0001_initial.py', '0002_person_age.py', '0003_moved.py', '0004_squashed.py', '__init__.py']
        self.assertEqual(files_in_app, expected_files)
        self.assertEqual(app_squash.Migration.replaces, [('app3', '0001_initial'),
                                                         ('app3', '0002_person_age'),
                                                         ('app3', '0003_moved')])
