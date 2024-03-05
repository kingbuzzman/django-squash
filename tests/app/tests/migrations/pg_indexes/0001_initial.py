from django.contrib.postgres.operations import BtreeGinExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        BtreeGinExtension(),
    ]
