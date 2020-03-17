django-squash
========================

|Travis CI| |codecov|

"django-squash" is an enhancement built on top of the migration classes that come standard with Django. The vision and architecture of Django migrations are unchanged. We replace one command to eliminate the bloat and slowness that grows in proportion to the changes you introduce to your models over time.

Before you use this package you need to understand what the normal Django makemigrations and squashmigrations commands do. Every migration file consists of one or more operations. Some of these operations created by makemigrations make changes to Django models that do not affect the DB table for that model (such as changes to validators, help text, etc). Some of these operations created by makemigrations make changes to the DB table for that model (such as column names, data types, foreign keys, etc). Migrations that you create by hand can run any SQL statement or python code you want.

You specify for each migration operation you create by hand whether it is elidable or not. "Elidable" means the operation can be eliminated when you squash migrations. For example, if you split an existing table into two or more tables, you must populate the new tables from the old. Once that is done, you never need to do it again, even if you are creating a brand new DB. This is because the source table is empty when creating a new DB so it's pointless to populate those two new tables from the empty old one.

"Non-elidable" means the operation cannot be eliminated when you squash migrations. Perhaps you are creating a very special index on a table that cannot be configured when describing the model. You have to write raw SQL that your flavor of DB understands. If you are creating a new DB, that operation must be run sometime after that table has been created.

When you run the normal Django squashmigrations command, typically 1 to 3 migration files per app are created for you. They "squash" migrations for that app by consolidating all the operations in the existing migration files. The new squashed migration files replace all those prior files because they now contain all the non-elidable operations contained in those prior files. If you had 50 non-elidable operations across 20 files, you now might have 2 new squashed migration files containing all those 50 operations. You have reduced the number of files, but you have not reduced the number of operations.

If you have changed the help_text attribute of a model's field three times, you only need to preserve the last one, but the squashmigrations command preserves all of them. If you have created a model, changed it a bit, and then deleted it, you don't need to preserve any of those operations if you're creating a new DB. Why create a model and its DB table just to delete it? Over time you carry this ever-growing burden with you. The step in your testing pipeline that creates the DB runs slower and slower. Every time you deploy your app and DB to a new environment, the step that creates the DB slows down to a crawl as it runs almost every operation created since the beginning of time.

This package offers an alternate command named squash_migrations. Its name differs from the normal Django squashmigrations by just that underscore in the middle of the name. Instead of preserving all historical non-elidable operations, internally it uses the makemigrations logic in a way that assumes no prior operations exist, and that one or more "initial" migrations must be created to create the DB tables from the current model definitions. This results in the fewest possible operations to build your DB. Testing pipelines and deployments of new databases run much, much faster. This is especially important if you use a schema-per-tenant strategy to support hundreds or thousands of tenants. Every time you create a new schema for a new tenant you must run all migrations to create that schema. Even if you don't use a schema-per-tenant strategy, you should never tolerate long-running testing pipelines as you are forced to choose between wasting valuable developer time and cutting corners by not testing everything all the time.

So what's the catch? Two things: 1) the proper use of elidable vs. non-elidable operations, and 2) this tool REQUIRES that all databases you are maintaining never fall behind to the point where they need a migration operation you just eliminated.

Our operation-eliminating squash_migrations command removes all elidable operations. That's what "elidable" means. We keep all non-elidable operations and call them last. But you really need to ask yourself why you are using non-elidable operations at all. What are you doing that cannot be done by simply using django.db.models.signals.post_migrate?

Our squash_migration command deletes all migrations before the prior time you ran it. Run it once per release AFTER cutting the release. It must be the first thing you do before adding migrations to the new release you're working on. All databases must be on the current release, the prior release, or somewhere in between. Any DB that is BEFORE that prior release cannot go directly to the current release. It must first apply the prior release with the migrations in effect for that release and only then apply the current release, which now contains only the operations needed to go from the prior release to the current release. This is the price you must pay for keeping migration operations to the absolute minimum.

This is NOT a tutorial on migration strategy and techniques. You need to know how to design multi-app systems that avoid circular dependencies and other problems that often remain hidden until you attempt to squash migrations.

We developed this approach at the Education Advisory Board after years of frustration and experience. At first we tried to eliminate unneeded operations by tediously searching for redundant or self-eliminating operations against the same field or model. We then tried to hide existing migrations in order to get Django's makemigrations command to create the perfect, minimal operations that an initial migration would create, followed by hand-stitching the replacement and dependency statements a squashing migration needs. Then add to that all those non-elidable operations.

We found ourselves following the same tedious steps every time we squashed migrations for a new release. When you do that every 2 - 4 weeks, you get highly motivated to automate that process. We hope you take the time to improve your migration strategy and find our tool useful.

Setup
~~~~~~~~~~~~~~~~~~~~~~~~

1. ``pip install django-squash``

2. Add ``django_squash`` to your ``INSTALLED_APPS``.

3. Profit!


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
