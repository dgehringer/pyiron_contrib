from __future__ import print_function
# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from collections import UserDict, UserList
from pyiron_contrib.protocol.lazy import Lazy
from abc import ABC, abstractmethod
from pyiron_contrib.protocol.utils.misc import LoggerMixin
import types

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


class NotData:
    """A datatype to indicate that an input stack really doesn't have data (since `None` might be valid input!)"""
    def __eq__(self, other):
        if isinstance(other, NotData):
            return True
        else:
            return False

    def __repr__(self):
        return "NotData"

    def __str__(self):
        return "NotData"


class IOChannel(UserList, ABC, LoggerMixin):
    """An abstract class for handling stacks of lazy data."""

    def __init__(self, *args, **kwargs):
        super(IOChannel, self).__init__(*args, **kwargs)

    def push(self, item):
        self.data.append(item)

    def append(self, item):
        self.push(item)

    def __iadd__(self, other):
        self.push(other)
        return self

    def __setitem__(self, key, value):
        self.logger.warning("Items cannot be assigned to stacks. Use `push`.")

    def __str__(self):
        return "{}({})".format(self.__class__.__name__, self.data.__str__())


class InputChannel(IOChannel):
    """A list with an alternative initialization argument and a push method."""

    def __init__(self, initlist=None, default=None):
        if initlist is not None and default is not None:
            raise ValueError("init_list and default cannot both be provided")
        if default is not None:
            super(InputChannel, self).__init__([default])
        else:
            super(InputChannel, self).__init__(initlist)


class OutputChannel(IOChannel):
    """
    A list with fixed length which rotates out old values.

    Attributes:
        buffer_length (int): The length of the channel. (Default is 1, pushing a new value removes the existing one.)
    """

    def __init__(self, buffer_length=1):
        super(OutputChannel, self).__init__()
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
            self.data = self.data[-length_change:]
        else:
            self.data = length_change*[NotData()] + self.data

    def push(self, item):
        super(OutputChannel, self).push(item)
        self.data = self.data[1:]


class IO(dict, ABC):

    def __init__(self):
        super(IO, self).__init__()  # Don't allow state from initialization

    @abstractmethod
    def resolve(self):
        pass

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

    def resolve(self):
        resolved_dict = {}
        for k, v in self.items():
            resolved_dict[k] = self._resolve_input_stack(v)
        return resolved_dict

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
        if not isinstance(item, InputChannel):
            raise ValueError("Input only accepts objects of type InputStack as attributes.")
        super(Input, self).__setitem__(key, item)

    def add_channel(self, channel_name, initlist=None, default=None):
        channel = InputChannel(initlist=initlist, default=default)
        self.__setitem__(channel_name, channel)


class Output(IO):
    """
    Stores a collection of output channels, all of which are guaranteed to be lazy.

    *Only* allows items to be set if they are instances of `OutputChannel`.
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
        if isinstance(item, Lazy):
            # Lazy isn't good enough for us, so make sure the user wasn't trying to be 'helpful'.
            item = ~item
        if not isinstance(item, OutputChannel):
            raise ValueError("Output can only contain output channels but got", type(item))
        super(Output, self).__setitem__(key, LazyForOutputChannel(item))

    def add_channel(self, channel_name, buffer_length=1):
        super(Output, self).__setitem__(channel_name, LazyForOutputChannel(OutputChannel(buffer_length=buffer_length)))


class LazyForOutputChannel(Lazy):
    """
    For `Output`, where we *know* that the object being wrapped is always an `OutputChannel`, we want to *not* be
    lazy when pushing to the channel. With a regular lazy class, to update the channel, we would need
    `output.foo.resolve().push(new_val)`

    Actually, the resolution can go an number of places in that expression, but it has to go *somewhere*. With this
    child class, we can simply call `output.foo.push(new_val)`, as we would intuitively expect.
    """
    def push(self, item):
        print("Pushing to lazy output channel")
        self.value.push(item)

    def append(self, item):
        print("Appending to lazy output channel")
        self.value.push(item)

    # item.__iadd__, i.e. +=, is already working as desired
