.. image:: https://img.shields.io/pypi/v/django-squash.svg?style=flat
    :alt: Supported PyPi Version
    :target: https://pypi.python.org/pypi/django-squash

.. image:: https://img.shields.io/pypi/pyversions/django-squash.svg
    :alt: Supported Python versions
    :target: https://pypi.python.org/pypi/django-squash

.. image:: https://img.shields.io/pypi/djversions/django-squash.svg
    :alt: Supported Django versions
    :target: https://pypi.org/project/django-squash/

.. image:: https://codecov.io/gh/kingbuzzman/django-squash/branch/master/graph/badge.svg
    :alt: Coverage
    :target: https://codecov.io/gh/kingbuzzman/django-squash

.. image:: https://img.shields.io/pypi/dm/django-squash
   :alt: PyPI - Downloads
   :target: https://pypistats.org/packages/django-squash

django-squash
========================

"django-squash" is a migration enhancement built on top of Django_'s standard migration classes. It aims to eliminate bloat and slowness in migration processes by replacing certain commands. The vision and architecture of Django migrations remain unchanged.

Before using "django-squash," it's important to understand the normal Django ``makemigrations`` and ``squashmigrations`` commands. Migration files consist of operations that may or may not affect the database table for a model. "elidable" operations can be eliminated when squashing migrations, while "non-elidable" operations cannot. Best way to think about the word "elidable" is to simply think "forgetable" or "disgardable" -- can this operation be disgarded once it's been ran?

The package introduces a command named ``squash_migrations`` as an alternative to Django's ``squashmigrations``. This command minimizes the number of operations needed to build the database's schema, resulting in faster testing pipelines and deployments, especially in scenarios with multiple tenants.

The catch lies in proper usage of elidable vs. non-elidable operations and the requirement that databases must not fall behind to the point where eliminated migration operations are needed. The ``squash_migrations`` command removes all elidable operations and preserves non-elidable ones.

It's crucial to run the ``squash_migrations`` command once per release after cutting the release. All databases must be on the current release, the prior release, or somewhere in between. Databases before the prior release cannot directly upgrade to the current release; they must first apply the prior release's migrations and then the current release's minimal operations.

This approach is not a tutorial on migration strategy but emphasizes the need for understanding multi-app systems, avoiding circular dependencies, and designing efficient migration processes. The tool is developed based on experience and frustration, aiming to automate and improve the migration squashing process.

You can read more about our motivation_ to creating this tool.

Setup
~~~~~~~~~~~~~~~~~~~~~~~~

1. ``pip install django-squash``

2. Add ``django_squash`` to your ``INSTALLED_APPS``.

   (optional) There are some settings_ you can customize

3. Run ``./manage.py squash_migrations`` once *after* each release

4. Profit!


Developing
~~~~~~~~~~~~~~~~~~~~~~~~

1. clone the repo

2. ``cd`` into repo

3. (optional) run inside ``docker`` environment that way you can change the python version quickly and iterate faster

.. code-block:: shell

    docker run --rm -it -v .:/app -v django-squash-pip-cache:/root/.cache/pip -e PYTHONDONTWRITEBYTECODE=1 python:3.12 bash -c "cd app; pip install -e .[test,lint]; echo \"alias linters=\\\"echo '> isort'; isort .; echo '> black'; black .; echo '> ruff'; ruff check .;echo '> flake8'; flake8 .; echo '> rst-lint'; rst-lint README.rst docs/*\\\"\" >> ~/.bash_profile; printf '\n\n\nrun **pytest** to run tests, **linters** to run linters\n\n'; exec bash --init-file ~/.bash_profile"

Alternatively, you can also create a virtual environment and run

.. code-block:: shell

    python3 -m venv venv

.. code-block:: shell

    source venv/bin/activate

.. code-block:: shell

    pip install -e '.[test]'

4. Run tests

.. code-block:: shell

    pytest

5. Before making a commit, make sure that the formatter and linter tools do not detect any issues.

.. code-block:: shell

    isort .
    black .
    flake8 .
    ruff check .
    rst-lint .

.. _Django: http://djangoproject.com
.. _`settings`: docs/settings.rst
.. _`motivation`: docs/motivation.rst
