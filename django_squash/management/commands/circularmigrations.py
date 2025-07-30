from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, no_translations
from django.db.migrations.state import ProjectState

from django_squash.db.migrations.autodetector import SquashMigrationAutodetector
from django_squash.db.migrations.loader import SquashMigrationLoader
from django_squash.db.migrations.questioner import NonInteractiveMigrationQuestioner


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

        changes = autodetector.changes(
            squash_loader.graph,
            trim_to_apps=None,
            convert_apps=None,
            migration_name=None,
        )
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
                        bad_dependencies.append(depends_on_app_label.split(".")[-1])

                if not bad_dependencies:
                    continue

                references_found = []
                for operation in migration.operations:
                    if hasattr(operation, "field") and hasattr(operation.field, "related_model"):
                        if apps.get_model(operation.field.related_model)._meta.app_label in bad_dependencies:
                        # if operation.field.related_model._meta.app_label in bad_dependencies:
                            references_found.append(
                                (
                                    operation.model_name,
                                    operation.name,
                                    operation.field.related_model,
                                )
                            )

                    if hasattr(operation, "fields"):
                        for name, field in operation.fields:
                            if (
                                hasattr(field, "related_model")
                                and field.related_model
                                and not isinstance(field.related_model, str)
                            ):
                                if apps.get_model(operation.field.related_model)._meta.app_label in bad_dependencies:
                                # if field.related_model._meta.app_label in bad_dependencies:
                                    references_found.append((operation.name, name, field.related_model))

                for model_name, field_name, model in references_found:
                    print(
                        f"  references {model._meta.app_label}.{model._meta.object_name} via {model_name}.{field_name}"
                    )
                if references_found:
                    raise CommandError("Bad dependencies found")
