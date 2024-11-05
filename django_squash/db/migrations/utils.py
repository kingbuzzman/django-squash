import ast
import functools
import hashlib
import importlib
import inspect
import itertools
import os
import re
import sysconfig
import types
from collections import defaultdict

from django.db import migrations
from django.utils.module_loading import import_string

from django_squash import settings as app_settings


@functools.lru_cache(maxsize=1)
def get_custom_rename_function():
    """
    Custom function naming when copying elidable functions from one file to another.
    """
    custom_rename_function = app_settings.DJANGO_SQUASH_CUSTOM_RENAME_FUNCTION

    if custom_rename_function:
        return import_string(custom_rename_function)


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
    """
    Return the absolute path of a module
    """
    return os.path.dirname(os.path.abspath(inspect.getsourcefile(module)))


class UniqueVariableName:
    """
    This class will return a unique name for a variable / function.
    """

    def __init__(self, context, naming_function=None):
        self.names = defaultdict(int)
        self.functions = {}
        self.context = context
        self.naming_function = naming_function or (lambda n, c: n)

    def update_context(self, context):
        self.context.update(context)

    def function(self, func):
        if not callable(func):
            raise ValueError("func must be a callable")

        if isinstance(func, types.FunctionType) and func.__name__ == "<lambda>":
            raise ValueError("func cannot be a lambda")

        if inspect.ismethod(func) or inspect.signature(func).parameters.get("self") is not None:
            raise ValueError("func cannot be part of an instance")

        name = func.__qualname__
        if "." in name:
            parent_name, actual_name = name.rsplit(".", 1)
            parent = getattr(import_string(func.__module__), parent_name)
            if issubclass(parent, migrations.Migration):
                name = actual_name

        if func in self.functions:
            return self.functions[func]

        name = self.naming_function(name, {**self.context, "type_": "function", "func": func})
        new_name = self.functions[func] = self.uniq(name)

        return new_name

    def uniq(self, name, original_name=None):
        original_name = original_name or name
        # Endless loop that will try different combinations until it finds a unique name
        for i, _ in enumerate(itertools.count(), 2):
            if self.names[name] == 0:
                self.names[name] += 1
                break

            name = "%s_%s" % (original_name, i)
        return name

    def __call__(self, name, force_number=False):
        original_name = name
        if force_number:
            name = f"{name}_1"
        return self.uniq(name, original_name)


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


def normalize_function_name(name):
    _, _, function_name = name.rpartition(".")
    if function_name[0].isdigit():
        # Functions CANNOT start with a number
        function_name = "f_" + function_name
    return function_name


def copy_func(f, name):
    """
    Return a function with same code, globals, defaults, closure, and name (or provide a new name)
    """
    func = types.FunctionType(f.__code__, f.__globals__, name, f.__defaults__, f.__closure__)
    func.__qualname__ = name
    func.__original__ = f
    func.__source__ = re.sub(
        pattern=rf"(def\s+){normalize_function_name(f.__qualname__)}",
        repl=rf"\1{name}",
        string=inspect.getsource(f),
        count=1,
    )
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
    site_packages_path_ = site_packages_path()
    try:
        loader = importlib.util.find_spec(module_name)
    except ImportError:
        return False
    return loader.origin.startswith(site_packages_path_)


@functools.lru_cache(maxsize=1)
def site_packages_path():
    # returns the "../site-packages" directory
    return sysconfig.get_path("purelib")


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
    output = []
    for lineno, line in enumerate(source.splitlines()):
        if lineno + 1 in comment_out_nodes.keys():
            output.append(" " * comment_out_nodes[lineno + 1][0] + attr + " = " + str(value))
            p_count = 0
            b_count = 0
            p_count, b_count = find_brackets(line, p_count, b_count)
        elif p_count != 0 or b_count != 0:
            p_count, b_count = find_brackets(line, p_count, b_count)
        else:
            output.append(line)

    # Overwrite the existing migration file to update it.
    return "\n".join(output) + "\n"
