import importlib.util
import inspect
import os
import textwrap
import unittest.mock

import black
import libcst
import pytest
from django.core.management import CommandError
from django.db import models


def load_migration_module(path):
    spec = importlib.util.spec_from_file_location("__module__", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        with open(path) as f:
            raise type(e)(f"{e}.\nError loading module file containing:\n\n{f.read()}") from e
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
        if isinstance(node, (libcst.ClassDef, libcst.FunctionDef)) and node.name.value == looking_for:
            return node
        if isinstance(node, libcst.Assign) and looking_for in [n.target.value for n in node.targets]:
            return node

        for child in node.children:
            result = traverse_node(child, looking_for)
            if result:
                return result


@pytest.mark.temporary_migration_module(module="app.tests.migrations.elidable", app_label="app")
def test_squashing_elidable_migration_simple(migration_app_dir, call_squash_migrations):
    class Person(models.Model):
        name = models.CharField(max_length=10)
        dob = models.DateField()

        class Meta:
            app_label = "app"

    call_squash_migrations()

    files_in_app = os.listdir(migration_app_dir)
    assert "0004_squashed.py" in files_in_app

    app_squash = load_migration_module(os.path.join(migration_app_dir, "0004_squashed.py"))
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


        SQL_1 = 'select 1 from "sqlite_master"'

        SQL_1_ROLLBACK = ["select 2", "select 21", "select 23", 'select 24 from "sqlite_master"']

        SQL_2 = "\\nselect 4\\n"


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
    assert pretty_extract_piece(app_squash, "") == expected


@pytest.mark.temporary_migration_module(module="app.tests.migrations.simple", app_label="app")
@pytest.mark.temporary_migration_module2(module="app2.tests.migrations.foreign_key", app_label="app2", join=True)
def test_squashing_migration_simple(migration_app_dir, migration_app2_dir, call_squash_migrations):
    class Person(models.Model):
        name = models.CharField(max_length=10)
        dob = models.DateField()
        # place_of_birth = models.CharField(max_length=100, blank=True)

        class Meta:
            app_label = "app"

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

    call_squash_migrations()

    files_in_app = os.listdir(migration_app_dir)
    files_in_app2 = os.listdir(migration_app2_dir)
    assert "0004_squashed.py" in files_in_app
    assert "0002_squashed.py" in files_in_app2

    app_squash = load_migration_module(os.path.join(migration_app_dir, "0004_squashed.py"))
    app2_squash = load_migration_module(os.path.join(migration_app2_dir, "0002_squashed.py"))

    assert app_squash.Migration.replaces == [
        ("app", "0001_initial"),
        ("app", "0002_person_age"),
        ("app", "0003_auto_20190518_1524"),
    ]

    assert app2_squash.Migration.replaces == [("app2", "0001_initial")]


@pytest.mark.temporary_migration_module(module="app.test_empty", app_label="app")
def test_squashing_migration_empty(call_squash_migrations):
    class Person(models.Model):
        name = models.CharField(max_length=10)
        dob = models.DateField()

        class Meta:
            app_label = "app"

    with pytest.raises(CommandError) as error:
        call_squash_migrations()
    assert str(error.value) == "There are no migrations to squash."


@pytest.mark.temporary_migration_module(module="app.test_empty", app_label="app")
def test_invalid_apps(call_squash_migrations):
    with pytest.raises(CommandError) as error:
        call_squash_migrations(
            "--ignore-app",
            "a",
            "b",
        )
    assert str(error.value) == "The following apps are not valid: a, b"


@pytest.mark.temporary_migration_module(module="app.test_empty", app_label="app")
def test_ignore_apps_argument(call_squash_migrations, monkeypatch):

    mock_squash = unittest.mock.MagicMock()
    monkeypatch.setattr("django_squash.db.migrations.autodetector.SquashMigrationAutodetector.squash", mock_squash)
    with pytest.raises(CommandError) as error:
        call_squash_migrations(
            "--ignore-app",
            "app2",
            "app",
        )
    assert str(error.value) == "There are no migrations to squash."
    assert mock_squash.called
    assert set(mock_squash.call_args[1]["ignore_apps"]) == {"app2", "app"}


@pytest.mark.temporary_migration_module(module="app.test_empty", app_label="app")
def test_only_argument(call_squash_migrations, settings, monkeypatch):

    mock_squash = unittest.mock.MagicMock()
    monkeypatch.setattr("django_squash.db.migrations.autodetector.SquashMigrationAutodetector.squash", mock_squash)
    with pytest.raises(CommandError) as error:
        call_squash_migrations(
            "--only",
            "app2",
            "app",
        )
    assert str(error.value) == "There are no migrations to squash."
    assert mock_squash.called
    assert set(mock_squash.call_args[1]["ignore_apps"]) == set(settings.INSTALLED_APPS) - {"app2", "app"}


@pytest.mark.temporary_migration_module(module="app.test_empty", app_label="app")
def test_only_argument_with_invalid_apps(call_squash_migrations, monkeypatch):

    mock_squash = unittest.mock.MagicMock()
    monkeypatch.setattr("django_squash.db.migrations.autodetector.SquashMigrationAutodetector.squash", mock_squash)
    with pytest.raises(CommandError) as error:
        call_squash_migrations(
            "--only",
            "app2",
            "invalid",
        )
    assert str(error.value) == "The following apps are not valid: invalid"
    assert not mock_squash.called


@pytest.mark.temporary_migration_module(module="app.tests.migrations.elidable", app_label="app")
def test_simple_delete_squashing_migrations_noop(migration_app_dir, call_squash_migrations):
    class Person(models.Model):
        name = models.CharField(max_length=10)
        dob = models.DateField()

        class Meta:
            app_label = "app"

    call_squash_migrations()

    files_in_app = sorted(file for file in os.listdir(migration_app_dir) if file.endswith(".py"))
    expected = [
        "0001_initial.py",
        "0002_person_age.py",
        "0003_add_dob.py",
        "0004_squashed.py",
        "__init__.py",
    ]
    assert files_in_app == expected


@pytest.mark.temporary_migration_module(module="app.tests.migrations.delete_replaced", app_label="app")
def test_simple_delete_squashing_migrations(migration_app_dir, call_squash_migrations):
    class Person(models.Model):
        name = models.CharField(max_length=10)
        dob = models.DateField()

        class Meta:
            app_label = "app"

    original_app_squash = load_migration_module(os.path.join(migration_app_dir, "0004_squashed.py"))
    assert original_app_squash.Migration.replaces == [
        ("app", "0001_initial"),
        ("app", "0002_person_age"),
        ("app", "0003_add_dob"),
    ]

    call_squash_migrations()

    files_in_app = sorted(file for file in os.listdir(migration_app_dir) if file.endswith(".py"))
    old_app_squash = load_migration_module(os.path.join(migration_app_dir, "0004_squashed.py"))
    new_app_squash = load_migration_module(os.path.join(migration_app_dir, "0005_squashed.py"))

    # We altered an existing file, and removed all the "replaces" items
    assert old_app_squash.Migration.replaces == []
    # The new squashed migration replaced the old one now
    assert new_app_squash.Migration.replaces == [("app", "0004_squashed")]
    assert files_in_app == ["0004_squashed.py", "0005_squashed.py", "__init__.py"]


@pytest.mark.temporary_migration_module(module="app3.tests.migrations.moved", app_label="app3")
def test_empty_models_migrations(migration_app_dir, call_squash_migrations):
    """
    If apps are moved but migrations remain, a fake migration must be made that does nothing and replaces the
    existing migrations, that way django doesn't throw errors when trying to do the same work again.
    """
    call_squash_migrations()
    files_in_app = sorted(file for file in os.listdir(migration_app_dir) if file.endswith(".py"))
    assert "0004_squashed.py" in files_in_app
    app_squash = load_migration_module(os.path.join(migration_app_dir, "0004_squashed.py"))

    expected_files = [
        "0001_initial.py",
        "0002_person_age.py",
        "0003_moved.py",
        "0004_squashed.py",
        "__init__.py",
    ]
    assert files_in_app == expected_files
    assert app_squash.Migration.replaces == [
        ("app3", "0001_initial"),
        ("app3", "0002_person_age"),
        ("app3", "0003_moved"),
    ]


@pytest.mark.temporary_migration_module(module="app.tests.migrations.incorrect_name", app_label="app")
def test_squashing_migration_incorrect_name(migration_app_dir, call_squash_migrations):
    """
    If the app has incorrect migration numbers like: `app/migrations/initial.py` instead of `0001_initial.py`
    it should not fail. Same goes for bad formats all around.
    """

    class Person(models.Model):
        name = models.CharField(max_length=10)
        dob = models.DateField()

        class Meta:
            app_label = "app"

    call_squash_migrations()

    files_in_app = os.listdir(migration_app_dir)
    assert "3001_squashed.py" in files_in_app

    app_squash = load_migration_module(os.path.join(migration_app_dir, "3001_squashed.py"))

    assert app_squash.Migration.replaces == [
        ("app", "2_person_age"),
        ("app", "3000_auto_20190518_1524"),
        ("app", "bad_no_name"),
        ("app", "initial"),
    ]


@pytest.mark.temporary_migration_module(module="app.tests.migrations.run_python_noop", app_label="app")
def test_run_python_same_name_migrations(migration_app_dir, call_squash_migrations):

    call_squash_migrations()

    files_in_app = sorted(file for file in os.listdir(migration_app_dir) if file.endswith(".py"))
    expected_files = [
        "0001_initial.py",
        "0002_run_python.py",
        "0003_squashed.py",
        "__init__.py",
    ]
    assert files_in_app == expected_files

    app_squash = load_migration_module(os.path.join(migration_app_dir, "0003_squashed.py"))
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
                    reverse_code=same_name,
                    elidable=False,
                ),
                migrations.RunPython(
                    code=same_name,
                    reverse_code=same_name_2,
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
    assert pretty_extract_piece(app_squash, "") == expected


@pytest.mark.temporary_migration_module(module="app.tests.migrations.swappable_dependency", app_label="app")
def test_swappable_dependency_migrations(migration_app_dir, settings, call_squash_migrations):
    settings.INSTALLED_APPS += [
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ]

    class UserProfile(models.Model):
        user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
        dob = models.DateField()

        class Meta:
            app_label = "app"

    call_squash_migrations()
    files_in_app = sorted(file for file in os.listdir(migration_app_dir) if file.endswith(".py"))

    expected_files = [
        "0001_initial.py",
        "0002_add_dob.py",
        "0003_squashed.py",
        "__init__.py",
    ]
    assert files_in_app == expected_files

    app_squash = load_migration_module(os.path.join(migration_app_dir, "0003_squashed.py"))
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
    assert pretty_extract_piece(app_squash, "") == expected
