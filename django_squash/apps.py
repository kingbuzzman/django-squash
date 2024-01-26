from django.apps import AppConfig
from django.db.migrations.serializer import Serializer


class DjangoSquashConfig(AppConfig):
    name = 'django_squash'

    def ready(self):
        from django_squash.db.migrations.operators import Variable
        from django_squash.db.migrations.serializer import VariableSerializer

        Serializer.register(Variable, VariableSerializer)
