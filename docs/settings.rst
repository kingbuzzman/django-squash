Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following settings are available in order to customize your experience.

``DJANGO_SQUASH_IGNORE_APPS``
----------------------------------------

Default: ``[]`` (Empty list)

Example: (``["app1", "app2"]``)

Hardcoded list of apps to always ignore, no matter what, the same as ``--ignore`` in the ``./manage.py squash_migrations`` command.

``DJANGO_SQUASH_MIGRATION_NAME``
----------------------------------------

Default: ``"squashed"`` (string)

The generated migration name when ``./manage.py squash_migrations`` command is run. It's possible to use the `python date formats <https://docs.python.org/3/library/datetime.html#format-codes>`_ as long you escape them in the string.

``DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION``
----------------------------------------

Default: ``None`` (None)

Example: "path.to.generator_function"

Dot path to the function that will rename the functions found inside ``RunPython`` operations.

Function needs to accept 2 arguments: ``name`` (``str``) and ``context`` (``dict``) and must return a string (``-> str``)
