Configuration
~~~~~~~~~~~~~~~~~~~~~~~~

The following settings are available in order to customize your experience.

``DJANGO_SQUASH_IGNORE_APPS``
-----------------------------

Default: ``[]`` (Empty list)

Example: (``["app1", "app2"]``)

Hardcoded list of apps to always ignore, no matter what, the same as ``--ignore`` in the ``./manage.py squash_migrations`` command.

``DJANGO_SQUASH_MIGRATION_NAME``
-----------------------------

Default: ``"squashed"`` (string)

The generated migration name when ``./manage.py squash_migrations`` command is ran.
