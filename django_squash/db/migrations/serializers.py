from django.db import migrations as dj_migrations
from django.db.migrations.serializer import FunctionTypeSerializer as BaseFunctionTypeSerializer


class FunctionTypeMigrationSerializer(BaseFunctionTypeSerializer):
    """
    This serializer is used to serialize functions that are in migrations.

    Knows that "migrations" is available in the global namespace, and sets the
    correct import statement for the functions that use it.
    """

    def serialize(self):
        response = super().serialize()

        if hasattr(self.value, '__in_migration_file__'):
            if self.value.__in_migration_file__:
                return self.value.__qualname__, {}
            else:
                collector = ''
                for part in self.value.__qualname__.split('.'):
                    collector += part
                    if hasattr(dj_migrations, collector):
                        return 'migrations.%s' % self.value.__qualname__, {'from django.db import migrations'}
                    collector += '.'

        return response
