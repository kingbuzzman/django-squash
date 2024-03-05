class Variable:
    """
    Wrapper type to be able to format the variable name correctly inside a migration
    """

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __bool__(self):
        return bool(self.value)
