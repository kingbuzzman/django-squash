import os
import sys
from itertools import takewhile

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, no_translations
from django.db import DEFAULT_DB_ALIAS, connection, connections, router
from django.db.migrations import Migration
from django.db.migrations.autodetector import MigrationAutodetector as MigrationAutodetectorBase
from django.db.migrations.graph import MigrationGraph
from django.db.migrations.loader import MigrationLoader as MigrationLoaderBase
from django.db.migrations.questioner import (
    InteractiveMigrationQuestioner, MigrationQuestioner, NonInteractiveMigrationQuestioner,
)
from django.db.migrations.state import ProjectState
from django.db.migrations.utils import get_migration_name_timestamp
from django.db.migrations.writer import MigrationWriter


class MigrationLoader(MigrationLoaderBase):
    pass
    def load_disk(self):
        """Load the migrations from all INSTALLED_APPS from disk."""
        self.disk_migrations = {}
        self.unmigrated_apps = set()
        self.migrated_apps = set()

class MigrationAutodetector(MigrationAutodetectorBase):
    pass

    def squash(self, graph, trim_to_apps=None, convert_apps=None, migration_name=None):
        changes = super().changes(graph, trim_to_apps, convert_apps, migration_name)
        return changes


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'args', metavar='app_label', nargs='*',
            help='Specify the app label(s) to create migrations for.',
        )

    def handle(self, *app_labels, **kwargs):
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
        autodetector = MigrationAutodetector(
            # loader.project_state(),
            ProjectState(),
            # ProjectState.from_apps(apps),
            ProjectState.from_apps(apps),
            questioner,
        )
        changes = autodetector.squash(
            graph=loader.graph,
            trim_to_apps=app_labels or None,
            convert_apps=app_labels or None,
            migration_name=self.migration_name,
        )
        import ipdb; ipdb.set_trace()


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
