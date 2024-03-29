# Generated by Django 2.0 on 2019-05-18 15:23

from django.db import migrations, models


def same_name(apps, schema_editor):
    """
    Content not important, testing same function name in multiple migrations
    """
    pass


def same_name_2(apps, schema_editor):
    """
    Content not important, testing same function name in multiple migrations, nasty
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(same_name, elidable=False),
        migrations.RunPython(same_name_2, reverse_code=migrations.RunPython.noop, elidable=False),
        migrations.AddField(
            model_name="person",
            name="age",
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
    ]
