from unittest import TestCase

from django_squash.management.commands.lib.autodetector import UniqueVariableName
from django_squash.management.commands.lib.writer import is_code_in_site_packages

func = lambda: 1  # noqa


def func2():
    return 2


def func2_impostor():
    return 21


func2_impostor.__qualname__ = 'func2'


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


class TestWriter(TestCase):

    def test_is_code_in_site_packages(self):
        import django

        import django_squash

        self.assertTrue(is_code_in_site_packages(django.get_version.__module__))
        path = django_squash.management.commands.lib.writer.is_code_in_site_packages.__module__
        self.assertFalse(is_code_in_site_packages(path))
        self.assertFalse(is_code_in_site_packages('bad.path'))


class TestUtils(TestCase):

    def test_unique_names(self):
        names = UniqueVariableName()
        self.assertEqual('var', names('var'))
        self.assertEqual('var_2', names('var'))
        self.assertEqual('var_2_2', names('var_2'))

    def test_unique_function_names_errors(self):
        names = UniqueVariableName()

        with self.assertRaises(ValueError):
            names.function("not-a-function")

        with self.assertRaises(ValueError):
            names.function(func)

        with self.assertRaises(ValueError):
            names.function(B.func)

        with self.assertRaises(ValueError):
            names.function(B().func)

        with self.assertRaises(ValueError):
            names.function(C.func)

        with self.assertRaises(ValueError):
            names.function(C().func)

    def test_unique_function_names(self):
        uniq1 = UniqueVariableName()
        uniq2 = UniqueVariableName()

        reassigned_func2 = func2
        reassigned_func2_impostor = func2_impostor

        self.assertEqual('func2', uniq1("func2"))
        self.assertEqual('func2_2', uniq1.function(func2))
        self.assertEqual('func2_2', uniq1.function(func2))
        self.assertEqual('func2_2', uniq1.function(reassigned_func2))
        self.assertEqual('func2_3', uniq1.function(func2_impostor))
        self.assertEqual('func2_3', uniq1.function(func2_impostor))
        self.assertEqual('func2_3', uniq1.function(reassigned_func2_impostor))
        self.assertEqual('A.func', uniq1.function(A.func))
        self.assertEqual('A.func', uniq1.function(A().func))
        self.assertEqual('A.func_2', uniq1("A.func"))
        self.assertEqual('A.func', uniq1.function(A.func))
        self.assertEqual('A.func', uniq1.function(A().func))

        self.assertEqual('func2', uniq2.function(func2_impostor))
        self.assertEqual('func2', uniq2.function(func2_impostor))
        self.assertEqual('func2_2', uniq2.function(func2))
        self.assertEqual('func2_2', uniq2.function(func2))
        self.assertEqual('func2', uniq2.function(func2_impostor))
        self.assertEqual('func2', uniq2.function(func2_impostor))
        self.assertEqual('func2_2', uniq2.function(func2))
        self.assertEqual('func2_2', uniq2.function(func2))
