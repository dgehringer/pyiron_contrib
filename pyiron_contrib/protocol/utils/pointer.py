# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import operator
import functools
from typing import Any, Callable, Optional, Tuple, Union
from pyiron_contrib.protocol.utils import ensure_iterable


"""
Python implementation of pointers using functional composition. Pointer can be resolved using ~ operator
"""

__author__ = "Dominik Gehringer, Liam Huber"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "May 21, 2022"


Transform = Callable[[Any], Any]
Predicate = Callable[[Any], bool]
Reduction = Callable[[Any, Any], Any]


def circ(f: Transform, g: Transform) -> Transform:
    return lambda x: f(g(x))


def compose(*functions: Transform, reduction: Reduction = circ) -> Transform:
    return functools.reduce(reduction, functions)


def identity(o: Any) -> Any:
    return o


def is_or_contains_pointer(item: Union[Any, Tuple[Any, ...]]) -> bool:
    return any(isinstance(el, Pointer) for el in ensure_iterable(item))


def possibly_deferred_pointer_execution(item: Union[Any, Tuple[Any, ...]], func) -> Transform:
    if is_or_contains_pointer(item):
        if isinstance(item, tuple):  # more than one arg
            return lambda o: func(*(~it if isinstance(it, Pointer) else it for it in item))(o)
        else:
            return lambda o: func(~item)(o)
    else:
        return func(item)


class Pointer:

    def __init__(self, args: Any, funcs: Optional[Tuple[Transform, ...]] = None, last_item: Optional[str] = None):
        self._args: Tuple[Any, ...] = ensure_iterable(args)
        self._funcs: Tuple[Transform, ...] = funcs or (identity,)
        self._callable: Transform = compose(*self._funcs)
        self._last_item: Optional[str] = last_item or None

    @property
    def funcs(self) -> Tuple[Transform, ...]:
        return self._funcs

    @property
    def args(self) -> Tuple[Any, ...]:
        return self._args

    def compose_pointer(self, f: Transform, last_item: Optional[str] = None):
        return Pointer(self._args, funcs=(f, *self._funcs), last_item=last_item)

    def __call__(self, *args, **kwargs):
        if is_or_contains_pointer(args) or is_or_contains_pointer(tuple(kwargs.values())):
            raise NotImplementedError('Pointers as function (keyword) arguments are not implemented')
        if self._last_item is not None:
            # instead of appending a function to the composition we modify the head from
            # operator.attrgetter(last_item) -> operator.methodcaller(last_item) using method shortcut
            _, *rest = self._funcs
            f = operator.methodcaller(self._last_item, *args, **kwargs)
            return Pointer(self._args, funcs=(f, *rest))
        else:
            # we have to assert that the last pointer crumb describes a method which we are going to call
            return self.compose_pointer(lambda fn: fn(*args, **kwargs))

    def __getattr__(self, item):
        return self.compose_pointer(
            possibly_deferred_pointer_execution(item, operator.attrgetter),
            last_item=item)

    def __getitem__(self, item):
        return self.compose_pointer(possibly_deferred_pointer_execution(item, operator.itemgetter))

    def resolve(self) -> Any:
        return self._callable(*self._args)

    def __invert__(self) -> Any:
        return self.resolve()


if __name__ == '__main__':
    import numpy as np

    a = np.arange(19) - 1.0j

    assert np.isclose(171.0, Pointer(a).conj().astype(float).sum().resolve())

    b = {
        1: lambda x: dict(x=x, y=x ** x),
        2: lambda x: x ** 2
    }

    index_pointer = Pointer(b)[1](3).get('y')
    assert ~index_pointer == 27

    c = np.arange(30**2).reshape(30, 30)

    assert np.allclose(~Pointer(c)[27, :],  c[~index_pointer, :])

    d = list(range(20, 50))
    print(~Pointer(d)[index_pointer])
    print(~Pointer(d).index(25))


