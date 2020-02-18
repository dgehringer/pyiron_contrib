# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function
from collections import UserList
from pyiron_contrib.protocol.lazy import Lazy, NotData
from abc import ABC
from pyiron_contrib.utils.logger_mixin import LoggerMixin

"""
Containers for streamlining graph input and output.

The intent is that input channels should be set up with a list of regular variables, or fed from an output channel.
When they try to resolve themselves, they start pulling off their stack until they find valid data. Output, meanwhile, 
has channels of some fixed length (so pushing new values gets rid of the old ones) and is guaranteed to be lazy.
"""


__author__ = "Liam Huber, Dominik Gehringer"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "Feb 10, 2020"


class IOChannel(Lazy, ABC, LoggerMixin):
    """An abstract class for handling stacks of lazy data."""

    def __init__(self, *args, **kwargs):
        super(IOChannel, self).__init__(*args, **kwargs)

    def push(self, item):
        self.value.append(item)

    def append(self, item):
        self.push(item)

    def __iadd__(self, other):
        self.push(other)
        return self

    def __setitem__(self, key, value):
        self.logger.warning("Items cannot be assigned to stacks. Use `push`.")

    # def __str__(self):
    #     return "{}({})".format(self.__class__.__name__, self.data.__str__())

    def __len__(self):
        return len(self.value)


class InputChannel(IOChannel):
    """A list with an alternative initialization argument and a push method."""

    def __init__(self, default=None):
        if default is not None:
            super(InputChannel, self).__init__(value=[default])
        else:
            super(InputChannel, self).__init__(value=[])

    def resolve(self):
        for val in self.value[::-1]:
            if isinstance(val, Lazy):
                val = val.resolve()
            if isinstance(val, (NotData, type(NotImplemented))):
                # TODO: Add tests for the NotImplemented case, and probably a logger warning too
                continue  # Catches when the final element of an OutputStack is passed but not data
            elif isinstance(val, (list, UserList)) and \
                    any(isinstance(item, (NotData, type(NotImplemented))) for item in val):
                continue  # Catches when multiple elements of an OutputStack are passed but contain missing data
            else:
                return val
        raise RuntimeError("Input stack ran out without finding data.")

    def clear(self):
        self.value = []


class OutputChannel(IOChannel):
    """
    A list with fixed length which rotates out old values.

    Attributes:
        buffer_length (int): The length of the channel. (Default is 1, pushing a new value removes the existing one.)
    """

    def __init__(self, buffer_length=1):
        super(OutputChannel, self).__init__(value=[])
        self._buffer_length = 0
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
            self.value = self.value[-length_change:]
        else:
            self.value = length_change * [NotData()] + self.value

    def push(self, item):
        super(OutputChannel, self).push(item)
        self.value = self.value[1:]


class IO(dict, ABC):

    def __init__(self):
        super(IO, self).__init__()  # Don't allow state from initialization

    def resolve(self):
        """Resolve all lazy values and return them in a regular dictionary."""
        resolved_dict = {}
        for k, v in self.items():
            resolved_dict[k] = v.resolve()
        return resolved_dict

    def __invert__(self):
        """Warning: syntactic sugar does not work when chaining the resolution with other calls."""
        return self.resolve()

    def __setattr__(self, key, item):
        self.__setitem__(key, item)

    def __getattr__(self, item):
        return super(IO, self).__getitem__(item)

    def __str__(self):
        rep = "{} with channel(s):\n".format(self.__class__.__name__)
        for k, v in self.items():
            rep += "\t{}: {}\n".format(k, v.__str__())
        return rep


class Input(IO):  # UserDict):  I'm having trouble with UserDict, it's .data attribute, and recursion with __setattr__
    """
    Stores a collection of input channels which can be resolved to get the most recently pushed which does not resolve
    to an instance of `NotData` or a (subset of) list-like data containing any `NotData` elements.

    Raises a RuntimeError if it gets to the end of one of its stacks without finding valid data.

    *Only* allows items to be set if they are instances of `InputChannel`.

    Allows attribute-style setting and getting.
    """

    def __setitem__(self, key, item):
        if not isinstance(item, InputChannel):
            raise ValueError("Input only accepts InputChannel attributes but got {}.".format(type(item)))
        super(Input, self).__setitem__(key, item)

    def add_channel(self, channel_name, default=None):
        self.__setitem__(channel_name, InputChannel(default=default))


class Output(IO):
    """
    Stores a collection of output channels, all of which are guaranteed to be lazy.

    *Only* allows items to be set if they are instances of `OutputChannel`.
    """

    def __setitem__(self, key, item):
        if not isinstance(item, OutputChannel):
            raise ValueError("Output only accepts OutputChannel attributes but got", type(item))
        super(Output, self).__setitem__(key, item)

    def add_channel(self, channel_name, buffer_length=1):
        super(Output, self).__setitem__(channel_name, OutputChannel(buffer_length=buffer_length))
