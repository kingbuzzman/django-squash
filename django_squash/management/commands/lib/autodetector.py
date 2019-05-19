import ast
import inspect
import itertools
import os
import sys
import types
from collections import defaultdict

from django.apps import apps
from django.conf import settings
from django.db import migrations as migration_module
from django.db.migrations.autodetector import MigrationAutodetector as MigrationAutodetectorBase
from django.db.migrations.graph import MigrationGraph


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
                    if isinstance(operation, migration_module.RunPython):
                        operation.code = copy_func(operation.code)
                        # TODO: get a better name?
                        operation.code.__module__ = 'DELETEMEPLEASE'
                    operations.append(operation)

            migration = changes[app][-1]
            migration.operations += operations
            migration.extra_imports = imports

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
        for key in self.migrations.keys():
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
                if dependency[0] == "__setting__":
                    dependency = getattr(settings, dependency[1]).split('.')[0], 'auto_1'
                migration = migrations_by_name[dependency]
                new_dependencies.append(migrations_by_name[dependency])
            migration.dependencies = new_dependencies

        return self.migrations

    def squash(self, loader, trim_to_apps=None, convert_apps=None, migration_name=None):
        project_path = os.path.abspath(os.curdir)
        new_graph = MigrationGraph()  # Don't care what the tree is, we want a blank slate

        def strip_nodes(nodes):
            data = {}
            for key, value in nodes.items():
                module = apps.get_app_config(key[0]).module
                app_path = inspect.getsourcefile(module)
                if not app_path.startswith(project_path):
                    data[key] = value
            return data

        new_graph.nodes = strip_nodes(loader.graph.nodes)
        new_graph.node_map = strip_nodes(loader.graph.node_map)

        changes = super().changes(new_graph, trim_to_apps, convert_apps, migration_name)

        graph = loader.graph

        self.rename_migrations(graph, changes, migration_name)
        self.replace_current_migrations(graph, changes)
        self.add_non_elidables(loader, changes)

        return changes
