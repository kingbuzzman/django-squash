import ast
import inspect
import os
import pkgutil
import re

from django import get_version
from django.db import migrations as migration_module
from django.db.migrations.writer import (
    MIGRATION_HEADER_TEMPLATE, MIGRATION_TEMPLATE, MigrationWriter as MigrationWriterBase, OperationWriter,
)
from django.utils.timezone import now

from django_squash.db.migrations import utils


class ReplacementMigrationWriter(MigrationWriterBase):
    """
    Take a Migration instance and is able to produce the contents
    of the migration file from it.
    """
    template_class_header = MIGRATION_HEADER_TEMPLATE
    template_class = MIGRATION_TEMPLATE

    def __init__(self, migration, include_header=True):
        self.migration = migration
        self.include_header = include_header
        self.needs_manual_porting = False

    def as_string(self):
        """Return a string of the file contents."""
        return self.template_class % self.get_kwargs()

    def get_kwargs(self):
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
        items["dependencies"] = "\n".join(dependencies) + "\n" if dependencies else ""

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
        sorted_imports = sorted(imports, key=lambda i: i.split()[1])
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
            items['replaces_str'] = "\n    replaces = %s\n" % self.serialize(self.migration.replaces)[0]
        # Hinting that goes into comment
        if self.include_header:
            items['migration_header'] = self.template_class_header % {
                'version': get_version(),
                'timestamp': now().strftime("%Y-%m-%d %H:%M"),
            }
        else:
            items['migration_header'] = ""

        if self.migration.initial:
            items['initial_str'] = "\n    initial = True\n"

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

    template_variable = '''%s = """%s"""'''

    def as_string(self):
        if hasattr(self.migration, 'is_migration_level') and self.migration.is_migration_level:
            return self.replace_in_migration()
        else:
            return super().as_string()

    def replace_in_migration(self):
        if self.migration._deleted:
            os.remove(self.path)
            return

        changed = False
        with open(self.path) as f:
            source = f.read()

        if self.migration._dependencies_change:
            source = utils.replace_migration_attribute(source, 'dependencies', self.migration.dependencies)
            changed = True
        if self.migration._replaces_change:
            source = utils.replace_migration_attribute(source, 'replaces', self.migration.replaces)
            changed = True
        if not changed:
            raise NotImplementedError()

        return source

    @staticmethod
    def extract_function(code):
        function_source = inspect.getsource(code)
        if code.__original_qualname__ == code.__qualname__:
            return function_source

        function_source = re.sub(rf'(def\s+){code.__original_qualname__}',
                                 rf'\1{code.__qualname__}',
                                 function_source,
                                 1)
        return function_source

    def get_kwargs(self):
        kwargs = super().get_kwargs()

        functions = []
        variables = []
        for operation in self.migration.operations:
            if isinstance(operation, migration_module.RunPython):
                if not utils.is_code_in_site_packages(operation.code.__original_module__):
                    functions.append(self.extract_function(operation.code))
                if operation.reverse_code:
                    if not utils.is_code_in_site_packages(operation.reverse_code.__original_module__):
                        functions.append(self.extract_function(operation.reverse_code))
            elif isinstance(operation, migration_module.RunSQL):
                variables.append(self.template_variable % (operation.sql.name, operation.sql.value))
                if operation.reverse_sql:
                    variables.append(self.template_variable % (operation.reverse_sql.name,
                                     operation.reverse_sql.value))

        kwargs['functions'] = ('\n\n' if functions else '') + '\n\n'.join(functions)
        kwargs['variables'] = ('\n\n' if variables else '') + '\n\n'.join(variables)
        kwargs['operations'] = kwargs['operations'].replace('DELETEMEPLEASE.', '')
        kwargs['imports'] = kwargs['imports'].replace('import DELETEMEPLEASE\n', '')

        imports = (x for x in set(kwargs['imports'].split('\n') + getattr(self.migration, 'extra_imports', [])) if x)
        sorted_imports = sorted(imports, key=lambda i: i.split()[1])
        kwargs["imports"] = "\n".join(sorted_imports) + "\n" if imports else ""

        return kwargs
