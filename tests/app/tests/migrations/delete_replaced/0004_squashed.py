from django.db import migrations, models


def create_admin_MUST_ALWAYS_EXIST(apps, schema_editor):
    Person = apps.get_model("app", "Person")

    Person.objects.create(name="admin", age=30)


class Migration(migrations.Migration):

    replaces = [
        ("app", "0001_initial"),
        ("app", "0002_person_age"),
        ("app", "0003_add_dob"),
    ]

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Person",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=10)),
                ("dob", models.DateField()),
            ],
        ),
        migrations.RunPython(
            code=create_admin_MUST_ALWAYS_EXIST,
        ),
    ]
