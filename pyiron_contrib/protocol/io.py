# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function
from collections import UserList
from pyiron_contrib.protocol.lazy import Lazy, _override_methods, BASE_MAGIC_NAMES, \
    AUGMENTING_MAGIC_NAMES
from abc import ABC, abstractmethod
from pyiron_contrib.utils.misc import LoggerMixin

"""
Classes for input and output of vertices.

Because graphs are 'wired' before they are executed, input and output is handled by lazy channels. Input channels 
represent a stack of possible inputs, the first valid one being evaluated. Output channels are a stack of the most 
recent output.
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
    """
    An abstract class for handling stacks of lazy data. The `value` is a list of items, which are better thought of as
    stack since the last value is the most important one.

    Channels are lazy so that they can be referred to and manipulated as items for other input channels before they
    contain real data.
    """

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

    def to_hdf(self, hdf, group_name=None):
        """
        Store the Vertex in an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object.
            group_name (str): HDF5 subgroup name. (Default is None.)
        """
        if group_name is not None:
            hdf5_server = hdf.open(group_name)
        else:
            hdf5_server = hdf

        hdf5_server["TYPE"] = str(type(self))

        # TODO: Iterate over channels

    def from_hdf(self, hdf, group_name=None):
        """
        Load the Protocol from an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        if group_name is not None:
            hdf5_server = hdf.open(group_name)
        else:
            hdf5_server = hdf

        # TODO: Iterate over nodes or whatever. Probably separate load for I and O


class InputChannel(IOChannel):
    """
    A channel designed for input data, where resolution goes through the stack and returns the first element which is
    not of the class `NotData`.
    """

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
    A channel designed for output data, where more recent data is at the end of the stack. Resolution returns the entire
    list, but pushing a new item gets rid of the oldest item. This way the channel is the `buffer_length` most recent
    items.

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
    """
    A base class for input/output managers which can have multiple channels. Can be resolved to a regular dictionary.

    Allows attribute-style setting and getting.
    """

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

    @abstractmethod
    def __setitem__(self, key, item):
        pass

    @abstractmethod
    def add_channel(self, channel_name, **kwargs):
        pass

    def to_hdf(self, hdf, group_name=None):
        """
        Store the Vertex in an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object.
            group_name (str): HDF5 subgroup name. (Default is None.)
        """
        if group_name is not None:
            hdf5_server = hdf.open(group_name)
        else:
            hdf5_server = hdf

        hdf5_server["TYPE"] = str(type(self))

        for k, v in self.items():
            v.to_hdf(hdf5_server, k)

    def from_hdf(self, hdf, group_name=None):
        """
        Load the Protocol from an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        if group_name is not None:
            hdf5_server = hdf.open(group_name)
        else:
            hdf5_server = hdf

        # TODO: Iterate over nodes or whatever. Probably separate load for I and O


class Input(IO):  # UserDict):  I'm having trouble with UserDict, it's .data attribute, and recursion with __setattr__
    """
    Stores a collection of input channels. Resolution gives a dictionary of the top-most items in each channel which
    can be resolved.

    Raises a RuntimeError if it gets to the end of one of its stacks without finding valid data.

    *Only* allows items to be set if they are instances of `InputChannel`.
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


def _not_data_magic(magic_name, cls):
    """
    A replacement for magic methods for the `NotData` class. Just returns the same instance of `NotData`.

    Args:
        magic_name (str): The name of the python magic method being replaced.
        cls (Lazy): The class to decorate. It had better be `Lazy`.

    Returns:
        (fnc): A new function which just returns self.
    """
    def fn(self, *args, **kwargs):
        return self
    return fn


@_override_methods(_not_data_magic, BASE_MAGIC_NAMES)
@_override_methods(_not_data_magic, AUGMENTING_MAGIC_NAMES)
class NotData(object):
    """
    A datatype to indicate that an input stack really doesn't have data (since `None` might be valid input!) Most magic
    methods are overwritten so that a `NotData` instance stays `NotData` after maniplulation.
    """

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