import importlib
import importlib.util
import inspect
import sys
from pathlib import Path

import black
import libcst

try:
    import tomllib

    with open("pyproject.toml", "r") as f:  # pragma: no cover
        if "Programming Language :: Python :: 3.10" not in f.read():
            raise Exception("Delete this try/except block and leave the just the 'import tomllib'.")
except ImportError:
    # Python 3.10 does not support tomllib
    import tomli as tomllib

import warnings

from django import VERSION as _DJANGO_FULL_VERSION
from packaging.version import Version


def is_pyvsupported(version):
    """
    Check if the Python version is supported by the package.
    """
    return Version(version) in SUPPORTED_PYTHON_VERSIONS


def is_djvsupported(version):
    """
    Check if the Django version is supported by the package.
    """
    return Version(version) in SUPPORTED_DJANGO_VERSIONS


def is_number(s):
    """Returns True if string is a number."""
    try:
        float(s)
        return True
    except ValueError:
        return False


def shorten_version(version):
    parts = version.split(".")
    return ".".join(parts[:2])


def is_supported_version(supported_versions, version_to_check):
    if version_to_check.is_prerelease:
        return True

    for base_version in supported_versions:
        if version_to_check.major == base_version.major and version_to_check.minor == base_version.minor:
            return True

    return False


SUPPORTED_PYTHON_VERSIONS = []
SUPPORTED_DJANGO_VERSIONS = []

with open(Path().resolve() / "pyproject.toml", "rb") as f:
    conf = tomllib.load(f)
for classifier in conf["project"]["classifiers"]:
    if "Framework :: Django ::" in classifier:
        version = classifier.split("::")[-1].strip()
        if is_number(version):
            SUPPORTED_DJANGO_VERSIONS.append(Version(version))
            globals()["DJ" + version.replace(".", "")] = False
    elif "Programming Language :: Python ::" in classifier:
        version = classifier.split("::")[-1].strip()
        if is_number(version) and "." in version:
            SUPPORTED_PYTHON_VERSIONS.append(Version(version))
            globals()["PY" + version.replace(".", "")] = False

current_python_version = Version(f"{sys.version_info.major}.{sys.version_info.minor}")
pre_release_map = {"alpha": "a", "beta": "b", "rc": "rc"}
# Extract the components of the tuple
major, minor, micro, pre_release, pre_release_num = _DJANGO_FULL_VERSION
# Get the corresponding identifier
pre_release_identifier = pre_release_map.get(pre_release, "")
# Construct the version string
_DJANGO_VERSION = f"{major}.{minor}.{micro}{pre_release_identifier}.{pre_release_num}"
current_django_version = Version(_DJANGO_VERSION)

globals()["DJ" + shorten_version(str(current_django_version).replace(".", ""))] = True
globals()["PY" + shorten_version(str(current_python_version).replace(".", ""))] = True

if not is_supported_version(SUPPORTED_DJANGO_VERSIONS, current_django_version):
    versions = ", ".join([str(v) for v in SUPPORTED_DJANGO_VERSIONS])
    warnings.warn(f"Current Django version {current_django_version} is not in" f" the supported versions: {versions}")

if not is_supported_version(SUPPORTED_PYTHON_VERSIONS, current_python_version):
    versions = ", ".join([str(v) for v in SUPPORTED_PYTHON_VERSIONS])
    warnings.warn(f"Current Python version {current_python_version} is not in" f" the supported versions: {versions}")


def load_migration_module(path):
    spec = importlib.util.spec_from_file_location("__module__", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        with open(path) as f:
            lines = f.readlines()
            formatted_lines = "".join(f"{i}: {line}" for i, line in enumerate(lines, start=1))
            raise type(e)(f"{e}.\nError loading module file containing:\n\n{formatted_lines}") from e
    return module


def pretty_extract_piece(module, traverse):
    """Format the code extracted from the module, so it can be compared to the expected output"""
    return format_code(extract_piece(module, traverse))


def extract_piece(module, traverse):
    """Extract a piece of code from a module"""
    source_code = inspect.getsource(module)
    tree = libcst.parse_module(source_code).body

    for looking_for in traverse.split("."):
        if looking_for:
            tree = traverse_node(tree, looking_for)

    if not isinstance(tree, tuple):
        tree = (tree,)
    return libcst.Module(body=tree).code


def format_code(code_string):
    """Format the code so it's reproducible"""
    mode = black.FileMode(line_length=10_000)
    return black.format_str(code_string, mode=mode)


def traverse_node(nodes, looking_for):
    """Traverse the tree looking for a node"""
    if not isinstance(nodes, (list, tuple)):
        nodes = [nodes]

    for node in nodes:
        if isinstance(node, (libcst.ClassDef, libcst.FunctionDef)) and node.name.value == looking_for:
            return node
        if isinstance(node, libcst.Assign) and looking_for in [n.target.value for n in node.targets]:
            return node

        for child in node.children:
            result = traverse_node(child, looking_for)
            if result:
                return result
