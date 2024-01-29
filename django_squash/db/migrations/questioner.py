from django.db.migrations.questioner import NonInteractiveMigrationQuestioner as NonInteractiveMigrationQuestionerBase


class NonInteractiveMigrationQuestioner(NonInteractiveMigrationQuestionerBase):
    def ask_initial(self, *args, **kwargs):
        # Ensures that the 0001_initial will always be generated
        return True
