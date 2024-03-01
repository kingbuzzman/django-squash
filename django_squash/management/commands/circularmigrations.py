import itertools
import os

from django.conf import settings
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError, no_translations
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState

from django_squash import settings as app_settings
from django_squash.db.migrations import serializer
from django_squash.db.migrations.autodetector import SquashMigrationAutodetector
from django_squash.db.migrations.loader import SquashMigrationLoader
from django_squash.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django_squash.db.migrations.writer import MigrationWriter


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    @no_translations
    def handle(self, **kwargs):
        self.verbosity = 1
        self.include_header = False

        dependency_list = settings.INSTALLED_APPS
        apps.all_models

        questioner = NonInteractiveMigrationQuestioner(specified_apps=None, dry_run=False)
        squash_loader = SquashMigrationLoader(None, ignore_no_migrations=True)
        autodetector = SquashMigrationAutodetector(
            squash_loader.project_state(),
            ProjectState.from_apps(apps),
            questioner,
        )

        changes = autodetector.changes(squash_loader.graph, trim_to_apps=None, convert_apps=None, migration_name=None)
        for app_label, migrations in changes.items():
            app_label = apps.get_app_config(app_label).name
            try:
                app_ranking = dependency_list.index(app_label)
            except ValueError:
                print(f"{app_label} not found")
                continue
            for migration in migrations:
                bad_dependencies = []
                for depends_on_app_label, _ in migration.dependencies:
                    if depends_on_app_label == "__setting__":
                        continue
                    depends_on_app_label = apps.get_app_config(depends_on_app_label).name
                    depends_on_app_ranking = dependency_list.index(depends_on_app_label)
                    if depends_on_app_ranking > app_ranking:
                        print(f"* {app_label} ({app_ranking}) > {depends_on_app_label} ({depends_on_app_ranking})")
                        bad_dependencies.append((app_label, depends_on_app_label))

                if not bad_dependencies:
                    continue

                import ipdb; print('\a'); ipdb.sset_trace()
                for operation in migration.operations:
                    for field in operation.fields:
                        continue


                    # elif depends_on_app_ranking < app_ranking:
                    #     print(f"{app_label} ({app_ranking}) < {depends_on_app_label} ({depends_on_app_ranking})")



        a=a


