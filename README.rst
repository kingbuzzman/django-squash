django-squash
========================

|Travis CI| |codecov|

django-squash is replacement for the standard squashmigration that comes with Django. It was created to eliminate the bloat and slowness that grows in proportion to the changes you introduce to your models over time.

Before you use this package you need to understand what the normal Django makemigrations and squashmigrations commands do. Every migration file consists of one or more operations. Some of these operations created by makemigrations make changes to Django models that do not affect the DB table for that model (such as changes to validators, help text, etc). Some of these operations created by makemigrations make changes to the DB table for that model (such as column names, data types, foreign keys, etc). Migrations that you create by hand can run any SQL statement or python code you want.

You specify for each migration operation you create by hand whether it is elidable or not. "Elidable" means the operation can be eliminated when you squash migrations. For example, if you split an existing table into two or more tables, you must populate the new tables from the old. Once that is done, you never need to do it again, even if you are creating a brand new DB. This is because the source table is empty when creating a new DB so it's pointless to populate those two new tables from the empty old one.

"Non-elidable" means the operation cannot be eliminated when you squash migrations. Perhaps you are creating a very special index on a table that cannot be configured when describing the model. You have to write raw SQL that your flavor of DB understands. If you are creating a new DB, that operation must be run sometime after that table has been created.

When you run the normal Django squashmigrations command, typically 1 to 3 migration files per app are created for you. They "squash" migrations for that app by consolidating all the operations in the existing migration files. The new squashed migration files replace all those prior files because they now contain all the non-elidable operations contained in those prior files. If you had 50 non-elidable operations in 20 files, you now might have 2 new squashed migration files containing all those 50 operations. You have reduced the number of files, but you have not reduced the number of operations.

If you have changed the help_text attribute of a model's field three times, you only need to preserve the last one, but the squashmigrations command preserves all of them. If you have created a model, changed it a bit, and then deleted it, you don't need to preserve any of those operations if you're creating a new DB. Why create a model and its DB table just to delete it? Over time you carry this ever-growing burden with you. The step in your testing pipeline that creates the DB runs slower and slower. Every time you deploy your app and DB to a new environment, the step that creates the DB slows down to a crawl as it runs almost every operation created since the beginning of time.

This package offers an alternate command named squash_migrations. Its name differs from the normal Django squashmigrations by just that underscore in the middle of the name. Instead of preserving all historical non-elidable operations, internally it uses the makemigrations command in a way that assumes no prior operations exist, and that one or more "initial" migrations must be created to create the DB tables from the current model definitions. This results in the fewest possible operations to build your DB. Testing pipelines and deployments of new databases run much, much faster.

So what's the catch? Two things: 1) the proper use of elidable vs. non-eliable operations, and 2) you can only delete migrations if all databases you are maintaining have applied those migrations.

Our operation-eliminating squash_migrations removes all elidable operations. That's what "elidable" means. We keep all non-elidable operations and call them last. But you really need to ask yourself why you are using non-eliable operations at all. What are you doing that cannot be done by simply using django.db.models.signals.post_migrate?

This is especially important if you use a schema-per-tenant strategy to support hundreds or thousands of tenants. Every time you create a new schema for a new tenant you must run all migrations to create that schema.

This is NOT a tutorial on migration strategy. You need to know how to design multi-app systems that avoid circular dependencies and other problems that often remain hidden until you attempt to squash migrations.

We developed this approach at the Education Advisory Board after years of frustration and experience. At first we tried to eliminate unneeded operations by searching for redundant or self-eliminating operations against the same field or model. We then tried to hide existing migrations in order to get makemigrations to create the perfect, minimal operations that an initial migration would create, followed by hand-stitching the replacement and dependency statements a squashing migration needs. Then add to that all those non-elidable operations.

We found ourselves following the same tedious steps every time we squashed migrations for a new release. When you do that every 2 - 4 weeks, you get highly motivated to automate that process. We hope you take the time to study your migration strategy and find our tool useful.

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

.. |codecov| image:: https://codecov.io/gh/kingbuzzman/django-squash/branch/develop/graph/badge.svg
  :target: https://codecov.io/gh/kingbuzzman/django-squash
