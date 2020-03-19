# Generated by Django 2.0 on 2019-05-18 15:24

import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_person_age'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='dob',
            field=models.DateField(default=datetime.datetime(1900, 1, 1, 0, 0)),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name='person',
            name='age',
        ),
    ]