from django.apps import AppConfig
from django.db.migrations.serializer import Serializer


class DjangoSquashConfig(AppConfig):
    name = 'django_squash'

    def ready(self):
        from .management.commands.lib.operators import Variable
        from .management.commands.lib.serializer import VariableSerializer

        Serializer.register(Variable, VariableSerializer)
