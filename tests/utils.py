import importlib
import importlib.util
import inspect
import sys
from pathlib import Path

import black
import libcst

spec = importlib.util.spec_from_file_location("dj_squash_setup", Path().resolve() / "setup.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def is_pyvsupported(version):
    """
    Check if the Python version is supported by the package.
    """
    return version in module.PYTHON_VERSIONS


def is_djvsupported(version):
    """
    Check if the Django version is supported by the package.
    """
    return version in module.DJANGO_VERSIONS


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
