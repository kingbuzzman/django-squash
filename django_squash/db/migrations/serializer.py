import functools
import types

from django.db import migrations as dj_migrations, models as dj_models
from django.db.migrations.serializer import (
    BaseSerializer,
    FunctionTypeSerializer as BaseFunctionTypeSerializer,
    Serializer,
)

from django_squash.db.migrations.operators import Variable


class VariableSerializer(BaseSerializer):
    def serialize(self):
        return (self.value.name, "")


class FunctionTypeSerializer(BaseFunctionTypeSerializer):
    """
    This serializer is used to serialize functions that are in migrations.

    Knows that "migrations" is available in the global namespace, and sets the
    correct import statement for the functions that use it.
    """

    def serialize(self):
        response = super().serialize()

        if hasattr(self.value, "__in_migration_file__") and self.value.__in_migration_file__:
            return self.value.__qualname__, {}

        full_name = f"{self.value.__module__}.{self.value.__qualname__}"
        if full_name.startswith("django.") and ".models." in full_name or ".migrations." in full_name:
            atttr = self.value.__qualname__.split(".")[0]
            if hasattr(dj_migrations, atttr):
                return "migrations.%s" % self.value.__qualname__, {"from django.db import migrations"}
            if hasattr(dj_models, atttr):
                return "models.%s" % self.value.__qualname__, {"from django.db import models"}

        return response


def patch_serializer_registry(func):
    """
    Serializer registry patcher.

    This decorator is used to patch the serializer registry to remove serialziers we don't want, and add ones we do.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        original_registry = Serializer._registry
        Serializer._registry = {**original_registry}

        for key, value in list(Serializer._registry.items()):
            if value == BaseFunctionTypeSerializer:
                del Serializer._registry[key]

        Serializer._registry.update(
            {
                Variable: VariableSerializer,
                (
                    types.FunctionType,
                    types.BuiltinFunctionType,
                    types.MethodType,
                    functools._lru_cache_wrapper,
                ): FunctionTypeSerializer,
            }
        )

        try:
            return func(*args, **kwargs)
        finally:
            Serializer._registry = original_registry

    return wrapper
