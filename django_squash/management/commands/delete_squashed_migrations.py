import ast
import inspect
import os
import sys

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.migrations.loader import MigrationLoader


def find_brackets(line, p_count, b_count):
    for char in line:
        if char == '(':
            p_count += 1
        elif char == ')':
            p_count -= 1
        elif char == '[':
            b_count += 1
        elif char == ']':
            b_count -= 1
    return p_count, b_count


def remove_old_migration_replace(migration_module):
    """
    Remove the 'replaces' statement in squashING migration files.
    """
    source = inspect.getsource(migration_module)
    path = inspect.getsourcefile(migration_module)

    tree = ast.parse(source)
    # Skip this file if it is not a migration.
    migration_node = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'Migration':
            migration_node = node
            break
    else:
        return

    # Find the "replaces" statement.
    comment_out_nodes = {}
    for node in migration_node.body:
        if isinstance(node, ast.Assign) and node.targets[0].id == 'replaces':
            comment_out_nodes[node.lineno] = (node.targets[0].col_offset, node.targets[0].id,)

    # Skip this migration if it does not replace (AKA squash) other migrations.
    if not comment_out_nodes:
        return

    # Remove the lines that form the multi-line "replaces" statement.
    p_count = 0
    b_count = 0
    col_offset = None
    name = None
    output = []
    for lineno, line in enumerate(source.splitlines()):
        if lineno + 1 in comment_out_nodes.keys():
            p_count = 0
            b_count = 0
            col_offset, name = comment_out_nodes[lineno + 1]
            p_count, b_count = find_brackets(line, p_count, b_count)
        elif p_count != 0 or b_count != 0:
            p_count, b_count = find_brackets(line, p_count, b_count)
        else:
            output.append(line)

    # Overwrite the existing migration file to update it.
    with open(path, 'w') as f:
        f.write('\n'.join(output) + '\n')


def source_directory(module):
    return os.path.dirname(os.path.abspath(inspect.getsourcefile(module)))


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'args', metavar='app_label', nargs='*',
            help='Specify the app label(s) to create migrations for.',
        )

        parser.add_argument(
            '--exclude-apps', metavar='exclude_apps', default='',
            help='Specify the app label(s) you want to exclude migrations for.',
        )

    def handle(self, *app_labels, **kwargs):
        kwargs['exclude_apps'] = kwargs['exclude_apps'].split(',')

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

        loader = MigrationLoader(None, ignore_no_migrations=True)

        project_path = os.path.abspath(os.curdir)
        project_apps = [app.label for app in apps.get_app_configs()
                        if source_directory(app.module).startswith(project_path) and
                        app.label not in kwargs['exclude_apps']]

        real_migrations = (loader.disk_migrations[key] for key in loader.graph.node_map.keys())
        project_migrations = [migration for migration in real_migrations if migration.app_label in project_apps]
        replaced_migrations = [migration for migration in project_migrations if migration.replaces]
        migrations_to_delete = set([inspect.getsourcefile(loader.disk_migrations[y].__class__)
                                    for x in replaced_migrations for y in x.replaces])

        for migration in replaced_migrations:
            remove_old_migration_replace(sys.modules[migration.__class__.__module__])

        for path in migrations_to_delete:
            os.remove(path)
