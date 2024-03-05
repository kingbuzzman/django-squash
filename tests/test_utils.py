import tempfile

import django
import pytest
from django.db import migrations

import django_squash
from django_squash.db.migrations import utils

func = lambda: 1  # noqa


def func2():
    return 2


def func2_impostor():
    return 21


func2_impostor.__qualname__ = "func2"


def func2_impostor2():
    return 22


func2_impostor2.__qualname__ = "func2"


def func2_3():
    return 2


class A:
    @staticmethod
    def func():
        return 3


class B:
    @classmethod
    def func(cls):
        return 4


class C:
    def func(self):
        return 5


class D(migrations.Migration):
    def func(self):
        return 6

    def func2(apps, schema_editor):
        return 61


def test_is_code_in_site_packages():
    assert utils.is_code_in_site_packages(django.get_version.__module__)
    path = django_squash.db.migrations.utils.is_code_in_site_packages.__module__
    assert not utils.is_code_in_site_packages(path)
    assert not utils.is_code_in_site_packages("bad.path")


def test_unique_names():
    names = utils.UniqueVariableName({})
    assert names("var") == "var"
    assert names("var") == "var_2"
    assert names("var_2") == "var_2_2"


def test_unique_function_names_errors():
    names = utils.UniqueVariableName({})

    with pytest.raises(ValueError):
        names.function("not-a-function")

    with pytest.raises(ValueError):
        names.function(func)

    with pytest.raises(ValueError):
        names.function(B.func)

    with pytest.raises(ValueError):
        names.function(B().func)

    with pytest.raises(ValueError):
        names.function(C.func)

    with pytest.raises(ValueError):
        names.function(C().func)

    with pytest.raises(ValueError):
        names.function(D.func)


def test_unique_function_names_context():
    def custom_name(name, context):
        return "{module}_{i}_{name}".format(**context, name=name)

    names = utils.UniqueVariableName({"module": __name__.replace(".", "_")}, naming_function=custom_name)
    collector = []
    for i, func in enumerate((func2, func2_3, func2_impostor, func2_impostor2)):
        names.update_context({"func": func, "i": i})
        collector.append(names.function(func))

    assert collector == [
        "tests_test_utils_0_func2",
        "tests_test_utils_1_func2_3",
        "tests_test_utils_2_func2",
        "tests_test_utils_3_func2",
    ]


def test_unique_function_names():
    uniq1 = utils.UniqueVariableName({})
    uniq2 = utils.UniqueVariableName({})

    reassigned_func2 = func2
    reassigned_func2_impostor = func2_impostor

    assert uniq1("func2") == "func2"
    assert uniq1.function(func2) == "func2_2"
    assert uniq1.function(func2) == "func2_2"
    assert uniq1.function(reassigned_func2) == "func2_2"
    assert uniq1.function(func2_impostor) == "func2_3"
    assert uniq1.function(func2_impostor) == "func2_3"
    assert uniq1.function(reassigned_func2_impostor) == "func2_3"
    assert uniq1.function(func2_3) == "func2_3_2"
    assert uniq1.function(func2_impostor2) == "func2_4"
    assert uniq1.function(A.func) == "A.func"
    assert uniq1.function(A().func) == "A.func"
    assert uniq1("A.func") == "A.func_2"
    assert uniq1.function(A.func) == "A.func"
    assert uniq1.function(A().func) == "A.func"
    assert uniq1.function(D.func2) == "func2_5"

    assert uniq2.function(func2_impostor) == "func2"
    assert uniq2.function(func2_impostor) == "func2"
    assert uniq2.function(func2) == "func2_2"
    assert uniq2.function(func2) == "func2_2"
    assert uniq2.function(func2_3) == "func2_3"
    assert uniq2.function(func2_impostor2) == "func2_4"
    assert uniq2.function(func2_impostor) == "func2"
    assert uniq2.function(func2_impostor) == "func2"
    assert uniq2.function(func2) == "func2_2"
    assert uniq2.function(func2) == "func2_2"
    assert uniq2.function(D.func2) == "func2_5"


def test_file_hash():
    with tempfile.NamedTemporaryFile() as f:
        f.write(b"test")
        f.flush()
        assert utils.file_hash(f.name) == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def test_normalize_function_name():
    reassigned_func2 = func2
    reassigned_func2_impostor = func2_impostor

    assert utils.normalize_function_name(func.__qualname__) == "<lambda>"
    assert utils.normalize_function_name(func2.__qualname__) == "func2"
    assert utils.normalize_function_name(reassigned_func2.__qualname__) == "func2"
    assert utils.normalize_function_name(func2_impostor.__qualname__) == "func2"
    assert utils.normalize_function_name(reassigned_func2_impostor.__qualname__) == "func2"
    assert utils.normalize_function_name(A().func.__qualname__) == "func"
    assert utils.normalize_function_name(D.func.__qualname__) == "func"


def test_get_custom_rename_function(monkeypatch):
    """
    Cover all cases where DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION can go wrong
    """
    assert not utils.get_custom_rename_function()
    utils.get_custom_rename_function.cache_clear()

    monkeypatch.setattr("django_squash.settings.DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION", "")
    assert not utils.get_custom_rename_function()
    utils.get_custom_rename_function.cache_clear()

    monkeypatch.setattr("django_squash.settings.DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION", "tests.test_utils.func2")
    assert utils.get_custom_rename_function() == func2
    utils.get_custom_rename_function.cache_clear()

    monkeypatch.setattr("django_squash.settings.DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION", "tests.test_utils.bad")
    with pytest.raises(ImportError):
        utils.get_custom_rename_function()
    utils.get_custom_rename_function.cache_clear()

    monkeypatch.setattr("django_squash.settings.DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION", "does.not.exist")
    with pytest.raises(ModuleNotFoundError):
        utils.get_custom_rename_function()
