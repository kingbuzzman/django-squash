import contextlib
import os
import sqlite3
import tarfile
import tempfile
import urllib.request

import pytest

SETTINGS_PY_DIFF = """\
--- original.py	2024-03-19 13:32:55
+++ diff.py	2024-03-19 13:33:05
@@ -31,13 +31,14 @@
 # Application definition

 INSTALLED_APPS = [
-    'polls.apps.PollsConfig',
     'django.contrib.admin',
     'django.contrib.auth',
     'django.contrib.contenttypes',
     'django.contrib.sessions',
     'django.contrib.messages',
     'django.contrib.staticfiles',
+    'django_squash',
+    'polls.apps.PollsConfig',
 ]

 MIDDLEWARE = [
"""


@contextlib.contextmanager
def download_and_extract_tar(url):
    with tempfile.TemporaryDirectory() as tmp_dir:
        filename = os.path.basename(url)
        filepath = os.path.join(tmp_dir, filename)

        # Download the file using urllib
        with urllib.request.urlopen(url) as response, open(filepath, "wb") as f:
            f.write(response.read())

        # Extract the tar.gz file
        with tarfile.open(filepath, "r:gz") as tar:
            replace_path = tar.getmembers()[0].name + "/mysite/"
            for member in tar.getmembers():
                # Remove the root directory
                if "mysite" not in member.name:
                    continue
                member.name = member.name.replace(replace_path, "")  # Remove leading path
                tar.extract(member, tmp_dir, filter="data")

        # Apply the INSTALLED_APPS patch
        with open(f"{tmp_dir}/diff.patch", "w") as f:
            f.write(SETTINGS_PY_DIFF)
        os.system(f"patch {tmp_dir}/mysite/settings.py {tmp_dir}/diff.patch")

        yield tmp_dir


@pytest.mark.slow
def test_standalone_app():
    """
    Test that a standalone (django sample poll) app can be installed using venv.

    This test is slow because it downloads a tar.gz file from the internet, extracts it and
    pip installs django + dependencies. After runs migrations, squashes them, and runs them again!
    """
    url = "https://github.com/consideratecode/django-tutorial-step-by-step/archive/refs/tags/2.0/7.4.tar.gz"
    django_squash = os.getcwd()
    with download_and_extract_tar(url) as tmp_dir, contextlib.chdir(tmp_dir):
        # Setup
        assert os.system("python -m venv venv") == 0
        assert os.system(f"venv/bin/pip install django {django_squash}") == 0

        # Everything works as expected
        assert os.system("DJANGO_SETTINGS_MODULE=mysite.settings venv/bin/python manage.py migrate") == 0
        os.rename("db.sqlite3", "db_original.sqlite3")

        # Squash and run the migrations
        assert os.system("DJANGO_SETTINGS_MODULE=mysite.settings venv/bin/python manage.py squash_migrations") == 0
        # __pycache__ can be present in the migrations folder. We don't care about it.
        assert set(os.listdir("polls/migrations")) == set(["0001_initial.py", "0002_squashed.py", "__init__.py"])
        assert os.system("DJANGO_SETTINGS_MODULE=mysite.settings venv/bin/python manage.py migrate") == 0

        # Check that the squashed migrations schema is the same as the original ones
        original_con = sqlite3.connect("db_original.sqlite3")
        squashed_con = sqlite3.connect("db.sqlite3")
        ocur = original_con.cursor()
        scur = original_con.cursor()

        ores = ocur.execute("select * from sqlite_schema")
        sres = scur.execute("select * from sqlite_schema")
        assert ores.fetchall() == sres.fetchall()

        ocur.close()
        scur.close()
        original_con.close()
        squashed_con.close()
