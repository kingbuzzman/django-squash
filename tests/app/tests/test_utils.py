from unittest import TestCase

from django_squash.management.commands.lib.autodetector import UniqueVariableName


class TestUtils(TestCase):

    def test_unique_names(self):
        names = UniqueVariableName()
        self.assertEqual('var', names('var'))
        self.assertEqual('var_2', names('var'))
        self.assertEqual('var_2_2', names('var_2'))
