import django.contrib.contenttypes.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
    ]

    def forwards_func(apps, schema_editor):
        return

    operations = [
        migrations.AddField(
            model_name="transcodejob",
            name="content_type",
            field=models.IntegerField(null=True, verbose_name=django.contrib.contenttypes.models.ContentType),
        ),
        migrations.AddField(
            model_name="transcodejob",
            name="object_id",
            field=models.BigIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name="transcodejob",
            name="job_id",
            field=models.CharField(max_length=50, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="transcodejob",
            name="status",
            field=models.CharField(
                choices=[
                    ("R", "Ready"),
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
        migrations.AlterField(
            model_name="transcodejob",
            name="video",
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to="app3.Person"),
        ),
        migrations.AlterIndexTogether(
            name="transcodejob",
            index_together=set([("content_type", "object_id")]),
        ),
        migrations.RunPython(forwards_func, reverse_code=migrations.RunPython.noop),
    ]
