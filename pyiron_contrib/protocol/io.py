from __future__ import print_function
# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from collections import UserDict, UserList
from pyiron_contrib.protocol.lazy import Lazy
from abc import ABC, abstractmethod
from pyiron_contrib.protocol.utils.misc import LoggerMixin

"""
Containers for streamlining graph input and output
"""


__author__ = "Liam Huber, Dominik Gehringer"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "Feb 10, 2020"


class NotData:
    """A datatype to indicate that an input stack really doesn't have data (since `None` might be valid input!)"""
    pass


class IOStack(UserList, ABC, LoggerMixin):
    """An abstract class for handling stacks of lazy data."""

    def __init__(self, *args, **kwargs):
        super(IOStack, self).__init__(*args, **kwargs)

    @abstractmethod
    def push(self, item):
        self.data.append(item)

    def append(self, item):
        self.push(item)

    def __iadd__(self, other):
        self.push(other)

    def __setitem__(self, key, value):
        self.logger.warning("Items cannot be assigned to stacks. Use `push`.")


class InputStack(IOStack):
    """
    A list with an alternative initialization argument and a push method.
    """

    def __init__(self, initlist=None, default=None):
        if initlist is not None and default is not None:
            raise ValueError("init_list and default cannot both be provided")
        if default is not None:
            super(InputStack, self).__init__([default])
        else:
            super(InputStack, self).__init__(initlist)


class Input(dict):  #UserDict):  I'm having trouble with UserDict, .data, and recursion
    """
    Stores a collection of input stacks which can be resolved to get the top-most stack value which does not resolve to
    an instance of `NotData` or a (subset of) `OutputStack` containing any `NotData`.

    Raises a RuntimeError if it gets to the end of one of its stacks without finding valid data.

    Only allows items of the type `InputStack` to be set.

    Allows attribute-style setting and getting.
    """

    def __init__(self):
        super(Input, self).__init__()  # Don't allow state from initialization

    def resolve(self):
        resolved_dict = {}
        for k, v in self.items():
            resolved_dict[k] = self._resolve_input_stack(v)
        return resolved_dict

    def __invert__(self):
        """Warning: syntactic sugar does not work when chaining the resolution with other calls."""
        return self.resolve()

    @staticmethod
    def _resolve_input_stack(stack):
        for val in stack[::-1]:
            if isinstance(val, Lazy):
                val = ~val
            if isinstance(val, NotData):
                continue  # Catches when the final element of an OutputStack is passed but not data
            elif isinstance(val, (list, UserList)) and any(isinstance(item, NotData) for item in val):
                continue  # Catches when multiple elements of an OutputStack are passed but contain missing data
            else:
                return val
        raise RuntimeError("Input stack ran out without finding data.")

    def __setitem__(self, key, item):
        if not isinstance(item, InputStack):
            raise ValueError("Input only accepts objects of type InputStack as attributes.")
        super(Input, self).__setitem__(key, item)

    def __setattr__(self, key, item):
        self.__setitem__(key, item)

    def __getattr__(self, item):
        return super(Input, self).__getitem__(item)


class OutputStack(IOStack):
    """
    A list with fixed length which rotates out old values.
    """

    def __init__(self, buffer_length=1):
        super(OutputStack, self).__init__([NotData()] * buffer_length)
        self._buffer_length = None
        self.buffer_length = buffer_length

    @property
    def buffer_length(self):
        return self._buffer_length

    @buffer_length.setter
    def buffer_length(self, new_length):
        new_length = int(new_length)
        if new_length < 1:
            raise ValueError("Output stacks have a minimum length of 1, got {}".format(new_length))
        length_change = new_length - self._buffer_length
        self._buffer_length = new_length

        if length_change < 0:
            self.data = self.data[-length_change:]
        else:
            self.data = length_change*[NotData()] + self.data

    def push(self, item):
        super(OutputStack, self).push(item)
        self.data = self.data[1:]


class Output(dict):
    """
    A dictionary which ensures all its items are of the type `Lazy`.

    New fields can only be initialized as instances of `NotData` and then can be modified. There is some syntactic
    sugar that simply calling a non-existent entry initializes it, i.e. `output.new_field` *creates* the new attribute
    (initialized to `Lazy(NotData())`.
    """
    def __init__(self):
        super(Output, self).__init__()  # Don't allow state from initialization

    def resolve(self):
        """Resolve all lazy values and return them in a regular dictionary."""
        resolved_dict = {}
        for k, v in self.items():
            resolved_dict[k] = ~v
        return resolved_dict

    def __setitem__(self, key, item):
        raise AttributeError("Set items using `add_channel`.")

    def __setattr__(self, key, item):
        self.__setitem__(key, item)

    def add_channel(self, name, buffer_length=1):
        super(Output, self).__setitem__(name, OutputStack(buffer_length=buffer_length))

    def __getitem__(self, item):
        if item not in list(self.keys()):
            # Note: I'm really not sure I like this syntax. If we keep it, we could do something similar for Input...
            self.__setitem__(item, Lazy(NotData()))
        return super(Output, self).__getitem__(item)

    def __getattr__(self, item):
        return self.__getitem__(item)
