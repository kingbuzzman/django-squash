from django.db import migrations
import pytest

from django_squash.db.migrations import utils
import django

import django_squash

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
    names = utils.UniqueVariableName()
    assert names("var") == "var"
    assert names("var") == "var_2"
    assert names("var_2") == "var_2_2"


def test_unique_function_names_errors():
    names = utils.UniqueVariableName()

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


def test_unique_function_names():
    uniq1 = utils.UniqueVariableName()
    uniq2 = utils.UniqueVariableName()

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
