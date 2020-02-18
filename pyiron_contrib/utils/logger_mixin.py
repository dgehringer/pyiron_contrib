from logging import getLogger


class LoggerMixin(object):
    """
    A class which is meant to be inherited from. Provides a logger attribute. The loggers name is the fully
    qualified type name of the instance
    """

    def fullname(self):
        """
        Returns the fully qualified type name of the instance

        Returns:
            str: fully qualified type name of the instance
        """
        return '{}.{}'.format(self.__class__.__module__, self.__class__.__name__)

    @property
    def logger(self):
        return getLogger(self.fullname())