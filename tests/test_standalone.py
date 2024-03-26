import contextlib
from functools import lru_cache
import os
import sqlite3
import tarfile
import tempfile
import urllib.request
import http
import hashlib
import pathlib

import pytest

from django_squash import __version__ as version
from tests import utils

if utils.is_pyvsupported("3.11"):
    try:
        from contextlib import chdir
    except ImportError:
        # Delete after python 3.10 is no longer supported (31 Oct 2026)
        @contextlib.contextmanager
        def chdir(path):
            prev_cwd = os.getcwd()
            os.chdir(path)
            try:
                yield
            finally:
                os.chdir(prev_cwd)

else:
    raise Exception("Remove this whole block please! and use contextlib.chdir instead.")


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


@lru_cache(maxsize=1)
def temp_global_file():
    hash_object = hashlib.sha256()

    # Update the hash object with the bytes of the input string
    hash_object.update(version.encode('utf-8'))

    # Obtain the hexadecimal representation of the digest
    hex_dig = hash_object.hexdigest()

    path = pathlib.Path(tempfile.gettempdir()) / f'django_squash_{hex_dig}'
    os.makedirs(path, exist_ok=True)
    return path


@contextlib.contextmanager
def download_and_extract_tar(url, filename):
    filepath = temp_global_file() / filename
    etag_path = temp_global_file() / 'etag.txt'
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Try to load the ETag from a local file (etag.txt)
        if os.path.exists(etag_path):
            with open(etag_path, "r") as f:
                etag = f.read().strip()
        else:
            etag = None

        request = urllib.request.Request(url)

        # If we have an ETag, add an If-None-Match header to the request
        if etag:
            request.add_header('If-None-Match', etag)

        try:
            # Download the file using urllib
            with urllib.request.urlopen(request) as response, open(filepath, "wb") as f:
                if response.status != http.HTTPStatus.OK:
                    raise Exception('Download error!')

                f.write(response.read())

                new_etag = response.headers.get('ETag')

                # Save the new ETag for next time
                if new_etag:
                    with open(etag_path, "w") as f:
                        f.write(new_etag)
        except urllib.error.HTTPError as e:
            if e.code != http.HTTPStatus.NOT_MODIFIED:
                raise

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

        with chdir(tmp_dir):
            yield tmp_dir


@pytest.mark.slow
def test_standalone_app():
    """
    Test that a standalone (django sample poll) app can be installed using venv.

    This test is slow because it downloads a tar.gz file from the internet, extracts it and
    pip installs django + dependencies. After runs migrations, squashes them, and runs them again!
    """
    url = "https://github.com/consideratecode/django-tutorial-step-by-step/archive/refs/tags/2.0/7.4.tar.gz"
    # This is a full django_squash package, with a copy of all the code, crucial for testing
    # This will alert us if a new module is added but not included in the final package
    project_path = os.getcwd()
    with download_and_extract_tar(url, 'django-tutorial.tar'):
        # Build the package from scratch
        assert os.system(f"python3 -m build {project_path} --outdir=./dist") == 0
        assert sorted(os.listdir("dist")) == [
            f"django_squash-{version}-py3-none-any.whl",
            f"django_squash-{version}.tar.gz",
        ]

        # Setup
        assert os.system("python -m venv venv") == 0
        assert os.system(f"venv/bin/pip install django dist/django_squash-{version}-py3-none-any.whl") == 0

        # Everything works as expected
        assert os.system("DJANGO_SETTINGS_MODULE=mysite.settings venv/bin/python manage.py migrate") == 0
        os.rename("db.sqlite3", "db_original.sqlite3")

        # Squash and run the migrations
        assert os.system("DJANGO_SETTINGS_MODULE=mysite.settings venv/bin/python manage.py squash_migrations") == 0
        # __pycache__ can be present in the migrations folder. We don't care about it.
        actual_files = sorted(set(os.listdir("polls/migrations")) - set(["__pycache__"]))
        assert actual_files == ["0001_initial.py", "0002_squashed.py", "__init__.py"]
        assert os.system("DJANGO_SETTINGS_MODULE=mysite.settings venv/bin/python manage.py migrate") == 0

        original_con = sqlite3.connect("db_original.sqlite3")
        squashed_con = sqlite3.connect("db.sqlite3")

        # Check that the squashed migrations schema is the same as the original ones
        sql = "select name, tbl_name, sql from sqlite_schema"
        assert original_con.execute(sql).fetchall() == squashed_con.execute(sql).fetchall()

        # Check that the migrations were applied
        sql = "select name from django_migrations where app = 'polls' order by name"
        assert original_con.execute(sql).fetchall() == [("0001_initial",)]
        assert squashed_con.execute(sql).fetchall() == [("0001_initial",), ("0002_squashed",)]

        original_con.close()
        squashed_con.close()
