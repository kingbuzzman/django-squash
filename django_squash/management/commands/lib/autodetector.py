import ast
import inspect
import itertools
import sys
import types
from collections import defaultdict

from django.conf import settings
from django.db import migrations as migration_module
from django.db.migrations.autodetector import MigrationAutodetector as MigrationAutodetectorBase

from .operators import RunPython, RunSQL


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
    sql_variable_count = 0
    for operation in operations:
        if operation.elidable:
            continue

        if isinstance(operation, migration_module.RunSQL):
            sql_variable_count = sql_variable_count + 1
            yield RunSQL.from_operation(operation, sql_variable_count)
        elif isinstance(operation, migration_module.RunPython):
            yield RunPython.from_operation(operation)
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

    def add_non_elidables(self, original, loader, changes):
        replacing_migrations_by_app = {app: [original.disk_migrations[r]
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
                        operation.code.__module__ = 'DELETEMEPLEASE'  # TODO: get a better name?
                        if operation.reverse_code:
                            operation.reverse_code = copy_func(operation.reverse_code)
                            operation.reverse_code.__module__ = 'DELETEMEPLEASE'  # TODO: get a better name?
                    operations.append(operation)

            migration = changes[app][-1]
            migration.operations += operations
            migration.extra_imports = imports

    def replace_current_migrations(self, original, graph, changes):
        """
        Adds 'replaces' to the squash migrations with all the current apps we have.
        """
        migrations_by_app = defaultdict(list)
        for app, migration in original.graph.node_map:
            migrations_by_app[app].append((app, migration))

        for app, migrations in changes.items():
            for migration in migrations:
                # TODO: maybe use use a proper order???
                migration.replaces = sorted(migrations_by_app[app])

    def rename_migrations(self, original, graph, changes, migration_name=None):
        """
        Continues the numbering from whats there now.
        """
        current_counters_by_app = defaultdict(int)
        for app, migration in original.graph.node_map:
            current_counters_by_app[app] = max([int(migration[:4]), current_counters_by_app[app]])

        for app, migrations in changes.items():
            for migration in migrations:
                next_number = current_counters_by_app[app] = current_counters_by_app[app] + 1
                migration.name = "%04i_%s" % (
                    next_number,
                    migration_name or 'squashed',
                )

    def convert_migration_references_to_objects(self, original, graph, changes):
        """
        Swap django.db.migrations.Migration with a custom one that behaves like a tuple when read, but is still an
        object for the purpose of easy renames.
        """
        migrations_by_name = {}
        # First pass, swapping existing migration objects
        for (app, _), migrations in itertools.groupby(original.disk_migrations.items(), lambda x: x[0]):
            for _, migration in migrations:
                new_migration = Migration.from_migration(migration)
                migrations_by_name.setdefault(tuple(new_migration), new_migration)

        # Second pass, swapping new objects
        for key in changes.keys():
            new_migrations = []
            for migration in self.migrations[key]:
                migration_id = migration.app_label, migration.name
                new_migration = migrations_by_name.get(migration_id)
                if not new_migration:
                    new_migration = Migration.from_migration(migration)
                    migrations_by_name.setdefault(migration_id, new_migration)
                new_migrations.append(new_migration)
            changes[key] = new_migrations

        # Third pass, replace the tuples with the newly created objects
        for migration in migrations_by_name.values():
            new_dependencies = []
            for dependency in migration.dependencies:
                if dependency[0] == "__setting__":
                    app_label = getattr(settings, dependency[1]).split('.')[0]
                    migrations = [migration for (app, _), migration in migrations_by_name.items() if app == app_label]
                    dependency = tuple(migrations[-1])
                elif dependency[1] == "__first__":
                    dependency = original.graph.root_nodes(dependency[0])[0]
                elif dependency[1] == "__latest__":
                    dependency = original.graph.leaf_nodes(dependency[0])[0]

                new_dependencies.append(migrations_by_name[dependency])
            migration.dependencies = new_dependencies

    def squash(self, real_loader, squash_loader, trim_to_apps=None, convert_apps=None, migration_name=None):
        graph = squash_loader.graph
        changes = super().changes(graph, trim_to_apps, convert_apps, migration_name)

        self.convert_migration_references_to_objects(real_loader, graph, changes)
        self.rename_migrations(real_loader, graph, changes, migration_name)
        self.replace_current_migrations(real_loader, graph, changes)
        self.add_non_elidables(real_loader, squash_loader, changes)

        return changes
