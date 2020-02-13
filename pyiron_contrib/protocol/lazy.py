from __future__ import print_function
# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from collections import UserDict

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


def _set_lazy_magic():
    """
    A decorator to give the `Lazy` class all manner of lazy magic methods. These methods return a new instance of the
    class with the calling instance set as the value and the magic method as the call. The call might be expiring if it
    is one of the 'augmenting' magic methods that begin with 'i'. This is to stop the call from being re-applied every
    time we resolve the lazy variable, but rather only the first time.

    Note: Inversion is *not* overwritten, since this is used as syntactic sugar for resolving the lazy variable.

    # TODO: More careful parsing so += will work on immutables.

    Returns:
        (fnc): The decorating function.
    """
    base_names = [
        '__getitem__',
        '__pos__', '__neg__', '__abs__', '__round__', '__floor__', '__ceil__', '__trunc__',
        '__eq__', '__ne__', '__lt__', '__gt__', '__le__', '__ge__',
        '__add__', '__sub__', '__mul__', '__floordiv__', '__truediv__', '__mod__', '__divmod__', '__pow__',
        '__lshift__', '__rshift__', '__and__', '__or__', '__xor__',
        '__radd__', '__rsub__', '__rmul__', '__rfloordiv__', '__rtruediv__', '__rmod__', '__rdivmod__', '__rpow__',
        '__rlshift__', '__rrshift__', '__rand__', '__ror__', '__rxor__',
        '__call__'
    ]
    augmenting_names = [
        '__iadd__', '__isub__', '__imul__', '__ifloordiv__', '__itruediv__', '__imod__', '__idivmod__', '__ipow__',
        '__ilshift__', '__irshift__', '__iand__', '__ior__', '__ixor__',
    ]

    def lazy_magic(magic_name, cls, expiring=False):
        """

        Args:
            magic_name (str):
            cls (Lazy): The class to decorate. It had better be `Lazy`.
            expiring (bool): Whether the recursing call should delete itself after being used. This should be true when
                the call is to an in-place modifying method, i.e. those which begin with 'i'.

        Returns:
            (cls): A new instance of the class with the calling instance as its `value`, the new `magic_name` named
                method as its function call, set to expire based on `expiring`.
        """
        def fn(self, *args, **kwargs):
            return cls(value=self, call=(magic_name, args, kwargs), expiring_call=expiring)
        return fn

    def decorate(cls):
        """

        Args:
            cls (Lazy): The class to decorate. Had better be `Lazy`.

        Returns:
            (cls): The class with a bunch of new magic methods.
        """
        for name in base_names:
            setattr(cls, name, lazy_magic(name, cls))

        for name in augmenting_names:
            setattr(cls, name, lazy_magic(name, cls, expiring=True))

        return cls
    return decorate


@_set_lazy_magic()
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
                return ~self.value
            else:
                return self.value
        else:
            atr, args, kwargs = self._call
            if self._expiring_call:
                self._call = None

            args = self._resolve_args(args)
            kwargs = self._resolve_kwargs(kwargs)
            if isinstance(self.value, Lazy):
                return getattr(~self.value, atr)(*args, **kwargs)
            else:
                return getattr(self.value, atr)(*args, **kwargs)

    @staticmethod
    def _resolve_args(args):
        """Ensure there are no Lazy variables in args"""
        new_args = []
        for arg in args:
            if isinstance(arg, Lazy):
                new_args.append(~arg)
            else:
                new_args.append(arg)
        return tuple(new_args)

    @staticmethod
    def _resolve_kwargs(kwargs):
        """Ensure there are no Lazy variables in kwargs"""
        new_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, Lazy):
                new_kwargs[k] = ~v
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
