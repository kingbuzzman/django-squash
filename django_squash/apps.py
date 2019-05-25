from django.apps import AppConfig


class DjangoSquashConfig(AppConfig):
    name = 'django_squash'

    def ready(self):
        from django.db.migrations.serializer import Serializer
        from .management.commands.lib.serializer import VariableSerializer
        from .management.commands.lib.operators import Variable
        Serializer.register(Variable, VariableSerializer)
