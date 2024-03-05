from django.contrib.postgres.operations import BtreeGinExtension
from django.db import migrations


class IgnoreRollbackBtreeGinExtension(BtreeGinExtension):
    """
    Custom extension that doesn't rollback no matter what
    """

    def database_backwards(self, *args, **kwargs):
        pass


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        IgnoreRollbackBtreeGinExtension(),
    ]
