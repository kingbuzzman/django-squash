from django.db.migrations.migration import Migration, swappable_dependency
from django.db.migrations.operations.special import RunPython
from django.db.models.base import Model
from django.db.models.fields.proxy import OrderWrt

from django_squash.db.migrations import serializer


def noop():
    pass


def test_function_type_serializer():
    S = serializer.FunctionTypeSerializer
    assert S(OrderWrt).serialize() == (
        "models.OrderWrt",
        {"from django.db import models"},
    )
    assert S(Model).serialize() == ("models.Model", {"from django.db import models"})

    assert S(Migration).serialize() == (
        "migrations.Migration",
        {"from django.db import migrations"},
    )
    assert S(swappable_dependency).serialize() == (
        "migrations.swappable_dependency",
        {"from django.db import migrations"},
    )
    assert S(RunPython).serialize() == (
        "migrations.RunPython",
        {"from django.db import migrations"},
    )
    assert S(RunPython.noop).serialize() == (
        "migrations.RunPython.noop",
        {"from django.db import migrations"},
    )

    assert S(noop).serialize() == (
        "tests.test_serializer.noop",
        {"import tests.test_serializer"},
    )
    noop.__in_migration_file__ = False
    assert S(noop).serialize() == (
        "tests.test_serializer.noop",
        {"import tests.test_serializer"},
    )
    noop.__in_migration_file__ = True
    assert S(noop).serialize() == ("noop", {})
