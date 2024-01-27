import collections.abc
import datetime
import decimal
import enum
import functools
import os
import pathlib
import types
import uuid

from django.conf import SettingsReference
from django.db import migrations as dj_migrations, models, models as dj_models
from django.db.migrations.operations.base import Operation
from django.db.migrations.serializer import (
    BaseSerializer, BaseSimpleSerializer, ChoicesSerializer, DatetimeDatetimeSerializer, DateTimeSerializer,
    DecimalSerializer, DeconstructableSerializer, DictionarySerializer, EnumSerializer, FloatSerializer,
    FrozensetSerializer, FunctionTypeSerializer as BaseFunctionTypeSerializer, FunctoolsPartialSerializer,
    IterableSerializer, ModelFieldSerializer, ModelManagerSerializer, OperationSerializer, PathLikeSerializer,
    PathSerializer, RegexSerializer, SequenceSerializer, SetSerializer, SettingsReferenceSerializer, TupleSerializer,
    TypeSerializer, UUIDSerializer,
)
from django.db.migrations.utils import COMPILED_REGEX_TYPE, RegexObject
from django.utils.functional import LazyObject, Promise
from django.utils.version import get_docs_version

from django_squash.db.migrations.operators import Variable

try:
    NoneType = types.NoneType
except AttributeError:
    NoneType = type(None)


class VariableSerializer(BaseSerializer):
    def serialize(self):
        return (self.value.name, '')


class FunctionTypeSerializer(BaseFunctionTypeSerializer):
    """
    This serializer is used to serialize functions that are in migrations.

    Knows that "migrations" is available in the global namespace, and sets the
    correct import statement for the functions that use it.
    """

    def serialize(self):
        response = super().serialize()

        if hasattr(self.value, '__in_migration_file__') and self.value.__in_migration_file__:
            return self.value.__qualname__, {}

        full_name = f'{self.value.__module__}.{self.value.__qualname__}'
        if full_name.startswith('django.') and '.models.' in full_name or '.migrations.' in full_name:
            collector = ''
            for part in self.value.__qualname__.split('.'):
                collector += part
                if hasattr(dj_migrations, collector):
                    return 'migrations.%s' % self.value.__qualname__, {'from django.db import migrations'}
                if hasattr(dj_models, collector):
                    return 'models.%s' % self.value.__qualname__, {'from django.db import models'}
                collector += '.'

        return response


class Serializer:
    _registry = {
        # Some of these are order-dependent.
        frozenset: FrozensetSerializer,
        list: SequenceSerializer,
        set: SetSerializer,
        tuple: TupleSerializer,
        dict: DictionarySerializer,
        models.Choices: ChoicesSerializer,
        enum.Enum: EnumSerializer,
        datetime.datetime: DatetimeDatetimeSerializer,
        (datetime.date, datetime.timedelta, datetime.time): DateTimeSerializer,
        SettingsReference: SettingsReferenceSerializer,
        float: FloatSerializer,
        (bool, int, NoneType, bytes, str, range): BaseSimpleSerializer,
        decimal.Decimal: DecimalSerializer,
        (functools.partial, functools.partialmethod): FunctoolsPartialSerializer,
        Variable: VariableSerializer,
        (
            types.FunctionType,
            types.BuiltinFunctionType,
            types.MethodType,
            functools._lru_cache_wrapper,
        ): FunctionTypeSerializer,
        collections.abc.Iterable: IterableSerializer,
        (COMPILED_REGEX_TYPE, RegexObject): RegexSerializer,
        uuid.UUID: UUIDSerializer,
        pathlib.PurePath: PathSerializer,
        os.PathLike: PathLikeSerializer,
    }

    @classmethod
    def register(cls, type_, serializer):
        if not issubclass(serializer, BaseSerializer):
            raise ValueError(
                "'%s' must inherit from 'BaseSerializer'." % serializer.__name__
            )
        cls._registry[type_] = serializer

    @classmethod
    def unregister(cls, type_):
        cls._registry.pop(type_)


def serializer_factory(value):
    if isinstance(value, Promise):
        value = str(value)
    elif isinstance(value, LazyObject):
        # The unwrapped value is returned as the first item of the arguments
        # tuple.
        value = value.__reduce__()[1][0]

    if isinstance(value, models.Field):
        return ModelFieldSerializer(value)
    if isinstance(value, models.manager.BaseManager):
        return ModelManagerSerializer(value)
    if isinstance(value, Operation):
        return OperationSerializer(value)
    if isinstance(value, type):
        return TypeSerializer(value)
    # Anything that knows how to deconstruct itself.
    if hasattr(value, "deconstruct"):
        return DeconstructableSerializer(value)
    for type_, serializer_cls in Serializer._registry.items():
        if isinstance(value, type_):
            return serializer_cls(value)
    raise ValueError(
        "Cannot serialize: %r\nThere are some values Django cannot serialize into "
        "migration files.\nFor more, see https://docs.djangoproject.com/en/%s/"
        "topics/migrations/#migration-serializing" % (value, get_docs_version())
    )
