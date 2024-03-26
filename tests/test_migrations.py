import textwrap
import unittest.mock

import pytest
from django.contrib.postgres.indexes import GinIndex
from django.core.management import CommandError
from django.db import models
from django.db.migrations.recorder import MigrationRecorder

DjangoMigrationModel = MigrationRecorder.Migration


@pytest.mark.temporary_migration_module(module="app.tests.migrations.elidable", app_label="app")
def test_squashing_elidable_migration_simple(migration_app_dir, call_squash_migrations):
    class Person(models.Model):
        name = models.CharField(max_length=10)
        dob = models.DateField()

        class Meta:
            app_label = "app"

    call_squash_migrations()

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
    assert migration_app_dir.migration_read("0004_squashed.py", "") == expected


def custom_func_naming(original_name, context):
    """
    Used in test_squashing_elidable_migration_unique_name_formatting to format the function names
    """
    return f"{context['migration'].name}_{original_name}"


@pytest.mark.temporary_migration_module(module="app.tests.migrations.elidable", app_label="app")
def test_squashing_elidable_migration_unique_name_formatting(migration_app_dir, call_squash_migrations, monkeypatch):
    """
    Test that DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION integration works properly
    """
    monkeypatch.setattr(
        "django_squash.settings.DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION", f"{__name__}.custom_func_naming"
    )

    class Person(models.Model):
        name = models.CharField(max_length=10)
        dob = models.DateField()

        class Meta:
            app_label = "app"

    call_squash_migrations()

    source = migration_app_dir.migration_read("0004_squashed.py", "")
    assert source.count("f_0002_person_age_same_name(") == 1
    assert source.count("code=f_0002_person_age_same_name,") == 1
    assert source.count("f_0002_person_age_same_name_2(") == 1
    assert source.count("code=f_0002_person_age_same_name_2,") == 1
    assert source.count("f_0003_add_dob_same_name(") == 1
    assert source.count("code=f_0003_add_dob_same_name,") == 1
    assert source.count("f_0003_add_dob_create_admin_MUST_ALWAYS_EXIST(") == 1
    assert source.count("code=f_0003_add_dob_create_admin_MUST_ALWAYS_EXIST,") == 1
    assert source.count("f_0003_add_dob_rollback_admin_MUST_ALWAYS_EXIST(") == 1
    assert source.count("code=f_0003_add_dob_rollback_admin_MUST_ALWAYS_EXIST,") == 1


@pytest.mark.temporary_migration_module(module="app.tests.migrations.simple", app_label="app")
@pytest.mark.temporary_migration_module2(module="app2.tests.migrations.foreign_key", app_label="app2")
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

    files_in_app = migration_app_dir.migration_files()
    files_in_app2 = migration_app2_dir.migration_files()
    assert "0004_squashed.py" in files_in_app
    assert "0002_squashed.py" in files_in_app2

    app_squash = migration_app_dir.migration_load("0004_squashed.py")
    app2_squash = migration_app2_dir.migration_load("0002_squashed.py")

    assert app_squash.Migration.replaces == [
        ("app", "0001_initial"),
        ("app", "0002_person_age"),
        ("app", "0003_auto_20190518_1524"),
    ]

    assert app2_squash.Migration.replaces == [("app2", "0001_initial")]


@pytest.mark.temporary_migration_module(module="app.tests.migrations.simple", app_label="app")
@pytest.mark.temporary_migration_module2(module="app2.tests.migrations.foreign_key", app_label="app2", join=True)
def test_squashing_migration_simple_ignore(migration_app_dir, migration_app2_dir, call_squash_migrations):
    """
    Test that "app" gets ignored correctly, nothing changes inside it's migration directory. "app2" gets squashed,
    and points to the latest "app" migration as a dependency.
    """

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

    call_squash_migrations(
        "--ignore-app",
        "app",
    )

    files_in_app = migration_app_dir.migration_files()
    assert files_in_app == ["0001_initial.py", "0002_person_age.py", "0003_auto_20190518_1524.py", "__init__.py"]

    files_in_app2 = migration_app2_dir.migration_files()
    assert files_in_app2 == ["0001_initial.py", "0002_squashed.py", "__init__.py"]

    app2_squash = migration_app2_dir.migration_load("0002_squashed.py")
    assert app2_squash.Migration.replaces == [("app2", "0001_initial")]
    assert app2_squash.Migration.dependencies == [("app", "0003_auto_20190518_1524")]


@pytest.mark.temporary_migration_module(module="app.tests.migrations.empty", app_label="app")
def test_squashing_migration_empty(migration_app_dir, call_squash_migrations):
    del migration_app_dir

    class Person(models.Model):
        name = models.CharField(max_length=10)
        dob = models.DateField()

        class Meta:
            app_label = "app"

    with pytest.raises(CommandError) as error:
        call_squash_migrations()
    assert str(error.value) == "There are no migrations to squash."


@pytest.mark.temporary_migration_module(module="app.tests.migrations.empty", app_label="app")
def test_invalid_apps(migration_app_dir, call_squash_migrations):
    del migration_app_dir
    with pytest.raises(CommandError) as error:
        call_squash_migrations(
            "--ignore-app",
            "aaa",
            "bbb",
        )
    assert str(error.value) == "The following apps are not valid: aaa, bbb"


@pytest.mark.temporary_migration_module(module="app.tests.migrations.empty", app_label="app")
def test_invalid_apps_ignore(migration_app_dir, monkeypatch, call_squash_migrations):
    del migration_app_dir
    monkeypatch.setattr("django_squash.settings.DJANGO_SQUASH_IGNORE_APPS", ["aaa", "bbb"])
    with pytest.raises(CommandError) as error:
        call_squash_migrations()
    assert str(error.value) == "The following apps are not valid: aaa, bbb"


@pytest.mark.filterwarnings("ignore")
def test_only_apps_with_ignored_app(call_squash_migrations):
    """
    Edge case: if the app was previously ignored, remove it from the ignore list
    """
    with pytest.raises(CommandError) as error:
        call_squash_migrations(
            "--ignore-app",
            "app2",
            "app",
            "--only",
            "app2",
        )
    assert str(error.value) == "The following app cannot be ignored and selected at the same time: app2"


@pytest.mark.temporary_migration_module(module="app.tests.migrations.empty", app_label="app")
def test_ignore_apps_argument(migration_app_dir, call_squash_migrations, monkeypatch):
    del migration_app_dir
    mock_squash = unittest.mock.MagicMock()
    monkeypatch.setattr(
        "django_squash.db.migrations.autodetector.SquashMigrationAutodetector.squash",
        mock_squash,
    )
    with pytest.raises(CommandError) as error:
        call_squash_migrations(
            "--ignore-app",
            "app2",
            "app",
        )
    assert str(error.value) == "There are no migrations to squash."
    assert mock_squash.called
    assert set(mock_squash.call_args[1]["ignore_apps"]) == {"app2", "app"}


@pytest.mark.temporary_migration_module(module="app.tests.migrations.empty", app_label="app")
def test_only_argument(migration_app_dir, call_squash_migrations, settings, monkeypatch):
    del migration_app_dir
    mock_squash = unittest.mock.MagicMock()
    monkeypatch.setattr(
        "django_squash.db.migrations.autodetector.SquashMigrationAutodetector.squash",
        mock_squash,
    )
    with pytest.raises(CommandError) as error:
        call_squash_migrations(
            "--only",
            "app2",
            "app",
        )
    assert str(error.value) == "There are no migrations to squash."
    assert mock_squash.called
    installed_apps = {full_app.rsplit(".")[-1] for full_app in settings.INSTALLED_APPS}
    assert set(mock_squash.call_args[1]["ignore_apps"]) == installed_apps - {"app2", "app"}


@pytest.mark.temporary_migration_module(module="app.tests.migrations.empty", app_label="app")
def test_only_argument_with_invalid_apps(migration_app_dir, call_squash_migrations, monkeypatch):
    del migration_app_dir
    mock_squash = unittest.mock.MagicMock()
    monkeypatch.setattr(
        "django_squash.db.migrations.autodetector.SquashMigrationAutodetector.squash",
        mock_squash,
    )
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

    files_in_app = migration_app_dir.migration_files()
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

    original_app_squash = migration_app_dir.migration_load("0004_squashed.py")
    assert original_app_squash.Migration.replaces == [
        ("app", "0001_initial"),
        ("app", "0002_person_age"),
        ("app", "0003_add_dob"),
    ]

    call_squash_migrations()

    files_in_app = migration_app_dir.migration_files()
    old_app_squash = migration_app_dir.migration_load("0004_squashed.py")
    new_app_squash = migration_app_dir.migration_load("0005_squashed.py")

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
    files_in_app = migration_app_dir.migration_files()
    assert "0004_squashed.py" in files_in_app
    app_squash = migration_app_dir.migration_load("0004_squashed.py")

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

    files_in_app = migration_app_dir.migration_files()
    assert "3001_squashed.py" in files_in_app

    app_squash = migration_app_dir.migration_load("3001_squashed.py")

    assert app_squash.Migration.replaces == [
        ("app", "2_person_age"),
        ("app", "3000_auto_20190518_1524"),
        ("app", "bad_no_name"),
        ("app", "initial"),
    ]


@pytest.mark.temporary_migration_module(module="app.tests.migrations.run_python_noop", app_label="app")
def test_run_python_same_name_migrations(migration_app_dir, call_squash_migrations):

    call_squash_migrations()

    files_in_app = migration_app_dir.migration_files()
    expected_files = [
        "0001_initial.py",
        "0002_run_python.py",
        "0003_squashed.py",
        "__init__.py",
    ]
    assert files_in_app == expected_files

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
    assert migration_app_dir.migration_read("0003_squashed.py", "") == expected


@pytest.mark.temporary_migration_module(module="app.tests.migrations.swappable_dependency", app_label="app")
def test_swappable_dependency_migrations(migration_app_dir, settings, call_squash_migrations):
    class UserProfile(models.Model):
        user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
        dob = models.DateField()

        class Meta:
            app_label = "app"

    call_squash_migrations()
    files_in_app = migration_app_dir.migration_files()

    assert files_in_app == [
        "0001_initial.py",
        "0002_add_dob.py",
        "0003_squashed.py",
        "__init__.py",
    ]

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
    assert migration_app_dir.migration_read("0003_squashed.py", "") == expected


@pytest.mark.temporary_migration_module(module="app.tests.migrations.pg_indexes", app_label="app")
def test_squashing_migration_pg_indexes(migration_app_dir, call_squash_migrations):

    class Message(models.Model):
        score = models.IntegerField(default=0)
        unicode_name = models.CharField(max_length=255, db_index=True)

        class Meta:
            indexes = [models.Index(fields=["-score"]), GinIndex(fields=["unicode_name"])]
            app_label = "app"

    call_squash_migrations()
    assert migration_app_dir.migration_files() == [
        "0001_initial.py",
        "0002_use_index.py",
        "0003_squashed.py",
        "__init__.py",
    ]
    expected = textwrap.dedent(
        """\
        import django.contrib.postgres.indexes
        import django.contrib.postgres.operations
        from django.contrib.postgres.operations import BtreeGinExtension
        from django.db import migrations
        from django.db import migrations, models


        class Migration(migrations.Migration):

            replaces = [("app", "0001_initial"), ("app", "0002_use_index")]

            initial = True

            dependencies = []

            operations = [
                django.contrib.postgres.operations.BtreeGinExtension(),
                migrations.CreateModel(
                    name="Message",
                    fields=[
                        ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("score", models.IntegerField(default=0)),
                        ("unicode_name", models.CharField(db_index=True, max_length=255)),
                    ],
        """  # noqa
    )
    # NOTE: different django versions handle index differently, since the Index part is actually not
    #       being tested, it doesn't matter that is not checked
    assert migration_app_dir.migration_read("0003_squashed.py", "").startswith(expected)


@pytest.mark.temporary_migration_module(module="app.tests.migrations.pg_indexes_custom", app_label="app")
def test_squashing_migration_pg_indexes_custom(migration_app_dir, call_squash_migrations):

    class Message(models.Model):
        score = models.IntegerField(default=0)
        unicode_name = models.CharField(max_length=255, db_index=True)

        class Meta:
            indexes = [models.Index(fields=["-score"]), GinIndex(fields=["unicode_name"])]
            app_label = "app"

    call_squash_migrations()
    assert migration_app_dir.migration_files() == [
        "0001_initial.py",
        "0002_use_index.py",
        "0003_squashed.py",
        "__init__.py",
    ]
    expected = textwrap.dedent(
        """\
        import django.contrib.postgres.indexes
        from django.contrib.postgres.operations import BtreeGinExtension
        from django.db import migrations
        from django.db import migrations, models


        class IgnoreRollbackBtreeGinExtension(BtreeGinExtension):
            \"\"\"
            Custom extension that doesn't rollback no matter what
            \"\"\"

            def database_backwards(self, *args, **kwargs):
                pass


        class Migration(migrations.Migration):

            replaces = [("app", "0001_initial"), ("app", "0002_use_index")]

            initial = True

            dependencies = []

            operations = [
                IgnoreRollbackBtreeGinExtension(),
                migrations.CreateModel(
                    name="Message",
                    fields=[
                        ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("score", models.IntegerField(default=0)),
                        ("unicode_name", models.CharField(db_index=True, max_length=255)),
                    ],
        """  # noqa
    )
    # NOTE: different django versions handle index differently, since the Index part is actually not
    #       being tested, it doesn't matter that is not checked
    assert migration_app_dir.migration_read("0003_squashed.py", "").startswith(expected)
