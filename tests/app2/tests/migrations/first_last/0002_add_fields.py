# Generated by Django 2.0 on 2019-05-18 15:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app2", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="Address",
            name="address1",
            field=models.CharField(max_length=100, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="Address",
            name="address2",
            field=models.CharField(max_length=100, default=""),
            preserve_default=False,
        ),
    ]