import ast
import datetime
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

from .operators import RunPython, RunSQL


def source_directory(module):
    return os.path.dirname(os.path.abspath(inspect.getsourcefile(module)))


class Migration(migration_module.Migration):

    _deleted = False
    _dependencies_change = False
    _replaces_change = False

    def describe(self):
        if self._deleted:
            yield 'Deleted'
        if self._dependencies_change:
            yield '"dependencies" changed'
        if self._replaces_change:
            yield '"replaces" keyword removed'

    @property
    def is_migration_level(self):
        return self._deleted or self._dependencies_change or self._replaces_change

    def __getitem__(self, index):
        return (self.app_label, self.name)[index]

    def __iter__(self):
        yield from (self.app_label, self.name)

    @classmethod
    def from_migration(cls, migration):
        new = Migration(name=migration.name, app_label=migration.app_label)
        new.__dict__ = migration.__dict__.copy()
        new._original_migration = migration
        return new


class UniqueVariableName:
    def __init__(self):
        self.names = defaultdict(int)

    def __call__(self, name, force_number=False):
        self.names[name] += 1
        count = self.names[name]
        if not force_number and count == 1:
            return name
        else:
            new_name = '%s_%s' % (name, count)
            # Make sure that the function name is fully unique
            # You can potentially have the same name already defined.
            return self(new_name)


def all_custom_operations(operations, unique_names):
    """
    Generator that loops over all the operations and traverses sub-operations such as those inside a -
    SeparateDatabaseAndState class.
    """

    for operation in operations:
        if operation.elidable:
            continue

        if isinstance(operation, migration_module.RunSQL):
            yield RunSQL.from_operation(operation, unique_names)
        elif isinstance(operation, migration_module.RunPython):
            yield RunPython.from_operation(operation, unique_names)
        elif isinstance(operation, migration_module.SeparateDatabaseAndState):
            # A valid use case for this should be given before any work is done.
            pass


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
    func = types.FunctionType(f.__code__, f.__globals__, name or f.__qualname__,
                              f.__defaults__, f.__closure__)
    func.__qualname__ = f.__qualname__
    func.__original_qualname__ = f.__original_qualname__
    return func


class SquashMigrationAutodetector(MigrationAutodetectorBase):

    def add_non_elidables(self, original, loader, changes):
        unique_names = UniqueVariableName()
        replacing_migrations_by_app = {app: [original.disk_migrations[r]
                                             for r in itertools.chain.from_iterable([m.replaces for m in migrations])]
                                       for app, migrations in changes.items()}

        for app in changes.keys():
            operations = []
            imports = []

            for migration in replacing_migrations_by_app[app]:
                module = sys.modules[migration.__module__]
                imports.extend(get_imports(module))
                for operation in all_custom_operations(migration.operations, unique_names):
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
                # TODO: maybe use a proper order???
                migration.replaces = sorted(migrations_by_app[app])

    def rename_migrations(self, original, graph, changes, migration_name):
        """
        Continues the numbering from whats there now.
        """
        current_counters_by_app = defaultdict(int)
        for app, migration in original.graph.node_map:
            current_counters_by_app[app] = max([int(migration[:4]), current_counters_by_app[app]])

        for app, migrations in changes.items():
            for migration in migrations:
                next_number = current_counters_by_app[app] = current_counters_by_app[app] + 1
                migration_name = datetime.datetime.now().strftime(migration_name)
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

        # First pass, swapping new objects
        for app_label, migrations in changes.items():
            new_migrations = []
            for migration in migrations:
                migration_id = migration.app_label, migration.name
                new_migration = Migration.from_migration(migration)
                migrations_by_name[migration_id] = new_migration
                new_migrations.append(new_migration)
            changes[app_label] = new_migrations

        # Second pass, replace the tuples with the newly created objects
        for app_label, migrations in changes.items():
            for migration in migrations:
                new_dependencies = []
                for dependency in migration.dependencies:
                    if dependency[0] == "__setting__":
                        app_label = getattr(settings, dependency[1]).split('.')[0]
                        migrations = [migration for (app, _), migration in migrations_by_name.items()
                                      if app == app_label]
                        dependency = tuple(migrations[-1])
                    elif dependency[1] == "__first__":
                        dependency = original.graph.root_nodes(dependency[0])[0]
                    elif dependency[1] == "__latest__":
                        dependency = original.graph.leaf_nodes(dependency[0])[0]

                    migration_id = dependency
                    if migration_id not in migrations_by_name:
                        new_migration = Migration.from_migration(original.disk_migrations[migration_id])
                        migrations_by_name[migration_id] = new_migration
                    new_dependencies.append(migrations_by_name[migration_id])

                migration.dependencies = new_dependencies

    def create_deleted_models_migrations(self, loader, changes):
        migrations_by_label = defaultdict(list)
        for (app, ident), _ in itertools.groupby(loader.disk_migrations.items(), lambda x: x[0]):
            migrations_by_label[app].append(ident)

        for app_config in loader.project_state().apps.get_app_configs():
            if app_config.models and app_config.label in migrations_by_label:
                migrations_by_label.pop(app_config.label)

        for app_label, migrations in migrations_by_label.items():
            subclass = type("Migration", (Migration,), {"operations": [], "dependencies": []})
            instance = subclass("temp", app_label)
            instance.replaces = migrations
            changes[app_label] = [instance]

    def squash(self, real_loader, squash_loader, ignore_apps=None, migration_name=None):
        changes_ = self.delete_old_squashed(real_loader, ignore_apps)

        graph = squash_loader.graph
        changes = super().changes(graph, trim_to_apps=None, convert_apps=None, migration_name=None)

        for app in ignore_apps:
            changes.pop(app, None)

        self.create_deleted_models_migrations(real_loader, changes)
        self.convert_migration_references_to_objects(real_loader, graph, changes)
        self.rename_migrations(real_loader, graph, changes, migration_name)
        self.replace_current_migrations(real_loader, graph, changes)
        self.add_non_elidables(real_loader, squash_loader, changes)

        for app, change in changes_.items():
            changes[app].extend(change)

        return changes

    def delete_old_squashed(self, loader, ignore_apps=None):
        changes = defaultdict(set)
        project_path = os.path.abspath(os.curdir)
        project_apps = [app.label for app in apps.get_app_configs()
                        if source_directory(app.module).startswith(project_path)]

        real_migrations = (Migration.from_migration(loader.disk_migrations[key])
                           for key in loader.graph.node_map.keys())
        project_migrations = [migration for migration in real_migrations
                              if migration.app_label in project_apps and migration.app_label not in ignore_apps or []]
        replaced_migrations = [Migration.from_migration(migration)
                               for migration in project_migrations if migration.replaces]

        migrations_to_remove = set()
        for migration in (y for x in replaced_migrations for y in x.replaces if y[0] not in ignore_apps or []):
            real_migration = Migration.from_migration(loader.disk_migrations[migration])
            real_migration._deleted = True
            migrations_to_remove.add(migration)
            changes[migration[0]].add(real_migration)

        # Remove all the old dependencies that will be removed
        for migration in project_migrations:
            new_dependencies = [migration for migration in migration.dependencies
                                if migration not in migrations_to_remove]
            if new_dependencies == migration.dependencies:
                # There is no need to write anything
                continue
            migration._dependencies_change = True
            changes[migration.app_label].add(migration)
            setattr(migration, 'dependencies', new_dependencies)

        for migration in replaced_migrations:
            migration._replaces_change = True
            changes[migration.app_label].add(migration)
            setattr(migration, 'replaces', [])

        return changes
