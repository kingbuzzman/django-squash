# Generated by Django 2.0 on 2019-05-18 15:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "3000_auto_20190518_1524"),
    ]

    operations = [
        migrations.AlterField(
            model_name="person",
            name="dob",
            field=models.DateField(),
            preserve_default=False,
        ),
    ]
