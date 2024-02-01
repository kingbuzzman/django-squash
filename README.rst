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

django-squash
========================

"django-squash" is a migration enhancement built on top of Django's standard migration classes. It aims to eliminate bloat and slowness in migration processes by replacing certain commands. The vision and architecture of Django migrations remain unchanged.

Before using "django-squash," it's important to understand the normal Django ``makemigrations`` and ``squashmigrations`` commands. Migration files consist of operations that may or may not affect the database table for a model. "elidable" operations can be eliminated when squashing migrations, while "non-elidable" operations cannot. Best way to think about the word "elidable" is to simply think "forgetable" or "disgardable" -- can this operation be disgarded once it's been ran?

The package introduces a command named ``squash_migrations`` as an alternative to Django's ``squashmigrations``. This command minimizes the number of operations needed to build the database's schema, resulting in faster testing pipelines and deployments, especially in scenarios with multiple tenants.

The catch lies in proper usage of elidable vs. non-elidable operations and the requirement that databases must not fall behind to the point where eliminated migration operations are needed. The ``squash_migrations`` command removes all elidable operations and preserves non-elidable ones.

It's crucial to run the ``squash_migrations`` command once per release after cutting the release. All databases must be on the current release, the prior release, or somewhere in between. Databases before the prior release cannot directly upgrade to the current release; they must first apply the prior release's migrations and then the current release's minimal operations.

This approach is not a tutorial on migration strategy but emphasizes the need for understanding multi-app systems, avoiding circular dependencies, and designing efficient migration processes. The tool is developed based on experience and frustration, aiming to automate and improve the migration squashing process.

Setup
~~~~~~~~~~~~~~~~~~~~~~~~

1. ``pip install django-squash``

2. Add ``django_squash`` to your ``INSTALLED_APPS``.

2.1 There are some :ref:`settings docs/settings.rst` you can customize

3. Run ``./manage.py squash_migrations`` once *after* each release

4. Profit!


What this does
~~~~~~~~~~~~~~~~~~~~~~~~

Let's say you're working on an app for a couple of years with lots of changes to models and their fields. You use this tool and eliminate all unnecessary migration operations after every release. That app's ``migrations`` directory will evolve something like this.

.. code-block::

    app/migrations/__init__.py
    app/migrations/0001_initial.py
    app/migrations/0002_changes_for_release1.py
    ...
    app/migrations/0019_changes_for_release1.py

You cut release 1. The migration directory for that release looks exactly as above. Then you run our ``python manage.py squash_migrations`` command. It will look something like below. You might have fewer or more migration files, depending on foreign keys and other things that determine how many migration files are needed.

.. code-block::

    app/migrations/__init__.py
    app/migrations/0001_initial.py
    app/migrations/0002_changes_for_release1.py
    ...
    app/migrations/0019_changes_for_release1.py
    app/migrations/0020_squashed.py
    app/migrations/0021_squashed.py

Inside the ``0020_squashed.py`` and ``0021_squashed.py`` files you will find the minimum operations needed to create your current models from scratch. The ``0021_squashed.py`` file will contain all your non-elidable ``RunPython`` and ``RunSQL`` operations that you wrote by hand. The variable and function names will be different to avoid duplicate names, but they will run in the exact order you put them.

Note that no migration files were deleted above. This is the only time this will happen.

Now you work on release 2, adding migrations as you go. The app's ``migrations`` directory will look something like below.

.. code-block::

    app/migrations/__init__.py
    app/migrations/0001_initial.py
    app/migrations/0002_changes_for_release1.py
    ...
    app/migrations/0019_changes_for_release1.py
    app/migrations/0020_squashed.py
    app/migrations/0021_squashed.py
    app/migrations/0022_changes_for_release2.py
    ...
    app/migrations/0037_changes_for_release2.py

You cut release 2. The migration directory for that release looks exactly as above. All databases at the level of release 1 will have applied all migrations up to ``0019_changes_for_release1.py``. When this release 2 is applied to them, migrations ``0020_squashed.py`` and ``0021_squashed.py`` will be faked and migrations ``0022_changes_for_release2.py`` to ``0037_changes_for_release2.py`` will be applied.

Then you run our ``python manage.py squash_migrations`` command. It will look something like below.

.. code-block::

    app/migrations/__init__.py
    app/migrations/0020_squashed.py
    app/migrations/0021_squashed.py
    app/migrations/0022_changes_for_release2.py
    ...
    app/migrations/0037_changes_for_release2.py
    app/migrations/0038_squashed.py
    app/migrations/0039_squashed.py

Inside the ``0038_squashed.py`` and ``0039_squashed.py`` files you will find the minimum operations needed to create your current models from scratch. Note that the migration files before the ``0020_squashed.py`` file were deleted above. When you run your tests or when you deploy this branch to a new environment and build your DB from scratch, only the ``0038_squashed.py`` and ``0039_squashed.py`` files will be used. This should run much faster than running all the operations contained in ``0020_squashed.py`` through ``0037_changes_for_release2.py``. Now you're ready to work on release 3.

But wait!! This is not realistic. You probably had to patch release 1, which required three migration files. What impact will that have on these releases?

Release 1 should now look like this:

.. code-block::

    app/migrations/__init__.py
    app/migrations/0001_initial.py
    app/migrations/0002_changes_for_release1.py
    ...
    app/migrations/0019_changes_for_release1.py
    app/migrations/0020_changes_for_release1.py
    app/migrations/0021_changes_for_release1.py
    app/migrations/0022_changes_for_release1.py

You must insert those same migrations logically AFTER what release 1 looked like IMMEDIATELY after squashing and BEFORE any migrations were introduced for release 2.

Done correctly release 2 should now look like the following except it will be ordered perfectly alphabetically:

.. code-block::

    app/migrations/__init__.py
    app/migrations/0001_initial.py
    app/migrations/0002_changes_for_release1.py
    ...
    app/migrations/0019_changes_for_release1.py
    app/migrations/0020_squashed.py
    app/migrations/0021_squashed.py
    
    app/migrations/0020_changes_for_release1.py
    app/migrations/0021_changes_for_release1.py
    app/migrations/0022_changes_for_release1.py
    
    app/migrations/0022_changes_for_release2.py
    ...
    app/migrations/0037_changes_for_release2.py

You have to manually change ``0020_changes_for_release1.py`` to depend on ``0021_squashed.py`` instead of ``0019_changes_for_release1.py``. This is how you insert it logically between release 1 and release 2.

Developing
~~~~~~~~~~~~~~~~~~~~~~~~

1. clone the repo

2. ``cd`` into repo

3. (optional) run inside ``docker`` environment that way you can change the python version quickly and iterate faster

.. code-block:: shell

    docker run --rm -it -v .:/app -e PYTHONDONTWRITEBYTECODE=1 python:3.12 bash -c 'cd app; pip install -e .[test]; echo; echo; echo "run **pytest** to run tests"; echo; exec bash'

Alternatively, you can also create a virtual environment and run

.. code-block:: shell

    pip install -e '.[test]'

4. Run tests

.. code-block:: shell

    pytest

5. Before making a commit, make sure that the formatter and linter tools do not detect any issues.

.. code-block:: shell

    isort .
    black --config .black .
    flake8 .
