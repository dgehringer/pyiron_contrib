# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function
from collections import UserDict
from numpy.linalg import norm as nplanorm

"""
To wire graphs before evaluating them, we will need a data type which is extremely lazy.
"""

__author__ = "Liam Huber, Dominik Gehringer"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "Feb 10, 2020"


class _LinalgSpoof:
    """
    A dummy class for lazy variables to access the `numpy.linalg.norm` method.
    """

    @staticmethod
    def norm(x, ord=2, axis=None, keepdims=False):
        if isinstance(x, NotData):
            return x
        else:
            return nplanorm(x, ord=ord, axis=axis, keepdims=keepdims)


def _lazy_magic(magic_name, cls, expiring=False):
    """
    A replacement to magic methods for lazy variables by way of returning another lazy variable.

    Args:
        magic_name (str): The name of the python magic method being replaced.
        cls (Lazy): The class to decorate. It had better be `Lazy`.
        expiring (bool): Whether the recursing call should delete itself after being used. This should be true when
            the call is to an in-place modifying method, i.e. those which begin with 'i'.

    Returns:
        (fnc): A function returning a new instance of `cls` using the calling instance as its `value`, the new
            `magic_name` named method as its function call, set to expire based on `expiring`.
    """
    def fn(self, *args, **kwargs):
        return cls(value=self, call=(magic_name, args, kwargs), expiring_call=expiring)
    return fn


def _lazy_base_magic(magic_name, cls):
    return _lazy_magic(magic_name, cls, expiring=False)


def _lazy_augmenting_magic(magic_name, cls):
    return _lazy_magic(magic_name, cls, expiring=True)


def _not_data_magic(magic_name, cls):
    """
    A replacement for magic methods for the `NotData` class.

    Args:
        magic_name (str): The name of the python magic method being replaced.
        cls (Lazy): The class to decorate. It had better be `Lazy`.

    Returns:
        (fnc): A new function which just returns self.
    """

    def fn(self, *args, **kwargs):
        return self
    return fn


_base_names = [
    '__getitem__',
    '__pos__', '__neg__', '__abs__', '__round__', '__floor__', '__ceil__', '__trunc__',
    '__eq__', '__ne__', '__lt__', '__gt__', '__le__', '__ge__',
    '__add__', '__sub__', '__mul__', '__floordiv__', '__truediv__', '__mod__', '__divmod__', '__pow__',
    '__lshift__', '__rshift__', '__and__', '__or__', '__xor__',
    '__radd__', '__rsub__', '__rmul__', '__rfloordiv__', '__rtruediv__', '__rmod__', '__rdivmod__', '__rpow__',
    '__rlshift__', '__rrshift__', '__rand__', '__ror__', '__rxor__',
    '__call__'
]
_augmenting_names = [
    '__iadd__', '__isub__', '__imul__', '__ifloordiv__', '__itruediv__', '__imod__', '__idivmod__', '__ipow__',
    '__ilshift__', '__irshift__', '__iand__', '__ior__', '__ixor__',
]


def _override_methods(replacement, names):
    """
    A decorator to override class methods with the provided replacement function.

    Args:
        replacement (fnc): The function with which to replace the methods in `base_names`.
        names (list): The names of methods to be replaced by `replacement`.

    Returns:
        (cls): A new instance of the class with the magic methods overwritten.
    """

    def decorate(cls):
        """

        Args:
            cls (Lazy): The class to decorate. Had better be `Lazy`.

        Returns:
            (cls): The class with a bunch of new magic methods.
        """
        for name in names:
            setattr(cls, name, replacement(name, cls))

        return cls
    return decorate


@_override_methods(_lazy_base_magic, _base_names)
@_override_methods(_lazy_augmenting_magic, _augmenting_names)
class Lazy:
    """
    A class which defers evaluation until its `.resolve` method is called, or it is prepended with a `~`.

    The goal is for all magic methods to work (except inversion, which is co-opted for value resolution), but they're
    not all written yet.

    Attributes:
        value (anything): The underlying value dug up on resolution.

    Examples:
        We can define complex objects and reference them before they sensibly exist:

        >>> foo = Lazy()
        >>> bar = Lazy()
        >>> baz = foo[:3].shape[0] + bar.flatten().shape[0]
        >>> print(baz)
        [path].Lazy object at [memory address]
        >>> foo.value = np.arange(5)
        >>> bar.value = np.eye(3)
        >>> print(baz)
        [path].Lazy object at [memory address]
        >>> print(~baz)  # 3 + 9 = 12
        12
    """

    def __init__(self, value=None, call=None, expiring_call=False):
        """
        Initialize a new lazy variable.

        Args:
            value (anything): The value returned on resolution. (Default is None.)
            call ((fnc, args, kwargs)): The function to call on resolution, if any. (Default is None.)
            expiring_call (bool): Whether the call should expire after the first resolution, such that future
                resolutions directly return the stored value. Useful when the call works in-place. (Default is False.)
        """
        self.value = value
        self._call = call
        self._expiring_call = expiring_call

    def resolve(self):
        if self._call is None:
            if isinstance(self.value, Lazy):
                return self.value.resolve()
            else:
                return self.value
        else:
            atr, args, kwargs = self._call
            if self._expiring_call:
                self._call = None

            args = self._resolve_args(args)
            kwargs = self._resolve_kwargs(kwargs)
            if isinstance(self.value, Lazy):
                res_val = self.value.resolve()
                return getattr(res_val, atr)(*args, **kwargs)
            else:
                return getattr(self.value, atr)(*args, **kwargs)

    @staticmethod
    def _resolve_args(args):
        """Ensure there are no Lazy variables in args"""
        new_args = []
        for arg in args:
            if isinstance(arg, Lazy):
                new_args.append(arg.resolve())
            else:
                new_args.append(arg)
        return tuple(new_args)

    @staticmethod
    def _resolve_kwargs(kwargs):
        """Ensure there are no Lazy variables in kwargs"""
        new_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, Lazy):
                new_kwargs[k] = v.resolve()
            else:
                new_kwargs[k] = v
        return new_kwargs

    def __invert__(self):
        """Syntactic sugar, but hopefully you don't really want to invert..."""
        return self.resolve()

    def __getattr__(self, item):
        if item == '_ipython_canary_method_should_not_exist_':  # For using in jupyter notebooks
            return self.value
        return Lazy(value=self, call=('__getattribute__', (item,), {}))

    def __str__(self):
        return "{}({})".format(self.__class__.__name__, self.value.__str__())

    def norm(self, ord=2, axis=None, keepdims=False):
        """
        Lazily apply Numpy's linalg norm.

        Docstrings directly copied from the `numpy docs`_.

        _`numpy docs`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.linalg.norm.html

        Args:
            ord (non-zero int/inf/-inf/'fro'/'nuc'): Order of the norm. inf means numpy’s inf object. (Default is 2).
            axis (int/2-tuple of ints/None): If axis is an integer, it specifies the axis of x along which to compute
                the vector norms. If axis is a 2-tuple, it specifies the axes that hold 2-D matrices, and the matrix
                norms of these matrices are computed. If axis is None then either a vector norm (when x is 1-D) or a
                matrix norm (when x is 2-D) is returned. (Default is None.)
            keepdims (bool): If this is set to True, the axes which are normed over are left in the result as dimensions
                with size one. With this option the result will broadcast correctly against the original x. (Default is
                False)

        returns:
            (float/numpy.ndarray): Norm of the matrix or vector(s).
        """
        return Lazy(value=Lazy(_LinalgSpoof), call=('norm', (self,), {'ord': ord, 'axis': axis, 'keepdims': keepdims}))


class PatientDict(UserDict):
    def __setattr__(self, key, value):
        self.__dict__[key] = value

    def resolve(self):
        resolved_dict = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Lazy):
                resolved_dict[k] = v.resolve()
            else:
                resolved_dict[k] = v

    def __invert__(self):
        return self.resolve()

    def __getitem__(self, item):
        if isinstance(self.__dict__[item], Lazy):
            return self.__dict__[item].resolve()
        else:
            return self.__dict__[item]

    def __getattr__(self, item):
        self.__getitem__(item)


@_override_methods(_not_data_magic, _base_names)
@_override_methods(_not_data_magic, _augmenting_names)
class NotData(object):
    """A datatype to indicate that an input stack really doesn't have data (since `None` might be valid input!)"""

    def __repr__(self):
        return "<NotData>"

    def __str__(self):
        return "notdata"

    def __getattribute__(self, item):
        try:
            return super(NotData, self).__getattribute__(item)
        except AttributeError:
            return self

    def __getattr__(self, item):
        return self
