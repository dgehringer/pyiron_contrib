from __future__ import print_function
# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from collections import UserDict, UserList
from pyiron_contrib.protocol.lazy import Lazy

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


class InputStack(UserList):
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

    def push(self, item):
        self.append(item)


class Input(dict):  #UserDict):  I'm having trouble with UserDict, .data, and recursion
    """
    Stores a collection of input stacks which can be resolved to get the top-most stack value which does not resolve to
    an instance of `NotData`.

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
            if not isinstance(val, NotData):
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
        if key == '_ipython_canary_method_should_not_exist_':  # Stupid jupyter notebooks...
            return
        if key not in list(self.keys()) and \
                not isinstance(item, NotData) and \
                not (isinstance(item, Lazy) and isinstance(~item, NotData)):
            # Note: This restriction ensures that all output fields wind up defined at Vertex initialization. In this
            #       way they are available for finding in other places, e.g. setting dumping periods. I'm not 100%
            #       convinced I like this restriction though.
            raise ValueError("New output fields must be initialized with the type `NotData`. A shortcut to do this is "
                             "to simply access the new field, e.g. `output.new_key`.")
        if not isinstance(item, Lazy):
            item = Lazy(item)
        super(Output, self).__setitem__(key, item)

    def __setattr__(self, key, item):
        self.__setitem__(key, item)

    def __getitem__(self, item):
        if item not in list(self.keys()):
            # Note: I'm really not sure I like this syntax. If we keep it, we could do something similar for Input...
            self.__setitem__(item, Lazy(NotData()))
        return super(Output, self).__getitem__(item)

    def __getattr__(self, item):
        return self.__getitem__(item)
