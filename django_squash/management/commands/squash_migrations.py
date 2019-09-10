import itertools
import os

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState

from .lib.autodetector import SquashMigrationAutodetector
from .lib.loader import SquashMigrationLoader
from .lib.questioner import NonInteractiveMigrationQuestioner
from .lib.writer import MigrationWriter


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--ignore-app',  action='append', nargs='*',
            help='Ignore app name from quashing, ensure that there is nothing dependent on these apps.',
        )
        parser.add_argument(
            '--squashed-name',
            help='Sets the name of the new squashed migration. (default: "squashed" -> "xxxx_squashed")',
        )

    def handle(self, **kwargs):
        self.verbosity = 1
        self.include_header = False
        self.dry_run = False
        self.migration_name = kwargs.get('squashed_name')

        ignore_apps = []
        bad_apps = []
        for app_label in itertools.chain.from_iterable(kwargs['ignore_app'] or []):
            try:
                apps.get_app_config(app_label)
                ignore_apps.append(app_label)
            except LookupError:
                bad_apps.append(app_label)
        if bad_apps:
            raise CommandError("The following apps are not valid: %s" % (', '.join(bad_apps)))

        questioner = NonInteractiveMigrationQuestioner(specified_apps=None, dry_run=False)

        loader = MigrationLoader(None, ignore_no_migrations=True)
        squash_loader = SquashMigrationLoader(None, ignore_no_migrations=True)

        # Set up autodetector
        autodetector = SquashMigrationAutodetector(
            squash_loader.project_state(),
            ProjectState.from_apps(apps),
            questioner,
        )

        autodetector.delete_old_squashed(loader, ignore_apps)

        squashed_changes = autodetector.squash(
            real_loader=loader,
            squash_loader=squash_loader,
            ignore_apps=ignore_apps,
            migration_name=self.migration_name,
        )

        replacing_migrations = 0
        for migration in itertools.chain.from_iterable(squashed_changes.values()):
            replacing_migrations += len(migration.replaces)

        if not replacing_migrations:
            raise CommandError("There are no migrations to squash.")

        self.write_migration_files(squashed_changes)

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
