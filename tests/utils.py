import importlib
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("dj_squash_setup", Path().resolve() / "setup.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def is_pyvsuported(version):
    """
    Check if the Python version is supported by the package.
    """
    return version in module.PYTHON_VERSIONS


def is_djvsuported(version):
    """
    Check if the Django version is supported by the package.
    """
    return version in module.DJANGO_VERSIONS
