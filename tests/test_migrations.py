import importlib.util
import inspect
import io
import os
import shutil
import tempfile
import textwrap
import unittest.mock
from contextlib import contextmanager
from importlib import import_module

import libcst
import black
from django.apps import apps
from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import connections, models
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase, override_settings
from django.test.utils import extend_sys_path
from django.utils.module_loading import module_dir


def clean_model(model):
    """
    Django registers models in the apps cache, this is a helper to remove them
    """
    model_name = model._meta.model_name
    app_label = model._meta.app_label
    app_models = apps.all_models[app_label]
    app_models.pop(model_name)
    apps.clear_cache()


class MigrationTestBase(TransactionTestCase):
    """
    Partial copy from the django source, can't subclass it
    https://github.com/django/django/blob/b9cf764be62e77b4777b3a75ec256f6209a57671/tests/migrations/test_base.py#L15
    """

    def tearDown(self):
        # Reset applied-migrations state.
        for db in connections:
            MigrationRecorder(connections[db])

    def addModelCleanup(self, model):
        # See clean_model for why we need to do this.
        self.addCleanup(clean_model, model)

    def assertTableExists(self, table, using="default"):
        with connections[using].cursor() as cursor:
            self.assertIn(table, connections[using].introspection.table_names(cursor))

    def assertTableNotExists(self, table, using="default"):
        with connections[using].cursor() as cursor:
            self.assertNotIn(
                table, connections[using].introspection.table_names(cursor)
            )

    @contextmanager
    def temporary_migration_module(self, app_label="app", module=None, join=False):
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
                with self.settings(MIGRATION_MODULES=modules):
                    yield target_migrations_dir


def load_migration_module(path):
    spec = importlib.util.spec_from_file_location("__module__", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        with open(path) as f:
            raise type(e)(
                "Error loading module file containing:\n\n%s" % f.read()
            ) from e
    return module


def pretty_extract_piece(module, traverse):
    """Format the code extracted from the module, so it can be compared to the expected output"""
    return format_code(extract_piece(module, traverse))


def extract_piece(module, traverse):
    """Extract a piece of code from a module"""
    source_code = inspect.getsource(module)
    tree = libcst.parse_module(source_code).body

    for looking_for in traverse.split("."):
        if looking_for:
            tree = traverse_node(tree, looking_for)

    if not isinstance(tree, tuple):
        tree = (tree,)
    return libcst.Module(body=tree).code


def format_code(code_string):
    """Format the code so it's reproducible"""
    mode = black.FileMode(line_length=10_000)
    return black.format_str(code_string, mode=mode)


def traverse_node(nodes, looking_for):
    """Traverse the tree looking for a node"""
    if not isinstance(nodes, (list, tuple)):
        nodes = [nodes]

    for node in nodes:
        if (
            isinstance(node, (libcst.ClassDef, libcst.FunctionDef))
            and node.name.value == looking_for
        ):
            return node
        if isinstance(node, libcst.Assign) and looking_for in [
            n.target.value for n in node.targets
        ]:
            return node

        for child in node.children:
            result = traverse_node(child, looking_for)
            if result:
                return result


class SquashMigrationTest(MigrationTestBase):
    available_apps = ["app", "app2", "app3", "django_squash"]

    maxDiff = None

    def test_squashing_elidable_migration_simple(self):
        class Person(models.Model):
            name = models.CharField(max_length=10)
            dob = models.DateField()

            class Meta:
                app_label = "app"

        self.addModelCleanup(Person)

        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(
            module="app.tests.migrations.elidable", app_label="app"
        )
        with patch_app_migrations as migration_app_dir:
            call_command("squash_migrations", verbosity=1, stdout=out, no_color=True)

            files_in_app = os.listdir(migration_app_dir)
            self.assertIn("0004_squashed.py", files_in_app)

            app_squash = load_migration_module(
                os.path.join(migration_app_dir, "0004_squashed.py")
            )
            expected = textwrap.dedent(
                """\
                import datetime
                import itertools
                from django.db import migrations
                from django.db import migrations, models
                from random import randrange


                def same_name(apps, schema_editor):
                    \"\"\"
                    Content not important, testing same function name in multiple migrations
                    \"\"\"
                    pass


                def same_name_2(apps, schema_editor):
                    \"\"\"
                    Content not important, testing same function name in multiple migrations, nasty
                    \"\"\"
                    pass


                def create_admin_MUST_ALWAYS_EXIST(apps, schema_editor):
                    \"\"\"
                    This is a test doc string
                    \"\"\"
                    itertools.chain()  # noop used to make sure the import was included
                    randrange  # noop used to make sure the import was included

                    Person = apps.get_model("app", "Person")

                    Person.objects.get_or_create(name="admin", age=30)


                def rollback_admin_MUST_ALWAYS_EXIST(apps, schema_editor):
                    \"\"\"Single comments\"\"\"
                    print("Ignoring, there is no need to do this.")


                def same_name_3(apps, schema_editor):
                    \"\"\"
                    Content not important, testing same function name in multiple migrations, second function
                    \"\"\"
                    pass


                SQL_1 = \"\"\"
                select 1
                \"\"\"

                SQL_1_ROLLBACK = \"\"\"
                select 2
                \"\"\"

                SQL_2 = \"\"\"
                select 4
                \"\"\"


                class Migration(migrations.Migration):

                    replaces = [("app", "0001_initial"), ("app", "0002_person_age"), ("app", "0003_add_dob")]

                    initial = True

                    dependencies = []

                    operations = [
                        migrations.CreateModel(
                            name="Person",
                            fields=[
                                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                                ("name", models.CharField(max_length=10)),
                                ("dob", models.DateField()),
                            ],
                        ),
                        migrations.RunPython(
                            code=same_name,
                            elidable=False,
                        ),
                        migrations.RunPython(
                            code=same_name_2,
                            reverse_code=migrations.RunPython.noop,
                            elidable=False,
                        ),
                        migrations.RunPython(
                            code=create_admin_MUST_ALWAYS_EXIST,
                            reverse_code=rollback_admin_MUST_ALWAYS_EXIST,
                            elidable=False,
                        ),
                        migrations.RunPython(
                            code=same_name_3,
                            elidable=False,
                        ),
                        migrations.RunSQL(
                            sql=SQL_1,
                            reverse_sql=SQL_1_ROLLBACK,
                            elidable=False,
                        ),
                        migrations.RunSQL(
                            sql=SQL_2,
                            elidable=False,
                        ),
                    ]
                """  # noqa
            )
            self.assertEqual(pretty_extract_piece(app_squash, ""), expected)

    def test_squashing_migration_simple(self):
        class Person(models.Model):
            name = models.CharField(max_length=10)
            dob = models.DateField()
            # place_of_birth = models.CharField(max_length=100, blank=True)

            class Meta:
                app_label = "app"

        self.addModelCleanup(Person)

        class Address(models.Model):
            person = models.ForeignKey("app.Person", on_delete=models.deletion.CASCADE)
            address1 = models.CharField(max_length=100)
            address2 = models.CharField(max_length=100)
            city = models.CharField(max_length=50)
            postal_code = models.CharField(max_length=50)
            province = models.CharField(max_length=50)
            country = models.CharField(max_length=50)

            class Meta:
                app_label = "app2"

        self.addModelCleanup(Address)

        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(
            module="app.tests.migrations.simple", app_label="app"
        )
        patch_app2_migrations = self.temporary_migration_module(
            module="app2.tests.migrations.foreign_key", app_label="app2", join=True
        )
        with patch_app_migrations as migration_app_dir, patch_app2_migrations as migration_app2_dir:
            call_command("squash_migrations", verbosity=1, stdout=out, no_color=True)

            files_in_app = os.listdir(migration_app_dir)
            files_in_app2 = os.listdir(migration_app2_dir)
            self.assertIn("0004_squashed.py", files_in_app)
            self.assertIn("0002_squashed.py", files_in_app2)

            app_squash = load_migration_module(
                os.path.join(migration_app_dir, "0004_squashed.py")
            )
            app2_squash = load_migration_module(
                os.path.join(migration_app2_dir, "0002_squashed.py")
            )

            self.assertEqual(
                app_squash.Migration.replaces,
                [
                    ("app", "0001_initial"),
                    ("app", "0002_person_age"),
                    ("app", "0003_auto_20190518_1524"),
                ],
            )

            self.assertEqual(app2_squash.Migration.replaces, [("app2", "0001_initial")])

    def test_squashing_migration_empty(self):
        class Person(models.Model):
            name = models.CharField(max_length=10)
            dob = models.DateField()

            class Meta:
                app_label = "app"

        self.addModelCleanup(Person)

        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(
            module="app.test_empty", app_label="app"
        )
        catch_error = self.assertRaisesMessage(
            CommandError, "There are no migrations to squash."
        )
        with patch_app_migrations, catch_error:
            call_command("squash_migrations", verbosity=1, stdout=out, no_color=True)

    def test_invalid_apps(self):
        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(
            module="app.test_empty", app_label="app"
        )
        catch_error = self.assertRaisesMessage(
            CommandError, "The following apps are not valid: a, b"
        )
        with patch_app_migrations, catch_error:
            call_command(
                "squash_migrations",
                "--ignore-app",
                "a",
                "b",
                verbosity=1,
                stdout=out,
                no_color=True,
            )

    def test_ignore_apps_argument(self):
        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(
            module="app.test_empty", app_label="app"
        )

        with unittest.mock.patch(
            target="django_squash.db.migrations.autodetector.SquashMigrationAutodetector.squash",
            autospec=True,
        ) as squash_mock, patch_app_migrations:
            with self.assertRaisesMessage(
                CommandError, "There are no migrations to squash."
            ):
                call_command(
                    "squash_migrations",
                    "--ignore-app",
                    "app2",
                    "app",
                    verbosity=1,
                    stdout=out,
                    no_color=True,
                )
            self.assertEqual(
                set(squash_mock.call_args[1]["ignore_apps"]), {"app2", "app"}
            )

    def test_only_argument(self):
        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(
            module="app.test_empty", app_label="app"
        )

        with unittest.mock.patch(
            target="django_squash.db.migrations.autodetector.SquashMigrationAutodetector.squash",
            autospec=True,
        ) as squash_mock, patch_app_migrations:
            with self.assertRaisesMessage(
                CommandError, "There are no migrations to squash."
            ):
                call_command(
                    "squash_migrations",
                    "--only",
                    "app2",
                    "app",
                    verbosity=1,
                    stdout=out,
                    no_color=True,
                )
            self.assertEqual(
                set(squash_mock.call_args[1]["ignore_apps"]),
                set(self.available_apps) - {"app", "app2"},
            )

    def test_only_argument_with_invalid_apps(self):
        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(
            module="app.test_empty", app_label="app"
        )

        with unittest.mock.patch(
            target="django_squash.db.migrations.autodetector.SquashMigrationAutodetector.squash",
            autospec=True,
        ) as squash_mock, patch_app_migrations:
            with self.assertRaisesMessage(
                CommandError, "The following apps are not valid: invalid"
            ):
                call_command(
                    "squash_migrations",
                    "--only",
                    "app2",
                    "invalid",
                    verbosity=1,
                    stdout=out,
                    no_color=True,
                )
            self.assertFalse(squash_mock.called)

    def test_simple_delete_squashing_migrations_noop(self):
        class Person(models.Model):
            name = models.CharField(max_length=10)
            dob = models.DateField()

            class Meta:
                app_label = "app"

        self.addModelCleanup(Person)

        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(
            module="app.tests.migrations.elidable", app_label="app"
        )
        with patch_app_migrations as migration_app_dir:
            call_command("squash_migrations", verbosity=1, stdout=out, no_color=True)

            files_in_app = sorted(
                file for file in os.listdir(migration_app_dir) if file.endswith(".py")
            )
        expected = [
            "0001_initial.py",
            "0002_person_age.py",
            "0003_add_dob.py",
            "0004_squashed.py",
            "__init__.py",
        ]
        self.assertEqual(files_in_app, expected)

    def test_simple_delete_squashing_migrations(self):
        class Person(models.Model):
            name = models.CharField(max_length=10)
            dob = models.DateField()

            class Meta:
                app_label = "app"

        self.addModelCleanup(Person)

        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(
            module="app.tests.migrations.delete_replaced", app_label="app"
        )
        with patch_app_migrations as migration_app_dir:
            original_app_squash = load_migration_module(
                os.path.join(migration_app_dir, "0004_squashed.py")
            )
            self.assertEqual(
                original_app_squash.Migration.replaces,
                [
                    ("app", "0001_initial"),
                    ("app", "0002_person_age"),
                    ("app", "0003_add_dob"),
                ],
            )

            call_command("squash_migrations", verbosity=1, stdout=out, no_color=True)

            files_in_app = sorted(
                file for file in os.listdir(migration_app_dir) if file.endswith(".py")
            )
            old_app_squash = load_migration_module(
                os.path.join(migration_app_dir, "0004_squashed.py")
            )
            new_app_squash = load_migration_module(
                os.path.join(migration_app_dir, "0005_squashed.py")
            )

        # We altered an existing file, and removed all the "replaces" items
        self.assertEqual(old_app_squash.Migration.replaces, [])
        # The new squashed migration replaced the old one now
        self.assertEqual(new_app_squash.Migration.replaces, [("app", "0004_squashed")])
        self.assertEqual(
            files_in_app, ["0004_squashed.py", "0005_squashed.py", "__init__.py"]
        )

    def test_empty_models_migrations(self):
        """
        If apps are moved but migrations remain, a fake migration must be made that does nothing and replaces the
        existing migrations, that way django doesn't throw errors when trying to do the same work again.
        """
        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(
            module="app3.tests.migrations.moved", app_label="app3"
        )
        with patch_app_migrations as migration_app_dir:
            call_command("squash_migrations", verbosity=1, stdout=out, no_color=True)
            files_in_app = sorted(
                file for file in os.listdir(migration_app_dir) if file.endswith(".py")
            )
            self.assertIn("0004_squashed.py", files_in_app)
            app_squash = load_migration_module(
                os.path.join(migration_app_dir, "0004_squashed.py")
            )
        expected_files = [
            "0001_initial.py",
            "0002_person_age.py",
            "0003_moved.py",
            "0004_squashed.py",
            "__init__.py",
        ]
        self.assertEqual(files_in_app, expected_files)
        self.assertEqual(
            app_squash.Migration.replaces,
            [
                ("app3", "0001_initial"),
                ("app3", "0002_person_age"),
                ("app3", "0003_moved"),
            ],
        )

    def test_squashing_migration_incorrect_name(self):
        """
        If the app has incorrect migration numbers like: `app/migrations/initial.py` instead of `0001_initial.py`
        it should not fail. Same goes for bad formats all around.
        """

        class Person(models.Model):
            name = models.CharField(max_length=10)
            dob = models.DateField()

            class Meta:
                app_label = "app"

        self.addModelCleanup(Person)

        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(
            module="app.tests.migrations.incorrect_name", app_label="app"
        )
        with patch_app_migrations as migration_app_dir:
            call_command("squash_migrations", verbosity=1, stdout=out, no_color=True)

            files_in_app = os.listdir(migration_app_dir)
            self.assertIn("3001_squashed.py", files_in_app)

            app_squash = load_migration_module(
                os.path.join(migration_app_dir, "3001_squashed.py")
            )

            self.assertEqual(
                app_squash.Migration.replaces,
                [
                    ("app", "2_person_age"),
                    ("app", "3000_auto_20190518_1524"),
                    ("app", "bad_no_name"),
                    ("app", "initial"),
                ],
            )

    def test_run_python_same_name_migrations(self):
        out = io.StringIO()
        patch_app_migrations = self.temporary_migration_module(
            module="app.tests.migrations.run_python_noop", app_label="app"
        )
        with patch_app_migrations as migration_app_dir:
            call_command("squash_migrations", verbosity=1, stdout=out, no_color=True)
            files_in_app = sorted(
                file for file in os.listdir(migration_app_dir) if file.endswith(".py")
            )
            expected_files = [
                "0001_initial.py",
                "0002_run_python.py",
                "0003_squashed.py",
                "__init__.py",
            ]
            self.assertEqual(files_in_app, expected_files)

            app_squash = load_migration_module(
                os.path.join(migration_app_dir, "0003_squashed.py")
            )
            expected = textwrap.dedent(
                """\
                from django.db import migrations
                from django.db.migrations import RunPython
                from django.db.migrations.operations.special import RunPython


                def same_name(apps, schema_editor):
                    # original function
                    return


                def same_name_2(apps, schema_editor):
                    # original function 2
                    return


                def same_name_3(apps, schema_editor):
                    # other function
                    return


                class Migration(migrations.Migration):

                    replaces = [("app", "0001_initial"), ("app", "0002_run_python")]

                    dependencies = []

                    operations = [
                        migrations.RunPython(
                            code=same_name,
                            reverse_code=migrations.RunPython.noop,
                            elidable=False,
                        ),
                        migrations.RunPython(
                            code=migrations.RunPython.noop,
                            reverse_code=migrations.RunPython.noop,
                            elidable=False,
                        ),
                        migrations.RunPython(
                            code=same_name_2,
                            elidable=False,
                        ),
                        migrations.RunPython(
                            code=migrations.RunPython.noop,
                            elidable=False,
                        ),
                        migrations.RunPython(
                            code=same_name_3,
                            elidable=False,
                        ),
                    ]
                """  # noqa
            )
            self.assertEqual(pretty_extract_piece(app_squash, ""), expected)

    def test_swappable_dependency_migrations(self):
        out = io.StringIO()
        INSTALLED_APPS = settings.INSTALLED_APPS + [
            "django.contrib.auth",
            "django.contrib.contenttypes",
        ]
        patch_installed_apps = override_settings(INSTALLED_APPS=INSTALLED_APPS)
        patch_app_migrations = self.temporary_migration_module(
            module="app.tests.migrations.swappable_dependency", app_label="app"
        )

        class UserProfile(models.Model):
            user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
            dob = models.DateField()

            class Meta:
                app_label = "app"

        self.addModelCleanup(UserProfile)

        with patch_installed_apps, patch_app_migrations as migration_app_dir:
            call_command("squash_migrations", verbosity=1, stdout=out, no_color=True)
            files_in_app = sorted(
                file for file in os.listdir(migration_app_dir) if file.endswith(".py")
            )

            expected_files = [
                "0001_initial.py",
                "0002_add_dob.py",
                "0003_squashed.py",
                "__init__.py",
            ]
            self.assertEqual(files_in_app, expected_files)

            app_squash = load_migration_module(
                os.path.join(migration_app_dir, "0003_squashed.py")
            )
            expected = textwrap.dedent(
                """\
                import datetime
                from django.conf import settings
                from django.db import migrations, models


                class Migration(migrations.Migration):

                    replaces = [("app", "0001_initial"), ("app", "0002_add_dob")]

                    initial = True

                    dependencies = [
                        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
                    ]

                    operations = [
                        migrations.CreateModel(
                            name="UserProfile",
                            fields=[
                                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                                ("dob", models.DateField()),
                                ("user", models.ForeignKey(on_delete=models.CASCADE, to=settings.AUTH_USER_MODEL)),
                            ],
                        ),
                    ]
                """  # noqa
            )
            self.assertEqual(pretty_extract_piece(app_squash, ""), expected)
