import ast
import collections
import copy
import inspect
import itertools
import os
import re
import sys
import types
from collections import defaultdict
from itertools import takewhile

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, no_translations
from django.core.management.commands.makemigrations import Command as MakeMigrationsCommand
from django.db import DEFAULT_DB_ALIAS, connection, connections, migrations as migration_module, router
from django.db.migrations.autodetector import MigrationAutodetector as MigrationAutodetectorBase
from django.db.migrations.graph import MigrationGraph
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.questioner import (
    InteractiveMigrationQuestioner, MigrationQuestioner,
    NonInteractiveMigrationQuestioner as NonInteractiveMigrationQuestionerBase,
)
from django.db.migrations.state import ProjectState
from django.db.migrations.utils import get_migration_name_timestamp
from django.db.migrations.writer import (
    MIGRATION_HEADER_TEMPLATE, MIGRATION_TEMPLATE, MigrationWriter as MigrationWriterBase, OperationWriter,
)
from django.utils.inspect import get_func_args


class Migration(migration_module.Migration):

    def __getitem__(self, index):
        return (self.app_label, self.name)[index]

    def __iter__(self):
        yield from (self.app_label, self.name)

    @classmethod
    def from_migration(cls, migration):
        new = Migration(name=migration.name, app_label=migration.app_label)
        new.__dict__ = migration.__dict__.copy()
        return new


def all_custom_operations(operations):
    """
    Generator that loops over all the operations and traverses sub-operations such as those inside a -
    SeparateDatabaseAndState class.
    """
    for operation in operations:
        if operation.elidable:
            continue

        if isinstance(operation, migration_module.RunSQL) or isinstance(operation, migration_module.RunPython):
            yield operation
        elif isinstance(operation, migration_module.SeparateDatabaseAndState):
            yield from all_custom_operations(operation.state_operations)
            # Just in case we added something in here incorrectly
            # This should always return nothing since it should NEVER have any RunSQL / RunPython
            yield from all_custom_operations(operation.database_operations)


def get_imports(module):
    """
    Return an generator with all the imports to a particular py file as string
    """
    source = inspect.getsource(module)
    path = inspect.getsourcefile(module)

    root = ast.parse(source, path)
    for node in ast.iter_child_nodes(root):
        if isinstance(node, ast.Import):
            for n in node.names:
                yield f'import {n.name}'
        elif isinstance(node, ast.ImportFrom):
            module = node.module.split('.')
            # Remove old python 2.x imports
            if '__future__' not in node.module:
                yield f"from {node.module} import {', '.join([x.name for x in node.names])}"
        else:
            continue


def copy_func(f, name=None):
    return types.FunctionType(f.__code__, f.__globals__, name or f.__name__,
                              f.__defaults__, f.__closure__)


# class OperationWriter(OperationWriterBase):
#
#     def serialize(self):
#
#         def _write(_arg_name, _arg_value):
#             if (_arg_name in self.operation.serialization_expand_args and
#                     isinstance(_arg_value, (list, tuple, dict))):
#                 if isinstance(_arg_value, dict):
#                     self.feed('%s={' % _arg_name)
#                     self.indent()
#                     for key, value in _arg_value.items():
#                         key_string, key_imports = MigrationWriter.serialize(key)
#                         arg_string, arg_imports = MigrationWriter.serialize(value)
#                         args = arg_string.splitlines()
#                         if len(args) > 1:
#                             self.feed('%s: %s' % (key_string, args[0]))
#                             for arg in args[1:-1]:
#                                 self.feed(arg)
#                             self.feed('%s,' % args[-1])
#                         else:
#                             self.feed('%s: %s,' % (key_string, arg_string))
#                         imports.update(key_imports)
#                         imports.update(arg_imports)
#                     self.unindent()
#                     self.feed('},')
#                 else:
#                     self.feed('%s=[' % _arg_name)
#                     self.indent()
#                     for item in _arg_value:
#                         arg_string, arg_imports = MigrationWriter.serialize(item)
#                         args = arg_string.splitlines()
#                         if len(args) > 1:
#                             for arg in args[:-1]:
#                                 self.feed(arg)
#                             self.feed('%s,' % args[-1])
#                         else:
#                             self.feed('%s,' % arg_string)
#                         imports.update(arg_imports)
#                     self.unindent()
#                     self.feed('],')
#             else:
#                 import ipdb; ipdb.set_trace()
#                 arg_string, arg_imports = MigrationWriter.serialize(_arg_value)
#                 args = arg_string.splitlines()
#                 if len(args) > 1:
#                     self.feed('%s=%s' % (_arg_name, args[0]))
#                     for arg in args[1:-1]:
#                         self.feed(arg)
#                     self.feed('%s,' % args[-1])
#                 else:
#                     self.feed('%s=%s,' % (_arg_name, arg_string))
#                 imports.update(arg_imports)
#
#         imports = set()
#         name, args, kwargs = self.operation.deconstruct()
#         operation_args = get_func_args(self.operation.__init__)
#
#         # See if this operation is in django.db.migrations. If it is,
#         # We can just use the fact we already have that imported,
#         # otherwise, we need to add an import for the operation class.
#         if getattr(migration_module, name, None) == self.operation.__class__:
#             self.feed('migrations.%s(' % name)
#         else:
#             imports.add('import %s' % (self.operation.__class__.__module__))
#             self.feed('%s.%s(' % (self.operation.__class__.__module__, name))
#
#         self.indent()
#
#         for i, arg in enumerate(args):
#             arg_value = arg
#             arg_name = operation_args[i]
#             _write(arg_name, arg_value)
#
#         i = len(args)
#         # Only iterate over remaining arguments
#         for arg_name in operation_args[i:]:
#             if arg_name in kwargs:  # Don't sort to maintain signature order
#                 arg_value = kwargs[arg_name]
#                 _write(arg_name, arg_value)
#
#         self.unindent()
#         self.feed('),')
#         return self.render(), imports


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
%(migration_header)s%(imports)s%(functions)s

class Migration(migrations.Migration):
%(replaces_str)s%(initial_str)s
    dependencies = [
%(dependencies)s\
    ]

    operations = [
%(operations)s\
    ]
"""

    def get_kwargs(self):
        kwargs = super().get_kwargs()

        functions = []

        module = sys.modules[self.migration.__module__]
        for operation in self.migration.operations:
            if isinstance(operation, migration_module.RunPython):
                functions.append(inspect.getsource(operation.code))

        kwargs['operations'] = kwargs['operations'].replace('DELETEMEPLEASE.', '')
        kwargs['imports'] = kwargs['imports'].replace('import DELETEMEPLEASE\n', '')
        kwargs['functions'] = ('\n\n' if functions else '') + '\n\n'.join(functions)

        return kwargs


class SquashMigrationAutodetector(MigrationAutodetectorBase):

    def add_non_elidables(self, loader, changes):
        replacing_migrations_by_app = {app: [loader.disk_migrations[r]
                                             for r in itertools.chain.from_iterable([m.replaces for m in migrations])]
                                       for app, migrations in changes.items()}

        for app in changes.keys():
            operations = []
            imports = []

            for migration in replacing_migrations_by_app[app]:
                module = sys.modules[migration.__module__]
                imports.extend(get_imports(module))
                for operation in all_custom_operations(migration.operations):
                    operation.code = copy_func(operation.code)
                    operation.code.__module__ = 'DELETEMEPLEASE'
                    operations.append(operation)

            migration = changes[app][-1]
            migration.operations += operations
            migration.extra_imports = imports

            # module = sys.modules[migration.__module__]
            # for operation in operations:
            #     import ipdb; ipdb.set_trace()
            #     setattr(module, operation.code.__name__, copy_func(operation.code))
            #     operation.code = getattr(module, operation.code.__name__)
            #     migration.operations += [operation]

        # import ipdb; ipdb.set_trace()

#     imports = []
#     for f in sorted(files):
#         if not (f.endswith('.py') and 'migrations' in root) or f.startswith('__init__'):
#             continue
#
#         module_name = '.'.join(root[2:].split('/') + [f[:-3]])
#         module = importlib.import_module(module_name)
#         temp_imports = list(get_imports(os.path.join(root, f)))
#         for operation in all_custom_operations(module.Migration.operations):
#             operations.append(operation)
#             if temp_imports:
#                 imports.extend(temp_imports)
#                 temp_imports = []

        # import ipdb; ipdb.set_trace()
        operations = []
        # imports = []
        # for f in sorted(files):
        #     if not (f.endswith('.py') and 'migrations' in root) or f.startswith('__init__'):
        #         continue
        #
        #     module_name = '.'.join(root[2:].split('/') + [f[:-3]])
        #     module = importlib.import_module(module_name)
        #     temp_imports = list(get_imports(os.path.join(root, f)))
        #     for operation in all_custom_operations(module.Migration.operations):
        #         operations.append(operation)
        #         if temp_imports:
        #             imports.extend(temp_imports)
        #             temp_imports = []
        #
        # if operations:
        #     top_body = []
        #     class_operations = []
        #     for i, operation in enumerate(operations):
        #         if isinstance(operation, module.migrations.RunSQL):
        #             top_body.append(f'SQL_{i + 1} = """\n{operation.sql}\n"""')
        #             class_operations.append(f'migrations.RunSQL(SQL_{i + 1}, elidable=False)')
        #         else:
        #             lines = inspect.getsource(operation.code).splitlines(True)
        #             lines = [c[len(lines[0]) - len(lines[0].lstrip()):] for c in lines]
        #             top_body.append(''.join(lines))
        #             class_operations.append(f'migrations.RunPython({operation.code.__name__}, elidable=False)')

    def replace_current_migrations(self, graph, changes):
        """
        Adds 'replaces' to the squash migrations with all the current apps we have.
        """
        migrations_by_app = defaultdict(list)
        for app, migration in graph.node_map:
            migrations_by_app[app].append((app, migration))

        for app, migrations in changes.items():
            for migration in migrations:
                # TODO: maybe use use a proper order???
                migration.replaces = sorted(migrations_by_app[app])

    def rename_migrations(self, graph, changes, migration_name=None):
        """
        Continues the numbering from whats there now.
        """
        current_counters_by_app = defaultdict(int)
        for app, migration in graph.node_map:
            current_counters_by_app[app] = max([int(migration[:4]), current_counters_by_app[app]])

        for app, migrations in changes.items():
            for migration in migrations:
                next_number = current_counters_by_app[app] + 1
                migration.name = "%04i_%s" % (
                    next_number,
                    migration_name or 'squashed',
                )

    def _detect_changes(self, convert_apps=None, graph=None):
        """
        Swap django.db.migrations.Migration with a custom one that behaves like a tuple.
        """
        super()._detect_changes(convert_apps=convert_apps, graph=graph)

        # First pass, swapping the objects
        migrations_by_name = {}
        for key in self.migrations:
            new_migrations = []
            for migration in self.migrations[key]:
                new_migration = Migration.from_migration(migration)
                new_migrations.append(new_migration)
                migrations_by_name.setdefault(tuple(new_migration), new_migration)
            self.migrations[key] = new_migrations

        # Second pass, replace the tuples with the newly created objects
        for migration in migrations_by_name.values():
            new_dependencies = []
            for dependency in migration.dependencies:
                new_dependencies.append(migrations_by_name[dependency])
            migration.dependencies = new_dependencies

        return self.migrations

    def squash(self, loader, trim_to_apps=None, convert_apps=None, migration_name=None):
        new_graph = MigrationGraph()  # Don't care what the tree is, we want a blank slate
        changes = super().changes(new_graph, trim_to_apps, convert_apps, migration_name)

        graph = loader.graph

        self.rename_migrations(graph, changes, migration_name)
        self.replace_current_migrations(graph, changes)
        self.add_non_elidables(loader, changes)

        return changes


class NonInteractiveMigrationQuestioner(NonInteractiveMigrationQuestionerBase):
    def ask_initial(self, *args, **kwargs):
        # Ensures that the 0001_initial will always be generated
        return True


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'args', metavar='app_label', nargs='*',
            help='Specify the app label(s) to create migrations for.',
        )

    def handle(self, *app_labels, **kwargs):
        self.verbosity = 1
        self.include_header = False
        self.dry_run = False

        # Make sure the app they asked for exists
        app_labels = set(app_labels)
        has_bad_labels = False
        for app_label in app_labels:
            try:
                apps.get_app_config(app_label)
            except LookupError as err:
                self.stderr.write(str(err))
                has_bad_labels = True
        if has_bad_labels:
            sys.exit(2)

        self.migration_name = ''

        loader = MigrationLoader(None, ignore_no_migrations=True)

        questioner = NonInteractiveMigrationQuestioner(specified_apps=app_labels, dry_run=False)
        # Set up autodetector
        autodetector = SquashMigrationAutodetector(
            ProjectState(),
            ProjectState.from_apps(apps),
            questioner,
        )

        changes = autodetector.squash(
            loader=loader,
            trim_to_apps=app_labels or None,
            convert_apps=app_labels or None,
            migration_name=self.migration_name,
        )

        replacing_migrations = 0
        for migration in itertools.chain.from_iterable(changes.values()):
            replacing_migrations += len(migration.replaces)

        if not replacing_migrations:
            raise CommandError("There are no migrations to squash.")

        self.write_migration_files(changes)

    def write_migration_files(self, changes):
        """
        Take a changes dict and write them out as migration files.
        """
        directory_created = {}
        for app_label, app_migrations in changes.items():
            if self.verbosity >= 1:
                self.stdout.write(self.style.MIGRATE_HEADING("Migrations for '%s':" % app_label) + "\n")
            for migration in app_migrations:
                # Describe the migration
                writer = MigrationWriter(migration, self.include_header)
                if self.verbosity >= 1:
                    # Display a relative path if it's below the current working
                    # directory, or an absolute path otherwise.
                    try:
                        migration_string = os.path.relpath(writer.path)
                    except ValueError:
                        migration_string = writer.path
                    if migration_string.startswith('..'):
                        migration_string = writer.path
                    self.stdout.write("  %s\n" % (self.style.MIGRATE_LABEL(migration_string),))
                    for operation in migration.operations:
                        self.stdout.write("    - %s\n" % operation.describe())
                if not self.dry_run:
                    # Write the migrations file to the disk.
                    migrations_directory = os.path.dirname(writer.path)
                    if not directory_created.get(app_label):
                        os.makedirs(migrations_directory, exist_ok=True)
                        init_path = os.path.join(migrations_directory, "__init__.py")
                        if not os.path.isfile(init_path):
                            open(init_path, "w").close()
                        # We just do this once per app
                        directory_created[app_label] = True
                    migration_string = writer.as_string()
                    with open(writer.path, "w", encoding='utf-8') as fh:
                        fh.write(migration_string)
                elif self.verbosity == 3:
                    # Alternatively, makemigrations --dry-run --verbosity 3
                    # will output the migrations to stdout rather than saving
                    # the file to the disk.
                    self.stdout.write(self.style.MIGRATE_HEADING(
                        "Full migrations file '%s':" % writer.filename) + "\n"
                    )
                    self.stdout.write("%s\n" % writer.as_string())


#
# #!/usr/bin/env bash
#
# set -e
#
# # Run the delete_squashed_migrations script BEFORE this script.
# # Read the documentation in that script for the flow of how these 2 scripts work together.
#
# # Pass all args from squash_migrations into can_squash. Realistically, we expect --force to be passed because when we
# # fail the can_squash check, we explain that --force will make it pass.
# can_squash $@
#
# export PYTHONWARNINGS="ignore"
# cd .
#
# # to test and start all over if all else fails
# # git reset .; find . -type d -path "*/migrations" -exec rm -rf {} +; git checkout -- .
#
#
# # Make print pretty.
# cprintf() {
#   # Shamelessly copied from: https://serverfault.com/questions/59262/bash-print-stderr-in-red-color#answer-59299
#   # with some tweeks
#   printf '\033[%sm%s\033[m\n' "${2:-'34;1'}" "$1"
#   # usage color "31;5" "string"
#   # 0 default
#   # 5 blink, 1 strong, 4 underlined
#   # fg: 31 red,  32 green, 33 yellow, 34 blue, 35 purple, 36 cyan, 37 white
#   # bg: 40 black, 41 red, 44 blue, 45 purple
#
#   # To debug, uncomment the line below
#   # read -p "Press enter to continue"
# }
#
#
# # Find all RunSQL and RunPython operations that did not specify the elidable param.
# cprintf 'Testing for elidable settings in the migration'
# ERRORS_FOUND=$(IFS=$'\n'; for part in $(grep -r "RunSQL\|RunPython" $(find . -type f -path "*/migrations/*.py") | perl -ne 'print if ! /\s+#/' | grep -v elidable); do
#   filepath=$(echo $part | cut -d ':' -f 1);
#   match=$(echo $part | cut -d ':' -f 2-);
#   search_for=$(echo $match | perl -pe 's/.*\((?:sql=|code=|)(\w+).*/$1/g');
#   found_at=$(grep -nirom 1 "$search_for" $filepath);
#   echo "$filepath:$(echo $found_at | cut -d ':' -f 1)";
# done
# )
#
#
# # Stop this script until elidable problems have been fixed.
# [ ! -z "$ERRORS_FOUND" ] && {
#   printf "Found some issues with migrations not having 'elidable':\n$ERRORS_FOUND\n\nCannot continue until you fix them.\n";
#   exit;
# }
#
#
# # Instead of squashing migrations, we are going to create initial migrations from the current model definitions.
# # This will cause us to lose RunSQL & RunPython operations that are elidable. We don't care about those.
# # This will cause us to lose RunSQL & RunPython operations that are NOT elidable. We need to remember/keep these.
# # The following code saves all non-elidable SQL variables, non-elidable functions, their imports, and their operations.
# # They are saved into save.p in the corresponding "migrations" directory.
# cprintf 'Saving all the variables/functions that are not elidable'
# (cat <<EOF
# import inspect, importlib, django, os, pickle, ast
# django.setup()
#
# # We need to generate all the RunSQL/RunPython functions before we convert them into .txt because after it's converted
# # we can no longer import them to traverse the code.
#
# def get_imports(path):
#     """
#     Return an generator with all the imports to a particular py file as string
#     """
#     with open(path) as fh:
#         root = ast.parse(fh.read(), path)
#     for node in ast.iter_child_nodes(root):
#         if isinstance(node, ast.Import):
#             for n in node.names:
#                 yield f'import {n.name}'
#         elif isinstance(node, ast.ImportFrom):
#             module = node.module.split('.')
#             # Remove old python 2.x imports
#             if '__future__' not in node.module:
#                 yield f"from {node.module} import {', '.join([x.name for x in node.names])}"
#         else:
#             continue
#
#
# def all_custom_operations(operations):
#     """
#     Generator that loops over all the operations and traverses sub-operations such as those inside a -
#     SeparateDatabaseAndState class.
#     """
#     for operation in operations:
#         if operation.elidable:
#             continue
#
#         if isinstance(operation, module.migrations.RunSQL) or isinstance(operation, module.migrations.RunPython):
#             yield operation
#         elif isinstance(operation, module.migrations.SeparateDatabaseAndState):
#             yield from all_custom_operations(operation.state_operations)
#             # Just in case we added something in here incorrectly
#             # This should always return nothing since it should NEVER have any RunSQL / RunPython
#             yield from all_custom_operations(operation.database_operations)
#
#
# for root, _, files in os.walk('.'):
#     save_path = os.path.join(root, 'save.p')
#     if os.path.isfile(save_path):
#         continue
#
#     operations = []
#     imports = []
#     for f in sorted(files):
#         if not (f.endswith('.py') and 'migrations' in root) or f.startswith('__init__'):
#             continue
#
#         module_name = '.'.join(root[2:].split('/') + [f[:-3]])
#         module = importlib.import_module(module_name)
#         temp_imports = list(get_imports(os.path.join(root, f)))
#         for operation in all_custom_operations(module.Migration.operations):
#             operations.append(operation)
#             if temp_imports:
#                 imports.extend(temp_imports)
#                 temp_imports = []
#
#     if operations:
#         top_body = []
#         class_operations = []
#         for i, operation in enumerate(operations):
#             if isinstance(operation, module.migrations.RunSQL):
#                 top_body.append(f'SQL_{i + 1} = """\n{operation.sql}\n"""')
#                 class_operations.append(f'migrations.RunSQL(SQL_{i + 1}, elidable=False)')
#             else:
#                 lines = inspect.getsource(operation.code).splitlines(True)
#                 lines = [c[len(lines[0]) - len(lines[0].lstrip()):] for c in lines]
#                 top_body.append(''.join(lines))
#                 class_operations.append(f'migrations.RunPython({operation.code.__name__}, elidable=False)')
#
#         with open(save_path, "wb") as save:
#             pickle.dump({'top_body': '\n'.join(top_body),
#                          'imports': set(imports),
#                          'operations': 'operations += [\n        ' + ",\n        ".join(class_operations) + '\n    ]'
#                         }, save)
#
# EOF
# ) | python
#
#
# # Before running makemigrations to create initial migrations from the current model definitions, we have to eliminate
# # all existing migrations. Rename existing migrations from .py to .txt.
# cprintf 'Renaming the extensions from existing migrations to .txt so we can make new migrations without interference'
# # Find all the files inside */migrations that end in .py and are NOT __init__.py, then rename them to .txt
# find . -type f -path "*/migrations/*.py" ! -name __init__.py -exec sh -c 'mv $1 ${1%.py}.txt' - {} \;
#
#
# # Instead of squashing migrations, we will create initial migrations from current model definitions.
# # This eliminates more operations than what squashing migrations would do.
# # For example, squashing migrations is not smart enough to follow operations that rename field A to field B to field C
# # and figure out that the model could have been created with correct field name C to start with. An initial migration
# # will simply create the model correctly with field C.
# cprintf 'Making new migrations'
# ./manage.py makemigrations
#
#
# # makemigrations creates files named 0001_initial.py, 0002_auto...py, etc. 0002 & higher are created only as needed.
# # Step 1: Rename them to 0001_initial_yyyymmdd.py, 0002_initial_yyyymmdd.py, etc.
# # Step 2: Change their dependencies to use the new file names.
#
# cprintf "Finding all the generated migrations and update the references to the new file name"
# for dir in $(find . -type d -path "*/migrations"); do
#   echo $dir
#   current_val=$(cd $dir; ls *.txt 2> /dev/null | tail -n 1 | cut -c -4 | sed 's/^0*//');
#   app_name=$(cd $dir; cd ..; basename $(pwd))
#   for migration in $(find $dir -type f -name "*.py" ! -name __init__.py); do
#     filename=$(basename $migration)
#     next_number=$(($current_val + $(echo ${filename:0:4} | sed 's/^0*//')))
#     new_filename=$(printf '%04d' $next_number)_initial_$(date +%Y%m%d).py
#     echo "  ${filename%.py} -> ${new_filename%.py}";
#
#     # Rename all the migrations with the new file names
#     replace_files=$(grep -l "'$app_name', '${filename%.py}'" $(find . -type f -path "*/migrations/*.py" ! -name __init__.py) || true);
#     [ -z "$replace_files" ] || (sed -i'.' "s/'$app_name', '${filename%.py}'/'$app_name', '${new_filename%.py}'/g" $replace_files; printf '%s. ' $replace_files | xargs rm)
#     mv $migration $(dirname $migration)/$new_filename
#   done
# done
#
#
# # Insert the previously saved non-elidable operations (in save.p) into the last 000x_initial_yyyymmdd file we created.
# cprintf "Inserting any elidable=False migrations into the new migrations"
# python <(cat <<EOF
# import os, pickle, datetime, ast, collections
#
# def get_imports(source, path):
#     """
#     Return an generator with all the imports to a particular py file as string
#     """
#     root = ast.parse(source, path)
#     for node in ast.iter_child_nodes(root):
#         if isinstance(node, ast.Import):
#             for n in node.names:
#                 yield f'import {n.name}'
#         elif isinstance(node, ast.ImportFrom):
#             module = node.module.split('.')
#             yield f"from {node.module} import {', '.join([x.name for x in node.names])}"
#         else:
#             continue
#
# today = datetime.date.today()
#
# for root, _, files in os.walk('.'):
#     files = sorted([f for f in files if f.endswith('.py') and '__init__' not in f], reverse=True)
#     if not files:
#         continue
#
#     migration_path = os.path.join(root, files[0])
#     save_path = os.path.join(root, 'save.p')
#     if not os.path.isfile(save_path):
#         continue
#
#     with open(save_path, "rb") as load:
#         temp = pickle.load(load)
#         top_body = temp['top_body']
#         operations = temp['operations']
#         original_imports = temp['imports']
#
#     with open(migration_path, 'r') as f:
#         source = f.read()
#
#     imports = list(get_imports(source, migration_path))
#
#     pos_class = source.find('class Migration')
#     source = f'{source[:pos_class -1]}{top_body}\n{source[pos_class:]}'
#     source += '\n    # The ALTER TABLE operations above need to be commited before we can manipulate data rows below'
#     source += f'\n    {operations}\n'
#
#     pos_first_import = source.find(imports[0])
#     pos_last_import = source.find(imports[-1]) + len(imports[-1])
#     new_imports = list(collections.OrderedDict.fromkeys(imports + list(original_imports)))
#     source = f'{source[:pos_first_import]}' + "\n".join(new_imports) + f'\n{source[pos_last_import:]}'
#
#     # # debugging
#     # print('\n\n\n\n')
#     # print(migration_path)
#     # print('\n'.join(imports))
#     # print('-' * 80)
#     # print('\n'.join(set(new_imports)))
#     # print('*' * 80)
#     # print(source[:1000])
#     with open(migration_path, 'w') as f:
#         f.write(source)
#     os.remove(save_path)
# EOF
# )
#
#
# # Goal 1:
# # Old migrations can contain "run_before" statements that were needed to process old migrations in the proper order.
# # But our new initial migrations don't need them. Our old migrations don't need them because we are guaranteed that all
# # old migrations have already run. This is because we do not allow releases to be skipped.
# # Leaving these "run_before" statements in the code brings these backward dependencies into the dependency graph that is
# # build every time migrations are run. This causes circular migration dependency errors when the graph is built.
# # We must simply comment them out in order for our new initial migrations to work.
# # Goal 2:
# # The old migrations might have started with a squashing migration that replaced migrations from the prior release.
# # That squashing migration's "replaced" statement should have been commented out. This step comments it out if it
# # somehow was not commented out like it should have. We are fixing an old existing migration here.
# cprintf "Find all the 'run_before' and 'replaces' statements in the old migrations and comment them out."
# python <(cat <<EOF
# import ast, sys, re, os
#
# def find_brackets(line, p_count, b_count):
#     for char in line:
#         if char == '(':
#             p_count += 1
#         elif char == ')':
#             p_count -= 1
#         elif char == '[':
#             b_count += 1
#         elif char == ']':
#             b_count -= 1
#     return p_count, b_count
#
# def comment_out_old_migration(path):
#     with open(path) as f:
#         source = f.read()
#
#     migration_class = None
#     tree = ast.parse(source)
#     for node in tree.body:
#         if isinstance(node, ast.ClassDef) and node.name == 'Migration':
#             migration_class = node
#             break
#     else:
#         sys.exit()
#
#     comment_out_nodes = {}
#     for node in migration_class.body:
#         if isinstance(node, ast.Assign) and node.targets[0].id in ['replaces', 'run_before']:
#             comment_out_nodes[node.lineno] = (node.targets[0].col_offset, node.targets[0].id,)
#
#     if not comment_out_nodes:
#         return
#
#     p_count = 0
#     b_count = 0
#     col_offset = None
#     name = None
#     output = []
#     for lineno, line in enumerate(source.splitlines()):
#         if lineno + 1 in comment_out_nodes.keys():
#             p_count = 0
#             b_count = 0
#             col_offset, name = comment_out_nodes[lineno + 1]
#             p_count, b_count = find_brackets(line, p_count, b_count)
#             output.append(f'{line[:col_offset - 1]} # {line[col_offset:]}')
#         elif p_count != 0 or b_count != 0:
#             p_count, b_count = find_brackets(line, p_count, b_count)
#             output.append(f'{line[:col_offset - 1]} # {line[col_offset:]}')
#         else:
#             output.append(line)
#
#     with open(path, 'w') as f:
#         f.write('\n'.join(output) + '\n')
#
# for root, _, files in os.walk('.'):
#     if 'migrations' not in root:
#         continue
#
#     for f in files:
#         if f.endswith('.txt'):
#             comment_out_old_migration(os.path.join(root, f))
# EOF
# )
#
#
# # Our initial migrations need to look like squashing migrations that replace the old migrations.
# cprintf "Add the required 'replaces = [...]' statement to each initial migration we just created."
# for file in $(find $(pwd) -type f -path "*/migrations/*.py"); do
#   # echo $(dirname $file);
#   cd $(dirname $file);
#   cp $file $file.dummy;
#   cat $file.dummy | tr '\n' '\r' | sed "s|initial = True|$(printf "replaces = [$(printf "                ('$(cd ..; basename $(pwd))', '%s'),\r" $(ls | grep \.txt) | sed 's/\.txt//g')    ]\r\r" | sed 's|\[                |[|g';)    initial = True|g" | tr '\r' '\n' > $file;
#   rm $file.dummy;
#   cd - > /dev/null;
# done
#
#
# # Now rename all the old migrations back to their original .py extensions.
# cprintf 'Get all existing migrations and convert them back to py'
# find . -type f -path "*/migrations/*.txt" ! -name 0000_* -exec sh -c 'mv $1 ${1%.txt}.py' - {} \;
# # If "eabtest" or "eabtestref" is found, undo all the migration related changes
# find . -type d -path "./eabtest*/migrations*" ! -path '*/__pycache__' -exec bash -c 'rm -rf $0; git checkout -- $0' {} \;
