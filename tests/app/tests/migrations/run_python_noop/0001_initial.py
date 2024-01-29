# Generated by Django 2.0 on 2019-05-18 15:22

from django.db import migrations
from django.db.migrations import RunPython

OtherRunPython = RunPython
noop = OtherRunPython.noop


def same_name(apps, schema_editor):
    # original function
    return


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    def same_name_2(apps, schema_editor):
        # original function 2
        return

    operations = [
        migrations.RunPython(same_name, migrations.RunPython.noop),
        migrations.RunPython(noop, OtherRunPython.noop),
        migrations.RunPython(same_name_2, same_name),
        migrations.RunPython(same_name, same_name_2),
    ]
