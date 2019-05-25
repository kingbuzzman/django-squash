from django.db.migrations import RunPython as RunPythonBase, RunSQL as RunSQLBase


class RunPython(RunPythonBase):

    def deconstruct(self):
        name, args, kwargs = super().deconstruct()
        kwargs['elidable'] = self.elidable
        return name, args, kwargs

    @classmethod
    def from_operation(cls, operation):
        return cls(code=operation.code, reverse_code=operation.reverse_code, atomic=operation.atomic,
                   hints=operation.hints, elidable=operation.elidable)


class RunSQL(RunSQLBase):

    def deconstruct(self):
        name, args, kwargs = super().deconstruct()
        kwargs['elidable'] = self.elidable
        return name, args, kwargs

    @classmethod
    def from_operation(cls, operation):
        return cls(sql=operation.sql, reverse_sql=operation.reverse_sql, state_operations=operation.state_operations,
                   hints=operation.hints, elidable=operation.elidable)
