from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("app3", "0001_inital"),
    ]

    operations = [
        migrations.CreateModel(
            name="TranscodeJob",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("job_id", models.CharField(max_length=50, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("S", "Submitted"),
                            ("P", "Progressing"),
                            ("C", "Complete"),
                            ("X", "Canceled"),
                            ("E", "Error"),
                            ("U", "Unknown"),
                        ],
                        default="S",
                        max_length=1,
                    ),
                ),
                ("initial_response_data", models.TextField()),
                ("final_response_data", models.TextField()),
                ("video", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to="app3.Person")),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
