# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function
from collections import UserList
from pyiron_contrib.protocol.lazy import Lazy, NotData
from abc import ABC, abstractmethod
from pyiron_contrib.utils.misc import LoggerMixin
from pyiron_contrib.utils.hdf import generic_to_hdf, generic_from_hdf, open_if_group

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

    def from_hdf(self, hdf, group_name=None):
        print("Input channel from hdf {}/{}".format(hdf, group_name))
        super(InputChannel, self).from_hdf(hdf, group_name)

    def to_hdf(self, hdf, group_name=None):
        """
        Store the channel in an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object.
            group_name (str): HDF5 subgroup name. (Default is None.)
        """
        hdf5_server = open_if_group(hdf, group_name)
        hdf5_server["TYPE"] = str(type(self))
        try:
            val = self.resolve()
        except RuntimeError:
            val = NotData()
        generic_to_hdf(val, hdf5_server, group_name="resolution")

    def from_hdf(self, hdf, group_name=None):
        """
        Load the channel from an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object.
            group_name (str): HDF5 subgroup name. (Default is None.)
        """
        hdf5_server = open_if_group(hdf, group_name)
        value = generic_from_hdf(hdf5_server, "resolution")
        if not isinstance(value, NotData):
            self.push(value)


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

    def to_hdf(self, hdf, group_name=None):
        """
        Store the channel in an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object.
            group_name (str): HDF5 subgroup name. (Default is None.)
        """
        hdf5_server = open_if_group(hdf, group_name)
        hdf5_server["TYPE"] = str(type(self))
        hdf5_server["bufferlength"] = self.buffer_length
        generic_to_hdf(self.resolve(), hdf5_server, group_name='value')

    def from_hdf(self, hdf, group_name=None):
        """
        Load the channel from an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object.
            group_name (str): HDF5 subgroup name. (Default is None.)
        """
        hdf5_server = open_if_group(hdf, group_name)
        self.buffer_length = hdf5_server['bufferlength']
        value = generic_from_hdf(hdf5_server, 'value')
        for v in value[::-1]:
            self.push(v)


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

    def to_hdf(self, hdf, group_name=None):
        """
        Store the each channel in an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object.
            group_name (str): HDF5 subgroup name. (Default is None.)
        """
        hdf5_server = open_if_group(hdf, group_name)
        hdf5_server["TYPE"] = str(type(self))
        for k, v in self.items():
            v.to_hdf(hdf5_server, k)

    def _from_hdf_pattern(self, hdf, group_name=None, cls=None):
        """
        Load the all channels from an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object.
            group_name (str): HDF5 subgroup name. (Default is None)
        """
        hdf5_server = open_if_group(hdf, group_name)
        for k in hdf5_server.list_groups():
            v = cls()
            v.from_hdf(hdf5_server, group_name=k)
            self[k] = v


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

    def from_hdf(self, hdf, group_name=None):
        """
        Load the all input channels from an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object.
            group_name (str): HDF5 subgroup name. (Default is None)
        """
        self._from_hdf_pattern(hdf, group_name=group_name, cls=InputChannel)


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

    def from_hdf(self, hdf, group_name=None):
        """
        Load the all output channels from an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object.
            group_name (str): HDF5 subgroup name. (Default is None)
        """
        self._from_hdf_pattern(hdf, group_name=group_name, cls=OutputChannel)
