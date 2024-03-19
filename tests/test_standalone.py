import pytest
import urllib.request
import tarfile
import tempfile
import os
import contextlib


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
            for chunk in iter(lambda: response.read(1024), b''):
                if not chunk:
                    break
                f.write(chunk)

        # Extract the tar.gz file
        with tarfile.open(filepath, "r:gz") as tar:
            replace_path = tar.getmembers()[0].name + '/mysite/'
            for member in tar.getmembers():
                # Remove the root directory
                if 'mysite' not in member.name:
                    continue
                member.name = member.name.replace(replace_path, '')  # Remove leading path
                tar.extract(member, tmp_dir, filter='data')

        # Apply the INSTALLED_APPS patch
        with open(f'{tmp_dir}/diff.patch', 'w') as f:
            f.write(SETTINGS_PY_DIFF)
        os.system(f'patch {tmp_dir}/mysite/settings.py {tmp_dir}/diff.patch')

        yield tmp_dir


def test_standalone_app():
    url = "https://github.com/consideratecode/django-tutorial-step-by-step/archive/refs/tags/2.0/7.4.tar.gz"
    with download_and_extract_tar(url) as tmp_dir:
        django_squash = os.getcwd()
        with contextlib.chdir(tmp_dir):
            assert os.system('python -m venv venv') == 0
            assert os.system(f'venv/bin/pip install django {django_squash}') == 0
            assert os.system('venv/bin/python manage.py squash_migrations') == 0

            import ipdb; print('\a'); ipdb.sset_trace()
            a=a
