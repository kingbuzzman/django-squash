# Generated by Django 2.0 on 2019-05-18 15:23

from django.db import migrations
from django.db.migrations.operations.special import RunPython


def same_name(apps, schema_editor):
    # other function
    return


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(RunPython.noop),
        migrations.RunPython(same_name),
    ]
