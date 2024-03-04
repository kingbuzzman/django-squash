import pytest
from django.db.migrations import Migration as OriginalMigration

from django_squash.db.migrations import autodetector, operators, utils


def test_migration():
    original = OriginalMigration("0001_inital", "app")
    new = autodetector.Migration.from_migration(original)
    assert new.name == "0001_inital"
    assert new.app_label == "app"
    assert new._original_migration == original

    assert new[0] == "app"
    assert new[1] == "0001_inital"
    assert list(new) == ["app", "0001_inital"]

    assert not list(new.describe())
    assert not new.is_migration_level
    new._deleted = True
    new._dependencies_change = True
    new._replaces_change = True
    assert new.is_migration_level
    assert list(new.describe()) == ["Deleted", '"dependencies" changed', '"replaces" keyword removed']


def test_migration_using_keywords():
    """
    Test that the migration can be created using our internal keywords
    """

    class FakeMigration:
        app_label = "app"
        name = "0001_inital"

    autodetector.Migration.from_migration(FakeMigration())

    for keyword in ("_deleted", "_dependencies_change", "_replaces_change", "_original_migration"):
        migration = OriginalMigration("0001_inital", "app")
        fake_migration = FakeMigration()
        new_migration = autodetector.Migration("0001_inital", "app")

        setattr(migration, keyword, True)
        setattr(fake_migration, keyword, True)
        setattr(new_migration, keyword, True)

        with pytest.raises(AssertionError):
            autodetector.Migration.from_migration(migration)

        with pytest.raises(AssertionError):
            autodetector.Migration.from_migration(fake_migration)

        autodetector.Migration.from_migration(new_migration)


def noop(*a, **k):
    pass


def test_all_custom_operations():
    """
    Test that all_custom_operations returns the correct operations
    """
    var = utils.UniqueVariableName()

    class Migration(autodetector.Migration):
        operations = [
            operators.RunSQL("SELECT 1", elidable=True),
            operators.RunPython(noop, elidable=True),
            operators.RunSQL("SELECT 2", elidable=True),
        ]

    assert list(autodetector.all_custom_operations(Migration.operations, var)) == []

    class Migration(autodetector.Migration):
        operations = [
            operators.RunSQL("SELECT 1", elidable=False),
            operators.RunPython(noop, elidable=False),
            operators.RunSQL("SELECT 2", elidable=True),
        ]

    assert [type(x).__name__ for x in autodetector.all_custom_operations(Migration.operations, var)] == [
        "RunSQL",
        "RunPython",
    ]