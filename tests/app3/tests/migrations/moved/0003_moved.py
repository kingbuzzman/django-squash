# Generated by Django 2.0 on 2019-05-18 15:24

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("app3", "0002_person_age"),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE TABLE new_table AS
            SELECT * FROM app3_person
            """,
            elidable=True,
        ),
        migrations.DeleteModel(
            name="Person",
        ),
    ]
