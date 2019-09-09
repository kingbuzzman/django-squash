import ast
import inspect
import os
import sys

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState

from .lib.questioner import NonInteractiveMigrationQuestioner
from .lib.autodetector import SquashMigrationAutodetector


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
        questioner = NonInteractiveMigrationQuestioner(specified_apps=app_labels, dry_run=False)

        # Set up autodetector
        autodetector = SquashMigrationAutodetector(
            loader.project_state(),
            ProjectState.from_apps(apps),
            questioner,
        )

        autodetector.delete_old_squashed(loader)
