import ast
import hashlib
import importlib
import inspect
import itertools
import os
import sysconfig
import types
from collections import defaultdict


def file_hash(file_path):
    """
    Calculate the hash of a file
    """
    BLOCK_SIZE = 65536

    file_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        fb = f.read(BLOCK_SIZE)
        while len(fb) > 0:
            file_hash.update(fb)
            fb = f.read(BLOCK_SIZE)

    return file_hash.hexdigest()


def source_directory(module):
    return os.path.dirname(os.path.abspath(inspect.getsourcefile(module)))


class UniqueVariableName:
    """
    This class will return a unique name for a variable / function.
    """

    def __init__(self):
        self.names = defaultdict(int)
        self.functions = {}

    def function(self, func):
        if not callable(func):
            raise ValueError("func must be a callable")

        if isinstance(func, types.FunctionType) and func.__name__ == "<lambda>":
            raise ValueError("func cannot be a lambda")

        if inspect.ismethod(func) or inspect.signature(func).parameters.get("self") is not None:
            raise ValueError("func cannot be part of an instance")

        name = original_name = func.__qualname__
        already_accounted = func in self.functions
        if already_accounted:
            return self.functions[func]

        # Endless loop that will try different combinations until it finds a unique name
        for i, _ in enumerate(itertools.count(), 2):
            if self.names[name] == 0:
                self.functions[func] = name
                self.names[name] += 1
                break

            name = "%s_%s" % (original_name, i)

        self.functions[func] = name

        return name

    def __call__(self, name, force_number=False):
        self.names[name] += 1
        count = self.names[name]
        if not force_number and count == 1:
            return name
        else:
            new_name = "%s_%s" % (name, count)
            # Make sure that the function name is fully unique
            # You can potentially have the same name already defined.
            return self(new_name)


def get_imports(module):
    """
    Return an generator with all the imports to a particular py file as string
    """
    source = inspect.getsource(module)
    path = inspect.getsourcefile(module)

    root = ast.parse(source, path)
    for node in ast.iter_child_nodes(root):
        if isinstance(node, ast.Import):
            for n in node.names:
                yield f"import {n.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module.split(".")
            # Remove old python 2.x imports
            if "__future__" not in node.module:
                yield f"from {node.module} import {', '.join([x.name for x in node.names])}"
        else:
            continue


def copy_func(f, name=None):
    """
    Return a function with same code, globals, defaults, closure, and name (or provide a new name)
    """
    name = name or f.__qualname__
    func = types.FunctionType(f.__code__, f.__globals__, name, f.__defaults__, f.__closure__)
    func.__qualname__ = f.__qualname__
    func.__original_qualname__ = f.__original_qualname__
    func.__original_module__ = f.__module__
    return func


def find_brackets(line, p_count, b_count):
    for char in line:
        if char == "(":
            p_count += 1
        elif char == ")":
            p_count -= 1
        elif char == "[":
            b_count += 1
        elif char == "]":
            b_count -= 1
    return p_count, b_count


def is_code_in_site_packages(module_name):
    # Find the module in the site-packages directory
    site_packages_path = sysconfig.get_path("purelib")  # returns the "../site-packages" directory
    try:
        loader = importlib.util.find_spec(module_name)
        return site_packages_path in loader.origin
    except ImportError:
        return False


def replace_migration_attribute(source, attr, value):
    tree = ast.parse(source)
    # Skip this file if it is not a migration.
    migration_node = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Migration":
            migration_node = node
            break
    else:
        return

    # Find the `attr` variable.
    comment_out_nodes = {}
    for node in migration_node.body:
        if isinstance(node, ast.Assign) and node.targets[0].id == attr:
            comment_out_nodes[node.lineno] = (
                node.targets[0].col_offset,
                node.targets[0].id,
            )

    # Skip this migration if it does not contain the `attr` we're looking for
    if not comment_out_nodes:
        return

    # Remove the lines that form the multi-line "replaces" statement.
    p_count = 0
    b_count = 0
    col_offset = None
    name = None
    output = []
    for lineno, line in enumerate(source.splitlines()):
        if lineno + 1 in comment_out_nodes.keys():
            output.append(" " * comment_out_nodes[lineno + 1][0] + attr + " = " + str(value))
            p_count = 0
            b_count = 0
            col_offset, name = comment_out_nodes[lineno + 1]
            p_count, b_count = find_brackets(line, p_count, b_count)
        elif p_count != 0 or b_count != 0:
            p_count, b_count = find_brackets(line, p_count, b_count)
        else:
            output.append(line)

    # Overwrite the existing migration file to update it.
    return "\n".join(output) + "\n"


def dev_mode():
    """Return True if the code is running in development mode"""
    return not is_code_in_site_packages("django_squash")
