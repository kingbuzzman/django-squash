from django.db.migrations import RunPython as RunPythonBase, RunSQL as RunSQLBase


class Variable:
    """
    Wrapper type to be able to format the variable name correctly inside a migration
    """
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __bool__(self):
        return bool(self.value)


class RunPython(RunPythonBase):
    # Fake the class so the OperationWriter thinks its the internal class and not a custom one
    __class__ = RunPythonBase

    def deconstruct(self):
        name, args, kwargs = super().deconstruct()
        kwargs['elidable'] = self.elidable
        return name, args, kwargs

    @classmethod
    def from_operation(cls, operation):
        return cls(code=operation.code, reverse_code=operation.reverse_code, atomic=operation.atomic,
                   hints=operation.hints, elidable=operation.elidable)


class RunSQL(RunSQLBase):
    # Fake the class so the OperationWriter thinks its the internal class and not a custom one
    __class__ = RunSQLBase

    def deconstruct(self):
        name, args, kwargs = super().deconstruct()
        kwargs['elidable'] = self.elidable
        return name, args, kwargs

    @classmethod
    def from_operation(cls, operation, num):
        reverse_sql = Variable('SQL_%s_ROLLBACK' % num, operation.reverse_sql) if operation.reverse_sql else None

        return cls(sql=Variable('SQL_%s' % num, operation.sql), reverse_sql=reverse_sql,
                   state_operations=operation.state_operations, hints=operation.hints,
                   elidable=operation.elidable)
