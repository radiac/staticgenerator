"""
Exeptions for staticgenerator
"""
class StaticGeneratorException(Exception):
    def __init__(self, message, **kwargs):
        super(StaticGeneratorException, self).__init__(message)
        self.__dict__.update(kwargs)

