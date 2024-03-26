#!/usr/bin/env python

import io
import itertools
import json
import os

here = os.path.abspath(os.path.dirname(__file__))
with io.open(os.path.join(here, "README.rst"), encoding="utf-8") as fp:
    README = fp.read()

DJANGO_VERSIONS = ["3.2", "4.1", "4.2", "5.0"]  # "main" is fictitiously here
PYTHON_VERSIONS = ["3.8", "3.9", "3.10", "3.11", "3.12"]
MIN_DJANGO_VERSION = ".".join(map(str, min([tuple(map(int, v.split("."))) for v in DJANGO_VERSIONS])))
MIN_PYTHON_VERSION = ".".join(map(str, min([tuple(map(int, v.split("."))) for v in PYTHON_VERSIONS])))
# Python/Django exceptions
EXCLUDE_MATRIX = (["3.8", "3.9"], ["5.0.*", "main"])
GITHUB_MATRIX = json.dumps(
    {
        "python-version": PYTHON_VERSIONS,
        "django-version": [f"{v}.*" for v in DJANGO_VERSIONS] + ["main"],
        "exclude": [{"django-version": d, "python-version": p} for p, d in itertools.product(*EXCLUDE_MATRIX)],
    }
)

if __name__ == "__main__":
    from setuptools import find_packages, setup

    setup(
        name="django_squash",
        version="0.0.11",
        description="A migration squasher that doesn't care how Humpty Dumpty was put together.",
        long_description=README,
        classifiers=[
            # See https://pypi.org/pypi?%3Aaction=list_classifiers
            "Development Status :: 5 - Production/Stable",
            "Environment :: Console",
            "Intended Audience :: Developers",
            "Framework :: Django",
        ]
        + [f"Framework :: Django :: {v}" for v in DJANGO_VERSIONS]
        + [
            "Programming Language :: Python",
            "Programming Language :: Python :: 3",
        ]
        + [f"Programming Language :: Python :: {v}" for v in PYTHON_VERSIONS]
        + [
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
        packages=find_packages(exclude=["tests*", "docs*"]),
        platforms=["any"],
        zip_safe=True,
        python_requires=f">={MIN_PYTHON_VERSION}",
        install_requires=[
            f"django>={MIN_DJANGO_VERSION}",
        ],
        tests_require=[],
        extras_require={
            "test": [
                "black",
                "build",
                "flake8",
                "flake8-tidy-imports",
                "ipdb",
                "isort",
                "libcst",
                "psycopg2-binary",
                "pytest-cov",
                "pytest-django",
                "restructuredtext-lint",
                "setuptools",
            ],
        },
    )
