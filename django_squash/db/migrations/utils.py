import ast
import inspect
import itertools
import os
import types
from collections import defaultdict

from django.db import migrations as migration_module

from .operators import RunPython, RunSQL


def source_directory(module):
    return os.path.dirname(os.path.abspath(inspect.getsourcefile(module)))


class UniqueVariableName:
    def __init__(self):
        self.names = defaultdict(int)
        self.functions = {}

    def function(self, func):
        if not callable(func):
            raise ValueError('func must be a callable')

        if isinstance(func, types.FunctionType) and func.__name__ == '<lambda>':
            raise ValueError('func cannot be a lambda')

        if inspect.ismethod(func) or inspect.signature(func).parameters.get('self') is not None:
            raise ValueError('func cannot be part of an instance')

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

            name = '%s_%s' % (original_name, i)

        self.functions[func] = name

        return name

    def __call__(self, name, force_number=False):
        self.names[name] += 1
        count = self.names[name]
        if not force_number and count == 1:
            return name
        else:
            new_name = '%s_%s' % (name, count)
            # Make sure that the function name is fully unique
            # You can potentially have the same name already defined.
            return self(new_name)


def all_custom_operations(operations, unique_names):
    """
    Generator that loops over all the operations and traverses sub-operations such as those inside a -
    SeparateDatabaseAndState class.
    """

    for operation in operations:
        if operation.elidable:
            continue

        if isinstance(operation, migration_module.RunSQL):
            yield RunSQL.from_operation(operation, unique_names)
        elif isinstance(operation, migration_module.RunPython):
            yield RunPython.from_operation(operation, unique_names)
        elif isinstance(operation, migration_module.SeparateDatabaseAndState):
            # A valid use case for this should be given before any work is done.
            pass


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
                yield f'import {n.name}'
        elif isinstance(node, ast.ImportFrom):
            module = node.module.split('.')
            # Remove old python 2.x imports
            if '__future__' not in node.module:
                yield f"from {node.module} import {', '.join([x.name for x in node.names])}"
        else:
            continue


def copy_func(f, name=None):
    func = types.FunctionType(f.__code__, f.__globals__, name or f.__qualname__,
                              f.__defaults__, f.__closure__)
    func.__qualname__ = f.__qualname__
    func.__original_qualname__ = f.__original_qualname__
    return func

