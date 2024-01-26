from django.db.migrations.serializer import BaseSerializer


class VariableSerializer(BaseSerializer):
    def serialize(self):
        return (self.value.name, '')
