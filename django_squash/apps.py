from django.apps import AppConfig


class DjangoSquashConfig(AppConfig):
    name = 'django_squash'

    def ready(self):
        from .management.commands.lib.serializer import VariableSerializer
        from .management.commands.lib.operators import Variable

        try:
            from django.db.migrations.serializer import Serializer
            Serializer.register(Variable, VariableSerializer)
        except ImportError:
            # If django < 2.2
            from django.db.migrations import serializer

            if hasattr(serializer, '_serializer_factory'):
                # We already patched it.
                return

            def patch_old_serializer_factory(value):
                if isinstance(value, Variable):
                    return VariableSerializer(value)
                return serializer._serializer_factory(value)

            serializer._serializer_factory = serializer.serializer_factory
            serializer.serializer_factory = patch_old_serializer_factory
