# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import re
import numpy as np
from collections import OrderedDict
from pyiron_contrib.protocol.utils.pointer import Pointer
from pyiron_contrib.utils.misc import LoggerMixin

"""
Classes to setup input and output dataflows for protocols
"""

__author__ = "Dominik Gehringer, Liam Huber"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "December 10, 2019"

# define a regex to find integer values
integer_regex = re.compile(r'[-+]?([1-9]\d*|0)')


TIMELINE_DICT_KEY_FORMAT = 't_{time}'
GENERIC_LIST_INDEX_FORMAT = 'i_{index}'


class IODictionary(dict, LoggerMixin):
    """
    A dictionary class representing the parameters of a Command class. The dictionary holds a path which is recipe
    that can be resolved at runtime to obtain underlying values. A dictionary instance can hold multiple instances of
    IODictionary as value items which can be resolved into the real values when desired.
    """

    # those members are not accessible
    _protected_members = [
        'resolve',
        'to_hdf',
        'from_hdf'
    ]

    def __init__(self, **kwargs):
        super(IODictionary, self).__init__(**kwargs)

    def __getattr__(self, item):
        if item in IODictionary._protected_members:
            return object.__getattribute__(self, item)
        return self.__getitem__(item)

    def __getitem__(self, item):
        if item in self.keys():
            value = super(IODictionary, self).__getitem__(item)
            if isinstance(value, Pointer):
                return ~value
            elif isinstance(value, list):  # TODO: Allow other containers than list
                cls = type(value)
                return cls([element if not isinstance(element, Pointer) else ~element for element in value])
            else:
                return value
        return super(IODictionary, self).__getitem__(item)

    def __setattr__(self, key, value):
        super(IODictionary, self).__setitem__(key, value)

    def resolve(self):
        """
        Even though printing the dictionary, or asking for a particular item resolves paths fine, somehow using the **
        unpacking syntax fails to resolve pointers. This is to cover that issue since I couldn't find anything on
        google how to modify the ** behaviour.
        """
        resolved = {}
        for key in self.keys():
            resolved[key] = self.__getitem__(key)
        return resolved

    def _generic_to_hdf(self, value, hdf, group_name=None):
        from pyiron_contrib.utils.hdf import generic_to_hdf
        return generic_to_hdf(value, hdf, group_name=group_name)

    def _generic_from_hdf(self, hdf, group_name=None):
        from pyiron_contrib.utils.hdf import generic_from_hdf
        return generic_from_hdf(hdf, group_name=group_name)

    def to_hdf(self, hdf, group_name=None):
        with hdf.open(group_name) as hdf5_server:
            hdf5_server['TYPE'] = str(type(self))

            for key in list(self.keys()):
                # default value is not to save any property
                try:
                    value = getattr(self, key)
                    try:
                        value.to_hdf(hdf5_server, group_name=key)
                    except AttributeError:
                        self._generic_to_hdf(value, hdf5_server, group_name=key)
                except KeyError:
                    # to_hdf will get called *before* protocols have run, so the pointers in these dictionaries
                    # won't be able to resolve. For now just let it not resolve and don't save it.
                    continue
                except (RuntimeError, OSError):
                    # if a "key" is initialized with a primitive value and the and the graph was already saved
                    # it might happen that the "key" already exists hdf5_server[key] but is of wrong HDF5 type
                    # e.g dataset instead of group. Thus the underlying library will raise an runtime error.
                    # The current workaround now is to try to delete the dataset and rewrite it
                    # TODO: Change to `del hdf5_server[key]` once pyiron.base.generic.hdfio is fixed
                    import posixpath
                    # hdf5_server.h5_path is relative
                    del hdf5_server[posixpath.join(hdf5_server.h5_path, key)]
                    # now we try again
                    try:
                        value.to_hdf(hdf5_server, group_name=key)
                    except AttributeError:
                        self._generic_to_hdf(value, hdf5_server, group_name=key)
                    except Exception:
                        raise

    def from_hdf(self, hdf, group_name):
        with hdf.open(group_name) as hdf5_server:
            for key in hdf5_server.list_nodes():
                if key in ('TYPE', 'FULLNAME'):
                    continue
                # Nodes are leaves, so just save them directly
                # structures will be listed as nodes
                try:
                    setattr(self, key, hdf5_server[key])
                except Exception as e:
                    self.logger.exception('Failed to load "{}"'.format(key), exc_info=e)
                    setattr(self, key, self._generic_from_hdf(hdf5_server, group_name=key))

            for key in hdf5_server.list_groups():
                # Groups are more complex data types with their own depth
                # For now we only treat other IODicts and Atoms (i.e. structures) explicitly.
                setattr(self, key, self._generic_from_hdf(hdf5_server, group_name=key))


class InputDictionary(IODictionary):
    """
    An ``IODictionary`` which is instantiated with a child dictionary to store default values. If a requested item
    can't be found in this dictionary, a default value is sought.
    """

    def __init__(self):
        super(InputDictionary, self).__init__()
        self.default = IODictionary()

    def __getitem__(self, item):
        try:
            return super(InputDictionary, self).__getitem__(item)
        except (KeyError, IndexError):
            return self.default.__getitem__(item)

    def __getattr__(self, item):
        if item == 'default':
            return object.__getattribute__(self, item)
        else:
            return super(InputDictionary, self).__getattr__(item)

    def __setattr__(self, key, value):
        if key == 'default':
            object.__setattr__(self, key, value)
        else:
            super(InputDictionary, self).__setattr__(key, value)

    def keys(self):
        both_keys = set(super(InputDictionary, self).keys()).union(self.default.keys())
        for k in both_keys:
            yield k

    def values(self):
        for k in self.keys():
            yield self[k]

    def items(self):
        # Make sure the dictionary resolve pointers
        for k in self.keys():
            # It resolves the, since we call __getitem__
            yield k, self[k]

    def __iter__(self):
        # Make sure all keys get into the ** unpacking also those from the default dictionary
        return self.keys().__iter__()


class TimelineDict(LoggerMixin, OrderedDict):
    """
        Dictionary which acts as timeline
    """

    def _parse_key(self, k):

        # leftover should contain only a number, try to parse it
        integer_matches = integer_regex.findall(k)
        if len(integer_matches) > 1:
            self.logger.warning('More than one integer was found. I\'ll take the first one')
            integer_matches = [integer_matches[0]]

        try:
            result = int(integer_matches[0])
        except:
            raise KeyError(k)
        else:
            return result

    def keys(self):
        for k in super(TimelineDict, self).keys():
            yield TIMELINE_DICT_KEY_FORMAT.format(time=k)

    def items(self):
        for k, v in zip(self.keys(), super(TimelineDict, self).values()):
            yield k, v

    def _super_getitem(self, k):
        return super(TimelineDict, self).__getitem__(k)

    def _super_keys(self):
        return super(TimelineDict, self).keys()

    @property
    def timeline(self):
        return np.array(list(self._super_keys()))

    @property
    def data(self):
        return np.array(list(self.values()))

    @property
    def array(self):
        return np.array([
            list(self._super_keys()),
            list(self.values())
        ])

    def _check_key_type(self, key):
        if isinstance(key, str):
            time = self._parse_key(key)
        elif isinstance(key, int):
            time = key
        elif isinstance(key, float):
            self.logger.warning('Floating points number are not allowed here. They will be converted to an integer')
            time = int(key)
        else:
            raise TypeError('Only strings of format "%s", integers and floats are allowed as keys'.format(
                TIMELINE_DICT_KEY_FORMAT))
        return time

    def __setitem__(self, key, value):
        super(TimelineDict, self).__setitem__(self._check_key_type(key), value)

    def __getitem__(self, item):
        return super(TimelineDict, self).__getitem__(self._check_key_type(item))
