import inspect
import os
import re
import textwrap
import warnings

from django import get_version
from django.db import migrations as dj_migrations
from django.db.migrations import writer as dj_writer
from django.utils.timezone import now

from django_squash.contrib import postgres
from django_squash.db.migrations import operators, utils

SUPPORTED_DJANGO_WRITER = (
    "39645482d4eb04b9dd21478dc4bdfeea02393913dd2161bf272f4896e8b3b343",  # 5.0
    "2aab183776c34e31969eebd5be4023d3aaa4da584540b91a5acafd716fa85582",  # 4.1 / 4.2
    "e90b1243a8ce48f06331db8f584b0bce26e2e3f0abdd177cc18ed37425a23515",  # 3.2
)


def check_django_migration_hash():
    """
    Check if the django migrations writer file has changed and may not be compatible with django-squash.
    """
    current_django_migration_hash = utils.file_hash(dj_writer.__file__)
    if current_django_migration_hash not in SUPPORTED_DJANGO_WRITER:
        messsage = textwrap.dedent(
            f"""\
            Django migrations writer file has changed and may not be compatible with django-squash.

            Django version: {get_version()}
            Django migrations writer file: {dj_writer.__file__}
            Django migrations writer hash: {current_django_migration_hash}
            """
        )
        warnings.warn(messsage, Warning)


check_django_migration_hash()


class OperationWriter(dj_writer.OperationWriter):
    def serialize(self):
        if isinstance(self.operation, postgres.PGCreateExtension):
            if not utils.is_code_in_site_packages(self.operation.__class__.__module__):
                self.feed("%s()," % (self.operation.__class__.__name__))
                return self.render(), set()

        return super().serialize()


class ReplacementMigrationWriter(dj_writer.MigrationWriter):
    """
    Take a Migration instance and is able to produce the contents
    of the migration file from it.
    """

    template_class_header = dj_writer.MIGRATION_HEADER_TEMPLATE
    template_class = dj_writer.MIGRATION_TEMPLATE

    def __init__(self, migration, include_header=True):
        self.migration = migration
        self.include_header = include_header
        self.needs_manual_porting = False

    def as_string(self):
        """Return a string of the file contents."""
        return self.template_class % self.get_kwargs()

    def get_kwargs(self):  # pragma: no cover
        """
        Original method from django.db.migrations.writer.MigrationWriter.as_string
        """
        items = {
            "replaces_str": "",
            "initial_str": "",
        }

        imports = set()

        # Deconstruct operations
        operations = []
        for operation in self.migration.operations:
            operation_string, operation_imports = OperationWriter(operation).serialize()
            imports.update(operation_imports)
            operations.append(operation_string)
        items["operations"] = "\n".join(operations) + "\n" if operations else ""

        # Format dependencies and write out swappable dependencies right
        dependencies = []
        for dependency in self.migration.dependencies:
            if dependency[0] == "__setting__":
                dependencies.append("        migrations.swappable_dependency(settings.%s)," % dependency[1])
                imports.add("from django.conf import settings")
            else:
                dependencies.append("        %s," % self.serialize(dependency)[0])
        items["dependencies"] = "\n".join(sorted(dependencies)) + "\n" if dependencies else ""

        # Format imports nicely, swapping imports of functions from migration files
        # for comments
        migration_imports = set()
        for line in list(imports):
            if re.match(r"^import (.*)\.\d+[^\s]*$", line):
                migration_imports.add(line.split("import")[1].strip())
                imports.remove(line)
                self.needs_manual_porting = True

        # django.db.migrations is always used, but models import may not be.
        # If models import exists, merge it with migrations import.
        if "from django.db import models" in imports:
            imports.discard("from django.db import models")
            imports.add("from django.db import migrations, models")
        else:
            imports.add("from django.db import migrations")

        # Sort imports by the package / module to be imported (the part after
        # "from" in "from ... import ..." or after "import" in "import ...").
        # First group the "import" statements, then "from ... import ...".
        sorted_imports = sorted(imports, key=lambda i: (i.split()[0] == "from", i.split()[1]))
        items["imports"] = "\n".join(sorted_imports) + "\n" if imports else ""
        if migration_imports:
            items["imports"] += (
                "\n\n# Functions from the following migrations need manual "
                "copying.\n# Move them and any dependencies into this file, "
                "then update the\n# RunPython operations to refer to the local "
                "versions:\n# %s"
            ) % "\n# ".join(sorted(migration_imports))
        # If there's a replaces, make a string for it
        if self.migration.replaces:
            items["replaces_str"] = "\n    replaces = %s\n" % self.serialize(self.migration.replaces)[0]
        # Hinting that goes into comment
        if self.include_header:
            items["migration_header"] = self.template_class_header % {
                "version": get_version(),
                "timestamp": now().strftime("%Y-%m-%d %H:%M"),
            }
        else:
            items["migration_header"] = ""

        if self.migration.initial:
            items["initial_str"] = "\n    initial = True\n"

        return items


class MigrationWriter(ReplacementMigrationWriter):
    template_class = """\
%(migration_header)s%(imports)s%(functions)s%(variables)s

class Migration(migrations.Migration):
%(replaces_str)s%(initial_str)s
    dependencies = [
%(dependencies)s\
    ]

    operations = [
%(operations)s\
    ]
"""

    template_variable = """%s = %s"""

    def as_string(self):
        if hasattr(self.migration, "is_migration_level") and self.migration.is_migration_level:
            return self.replace_in_migration()

        variables = []
        custom_naming_function = utils.get_custom_rename_function()
        unique_names = utils.UniqueVariableName(
            {"app": self.migration.app_label}, naming_function=custom_naming_function
        )
        for operation in self.migration.operations:
            unique_names.update_context(
                {
                    "new_migration": self.migration,
                    "operation": operation,
                    "migration": (
                        operation._original_migration if hasattr(operation, "_original_migration") else self.migration
                    ),
                }
            )
            operation._deconstruct = operation.__class__.deconstruct

            def deconstruct(self):
                name, args, kwargs = self._deconstruct(self)
                kwargs["elidable"] = self.elidable
                return name, args, kwargs

            if isinstance(operation, dj_migrations.RunPython):
                # Bind the deconstruct() to the instance to get the elidable
                operation.deconstruct = deconstruct.__get__(operation, operation.__class__)
                if not utils.is_code_in_site_packages(operation.code.__module__):
                    code_name = utils.normalize_function_name(unique_names.function(operation.code))
                    operation.code = utils.copy_func(operation.code, code_name)
                    operation.code.__in_migration_file__ = True
                if operation.reverse_code:
                    if not utils.is_code_in_site_packages(operation.reverse_code.__module__):
                        reversed_code_name = utils.normalize_function_name(
                            unique_names.function(operation.reverse_code)
                        )
                        operation.reverse_code = utils.copy_func(operation.reverse_code, reversed_code_name)
                        operation.reverse_code.__in_migration_file__ = True
            elif isinstance(operation, dj_migrations.RunSQL):
                # Bind the deconstruct() to the instance to get the elidable
                operation.deconstruct = deconstruct.__get__(operation, operation.__class__)

                variable_name = unique_names("SQL", force_number=True)
                variables.append(self.template_variable % (variable_name, repr(operation.sql)))
                operation.sql = operators.Variable(variable_name, operation.sql)
                if operation.reverse_sql:
                    reverse_variable_name = "%s_ROLLBACK" % variable_name
                    variables.append(self.template_variable % (reverse_variable_name, repr(operation.reverse_sql)))
                    operation.reverse_sql = operators.Variable(reverse_variable_name, operation.reverse_sql)

        return super().as_string()

    def replace_in_migration(self):
        if self.migration._deleted:
            os.remove(self.path)
            return

        changed = False
        with open(self.path) as f:
            source = f.read()

        if self.migration._dependencies_change:
            source = utils.replace_migration_attribute(source, "dependencies", self.migration.dependencies)
            changed = True
        if self.migration._replaces_change:
            source = utils.replace_migration_attribute(source, "replaces", self.migration.replaces)
            changed = True
        if not changed:
            raise NotImplementedError()  # pragma: no cover

        return source

    def get_kwargs(self):
        kwargs = super().get_kwargs()
        functions_references = []
        functions = []
        variables = []
        for operation in self.migration.operations:
            if isinstance(operation, dj_migrations.RunPython):
                if hasattr(operation.code, "__original__"):
                    if operation.code.__original__ in functions_references:
                        continue
                    functions_references.append(operation.code.__original__)
                else:
                    if operation.code in functions_references:
                        continue
                    functions_references.append(operation.code)

                if not utils.is_code_in_site_packages(operation.code.__module__):
                    functions.append(textwrap.dedent(operation.code.__source__))
                if operation.reverse_code:
                    if hasattr(operation.reverse_code, "__original__"):
                        if operation.reverse_code.__original__ in functions_references:
                            continue
                        functions_references.append(operation.reverse_code.__original__)
                    else:
                        if operation.reverse_code in functions_references:
                            continue
                        functions_references.append(operation.reverse_code)
                    if not utils.is_code_in_site_packages(operation.reverse_code.__module__):
                        functions.append(textwrap.dedent(operation.reverse_code.__source__))
            elif isinstance(operation, dj_migrations.RunSQL):
                variables.append(self.template_variable % (operation.sql.name, repr(operation.sql.value)))
                if operation.reverse_sql:
                    variables.append(
                        self.template_variable % (operation.reverse_sql.name, repr(operation.reverse_sql.value))
                    )
            elif isinstance(operation, postgres.PGCreateExtension):
                if not utils.is_code_in_site_packages(operation.__class__.__module__):
                    functions.append(textwrap.dedent(inspect.getsource(operation.__class__)))

        kwargs["functions"] = ("\n\n" if functions else "") + "\n\n".join(functions)
        kwargs["variables"] = ("\n\n" if variables else "") + "\n\n".join(variables)

        imports = (x for x in set(kwargs["imports"].split("\n") + getattr(self.migration, "extra_imports", [])) if x)
        sorted_imports = sorted(imports, key=lambda i: (i.split()[0] == "from", i.split()))
        kwargs["imports"] = "\n".join(sorted_imports) + "\n" if imports else ""

        return kwargs
