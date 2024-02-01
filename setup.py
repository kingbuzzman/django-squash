#!/usr/bin/env python

import io
import os

from setuptools import find_packages, setup

here = os.path.abspath(os.path.dirname(__file__))
with io.open(os.path.join(here, "README.rst"), encoding="utf-8") as fp:
    README = fp.read()


setup(
    name="django_squash",
    version="0.0.10",
    description="A migration squasher that doesn't care how Humpty Dumpty was put together.",
    long_description=README,
    classifiers=[
        # See https://pypi.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.1",
        "Framework :: Django :: 4.2",
        "Framework :: Django :: 5.0",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
    ],
    keywords="django migration squashing squash",
    author="Javier Buzzi",
    author_email="buzzi.javier@gmail.com",
    url="https://github.com/kingbuzzman/django-squash",
    license="MIT",
    packages=find_packages(exclude=["tests*"]),
    platforms=["any"],
    zip_safe=True,
    python_requires=">=3.7",
    install_requires=[
        "django>=3.2",
    ],
    tests_require=[],
    extras_require={
        "test": [
            "pytest-cov",
            "pytest-django",
            "flake8",
            "ipdb",
            "libcst",
            "isort",
            "black",
        ],
    },
)
