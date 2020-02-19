# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function
import numpy as np

from pyiron_contrib.protocol.utils.dictionaries import IODictionary, InputDictionary
from pyiron_contrib.utils.misc import fullname
from pydoc import locate
from pyiron.atomistics.structure.atoms import Atoms

"""
Methods for handling hdf saving and loading.
"""

__author__ = "Dominik Gehringer, Liam Huber"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "Feb 18, 2020"


GENERIC_LIST_INDEX_FORMAT = 'i_{index}'

KNOWN_COMPLEX_TYPES = {str(cls): cls for cls in [Atoms, IODictionary, InputDictionary]}


def _try_save_key(k, v, hdf, exclude=(dict, tuple, list)):
    """
    Tries to save a simple value

    Args:
        k: (str) key name of the HDF entry
        v: (obj) value
        hdf: the hdf server

    Returns: (bool) wether saving the key was successful or not

    """
    # try to call to_hdf first
    if hasattr(v, 'to_hdf'):
        v.to_hdf(hdf, group_name=k)
        result = True
    else:
        if exclude is not None:
            if isinstance(v, exclude):
                return False
        try:
            # try to do it the easy way
            hdf[k] = v
            result = True
        except TypeError:
            result = False
    return result


def generic_to_hdf(value, hdf, group_name, logger=None):
    """
    Saves also dictionaries and lists to hdf
    Args:
        value (obj): The object to save.
        hdf: The hdf server.
        group_name (str): The group name where to store it.
    """
    if hasattr(value, 'to_hdf'):
        value.to_hdf(hdf, group_name=group_name)
    elif isinstance(value, dict):
        # if we deal with a dictionary we have to open a new group anyway
        with hdf.open(group_name) as server:
            # store class metadata
            server['TYPE'] = str(type(value))
            server['FULLNAME'] = fullname(value)
            for k, v in value.items():
                # try to save it
                if not isinstance(k, str):
                    # it is possible that the keys are not strings, thus we have to enforce this
                    if logger is not None:
                        logger.warning('Key "{}" is not a string, it will be converted to {}'.format(k, str(k)))
                    k = str(k)
                # try it the easy way first (either call v.to_hdf or directly save it
                if _try_save_key(k, v, server):
                    pass  # everything was successful
                else:
                    # well pyiron did not manage lets -> more complex object
                    generic_to_hdf(v, server, group_name=k)
    elif isinstance(value, (list, tuple)):
        # check if all do have the same type -> then we can make a numpy array out of it
        if len(value) == 0:
            pass  # there is nothing to do, no data to store
        else:
            first_type = type(value[0])
            same = all([type(v) == first_type for v in value])
            # if all items are of the same type and it is simple
            if same and issubclass(first_type, (float, complex, int, np.ndarray)):
                # that is trivial we do have an array
                if issubclass(first_type, np.ndarray):
                    # we do not want dtype=object, thus we do make this distinction
                    hdf[group_name] = np.array(value)
                else:
                    hdf[group_name] = np.array(value, dtype=first_type)
            else:
                with hdf.open(group_name) as server:
                    # again write the metadata
                    server['TYPE'] = str(type(value))
                    server['FULLNAME'] = fullname(value)
                    for i, v in enumerate(value):
                        index_key = GENERIC_LIST_INDEX_FORMAT.format(index=i)
                        if _try_save_key(index_key, v, server):
                            pass  # everything was successful
                        else:
                            generic_to_hdf(v, server, group_name=index_key)
    else:
        # so this one is the primitive item case
        # lets check if it has a to_hdf method
        try:
            value.to_hdf(hdf, group_name=group_name)
        except AttributeError:
            # Ok there is no to_hdf method however lets try it again
            try:
                hdf[group_name] = value
            except:
                # now we have no clue any more, we have to raise this error
                raise


def generic_from_hdf(hdf, group_name, logger=None):
    """
    Loads dicts, lists and tuples as well as their subclasses from an hdf file

    Args:
        hdf: the hdf server
        group_name: (str) the group name

    Returns: (obj) the object to return
    """

    # try a simple load
    if not hasattr(hdf[group_name], 'list_nodes') or 'TYPE' not in hdf[group_name].list_nodes():
        return hdf[group_name]
    # handle special types
    elif hdf[group_name]['TYPE'] in list(KNOWN_COMPLEX_TYPES.keys()):
        obj = KNOWN_COMPLEX_TYPES[hdf[group_name]['TYPE']]()
        obj.from_hdf(hdf, group_name)
        return obj
    # FULLNAME will only be present if generic_to_hdf wrote the underlying object
    elif 'FULLNAME' in hdf[group_name].keys():
        with hdf.open(group_name) as server:
            # convert the class qualifier to a type
            cls_ = locate(server['FULLNAME'])
            # handle a dictionary
            if issubclass(cls_, dict):
                result = {}
                # nodes are primitive objects -> that is easy
                for k in server.list_nodes():
                    # skip the special nodes
                    if k in ('TYPE', 'FULLNAME'):
                        continue
                    result[k] = server[k]

                for k in server.list_groups():
                    # groups are more difficult, since they're other objects -> give it a try
                    result[k] = generic_from_hdf(server, group_name=k)

                # create the instance -> we have to assume a constructor of type cls_(**kwargs) for that
                # NOTE: if the default constructor is not available this code will break
                result = cls_(result)
                return result
            elif issubclass(cls_, (list, tuple)):
                result = []
                # we have to keep track of the indices -> str.__cmp__ != int.__cmp__ we cannot assume an order
                indices = []

                for k in server.list_nodes():
                    if k in ('TYPE', 'FULLNAME'):
                        continue
                    # nodes are trivial
                    index = int(k.replace('i_', ''))
                    result.append(server[k])
                    indices.append(index)
                    # TODO: Since Atoms object appear as a node we might have to call it here too

                for k in server.list_groups():
                    # we do have the recursive call here
                    index = int(k.replace('i_', ''))
                    result.append(generic_from_hdf(server, group_name=k))
                    indices.append(index)

                # sort it, with the keys as indices
                result = sorted(enumerate(result), key=lambda t: indices[t[0]])
                # create the instance, and get rid of the instances
                result = cls_([val for idx, val in result])
                return result
            else:
                raise ImportError('Could not locate type({})'.format(server['FULLNAME']))
    else:
        raise TypeError('I do not know how to deserialize type({}), {}'.format(hdf[group_name], type(hdf[group_name])))
