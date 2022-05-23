from __future__ import print_function
# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import collections.abc
from logging import getLogger
from typing import Any, Tuple, Type

exclude_types = (str, bytes, dict, list, set, frozenset)

try:
    import numpy as np
except ImportError:
    pass
else:
    exclude_types += (np.ndarray, )

"""
Classes for handling protocols, particularly setting up input and output pipes.
"""

__author__ = "Dominik Gehringer, Liam Huber"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "18 July, 2019"


def ordered_dict_get_last(ordered_dict):
    """
    Gets the last most recently added object of an collections.OrderedDict instance

    Args:
        ordered_dict: (collections.OrderedDict) the dict to get the value from

    Returns: (object) the object at the back

    """

    return ordered_dict[next(reversed(ordered_dict))]


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


def fullname(obj):
    """
    Returns the fully qualified class name of an object

    Args:
        obj: (object) the object

    Returns: (str) the class name

    """
    obj_type = type(obj)
    return '{}.{}'.format(obj_type.__module__, obj_type.__name__)


# convenience function to ensure the passed argument is iterable
def ensure_iterable(o: Any, factory: Type = tuple, exclude: Tuple[Type, ...] = exclude_types):
    if isinstance(o, collections.abc.Iterable):
        return o if not isinstance(o, exclude) else factory((o,))
    else:
        return factory((o,))


class Registry(type):
    def __init__(cls, name, bases, nmspc):
        super(Registry, cls).__init__(name, bases, nmspc)
        if not hasattr(cls, 'registry'):
            cls.registry = set()
        cls.registry.add(cls)
        cls.registry -= set(bases)  # Remove base classes