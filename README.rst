django-squash
===========

|Travis CI|

django-squash is a migration squashing replacement that cares more about keeping migrations small and precise.


Setup
~~~~~~~~~~~~~~~~~~~~~~~~

1. ``pip install django-squash``

2. Add ``django_squash`` to your ``INSTALLED_APPS``.

3. Profit!


What this does
~~~~~~~~~~~~~~~~~~~~~~~~

Let's say you have an app for a couple of years, with lots of changes to the app's ``migrations`` folder would look something like this:

.. code-block::

    app/migrations/__init__.py
    app/migrations/0001_initial.py
    app/migrations/0002_changes.py
    ...
    app/migrations/0400_changes.py

You can run ``python manage.py squash_migrations`` and then it will look like this:

.. code-block::

    app/migrations/__init__.py
    app/migrations/0001_initial.py
    app/migrations/0002_changes.py
    ...
    app/migrations/0400_changes.py
    app/migrations/0401_squashed.py

Inside the ``0401_squashed.py``, you will find all you migrations including all your ``RunPython`` and ``RunSQL`` that are `elidable`.

After you know that all the migrations from ``0001`` to ``0401`` have been applied, run ``python manage.py delete_squashed_migrations``.


Run tests
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: shell

    pip install -e '.[test]'
    coverage run setup.py test
    coverage report -m


.. |Travis CI| image:: https://travis-ci.com/kingbuzzman/django-squash.svg?branch=develop
   :target: https://travis-ci.com/kingbuzzman/django-squash
