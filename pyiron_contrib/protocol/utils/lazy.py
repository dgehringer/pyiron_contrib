from __future__ import print_function
# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from collections import UserDict

"""
To wire graphs before evaluating them, we need a data type which is extremely lazy
"""

__author__ = "Liam Huber, Dominik Gehringer"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "Feb 10, 2020"


class Lazy:
    """
    A class which defers evaluation until its `.resolve` method is called, or it is prepended with a `~`.

    The goal is for all magic methods to work (except inversion, which is co-opted for value resolution), but they're
    not all written yet.
    """

    def __init__(self, default=None):
        self._val = default

    def __set__(self, instance, value):
        instance._val = value

    def resolve(self):
        return self._val

    def __invert__(self):
        return self.resolve()

    def __getattr__(self, item):
        return Lazy(getattr(self._val, item))

    def __call__(self, *args, **kwargs):
        return Lazy(self._val.__call__(*args, **kwargs))

    def __getitem__(self, item):
        return Lazy(self._val.__getitem__(item))

    def __add__(self, other):
        if isinstance(other, Lazy):
            return Lazy(self._val.__add__(other._val))
        else:
            return Lazy(self._val.__add__(other))


class PatientDict(UserDict):
    def __setattr__(self, key, value):
        self.__dict__[key] = value

    def resolve(self):
        resolved_dict = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Lazy):
                resolved_dict[k] = ~v
            else:
                resolved_dict[k] = v

    def __invert__(self):
        return self.resolve()

    def __getitem__(self, item):
        if isinstance(self.__dict__[item], Lazy):
            return ~self.__dict__[item]
        else:
            return self.__dict__[item]

    def __getattr__(self, item):
        self.__getitem__(item)
