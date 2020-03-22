#!/usr/bin/env python
# coding=utf-8

import io
import os
import sys

from setuptools import find_packages, setup
from setuptools.command.test import test as TestCommand

here = os.path.abspath(os.path.dirname(__file__))
with io.open(os.path.join(here, 'README.rst'), encoding='utf-8') as fp:
    README = fp.read()


class DjangoTest(TestCommand):
    command_consumes_arguments = True

    def initialize_options(self):
        self.args = None
        super().initialize_options()

    def run_tests(self):
        from tests.runtests import django_tests

        sys.path.insert(0, 'tests')
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

        django_tests(verbosity=3,
                     interactive=False,
                     failfast=True,
                     keepdb=False,
                     reverse=False,
                     test_labels=[os.path.normpath(labels) for labels in self.args],
                     debug_sql=False,
                     parallel=False,
                     tags=[],
                     exclude_tags=[],
                     test_name_patterns=[])


setup(
    name='django_squash',
    version='0.0.4',
    description="A migration squasher that doesn't care how Humpty Dumpty was put together.",
    long_description=README,
    classifiers=[
        # See https://pypi.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Testing',
        'Topic :: Utilities',
        'License :: OSI Approved :: MIT License',
    ],
    keywords='django migration squashing squash',
    author='Javier Buzzi',
    author_email='buzzi.javier@gmail.com',
    url='https://github.com/kingbuzzman/django-squash',
    license="MIT",
    packages=find_packages(exclude=['tests*']),
    platforms=['any'],
    zip_safe=True,
    python_requires='!=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*',
    cmdclass={'test': DjangoTest},
    install_requires=[
        'django>=2.0',
    ],
    tests_require=[],
    extras_require={
        'test':  ['isort', 'flake8', 'ipdb', 'coverage'],
    }
)
