# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from pyiron_contrib.utils.hdf import open_if_group, generic_to_hdf, generic_from_hdf
from pyiron_contrib.utils.hdf_tester import TestHasProjectHDF
import numpy as np


class TestOpenIfGroup(TestHasProjectHDF):

    def test(self):
        without_group = open_if_group(self.hdf, None)
        with_group = open_if_group(self.hdf, 'group')
        self.assertEqual(without_group.h5_path, '/')
        self.assertEqual(with_group.h5_path, '/group')


class TestGenericHDFers(TestHasProjectHDF):

    def test_simple(self):
        """Simple values that should be trivial"""

        generic_to_hdf(1, self.hdf, 'int')
        self.assertEqual(generic_from_hdf(self.hdf, 'int'), 1)

        generic_to_hdf('a', self.hdf, 'str')
        self.assertEqual(generic_from_hdf(self.hdf, 'str'), 'a')

    def test_complex(self):
        """Values which need some special treatment"""

        generic_to_hdf(np.array([1, 2, 3]), self.hdf, 'array')
        self.assertTrue(np.all(generic_from_hdf(self.hdf, 'array') == np.array([1, 2, 3])))

        generic_to_hdf(['c', 'b', 'a'], self.hdf, 'list')
        self.assertTrue(np.all(generic_from_hdf(self.hdf, 'list') == np.array(['c', 'b', 'a'])))

        dict_ = {'one': 1, 'eh': 'a'}
        generic_to_hdf(dict_, self.hdf, 'dict')
        self.assertTrue(np.all([dict_[k] == v for k, v in generic_from_hdf(self.hdf, 'dict').items()]))

        struct = self.project.create_ase_bulk('Al')
        generic_to_hdf(struct, self.hdf, 'structure')
        self.assertEqual(generic_from_hdf(self.hdf, 'structure'), struct)

        # TODO: Add other objects which have their own to_hdf?

    def test_nested(self):

        struct = self.project.create_ase_bulk('Al')
        nested = {'dictionary': {'char': 'a', 'array': np.array([1, 2, 3])},
                  'list': [struct.copy(), struct.copy()]}
        generic_to_hdf(nested, self.hdf, 'nested')
        loading = generic_from_hdf(self.hdf, 'nested')
        self.assertEqual(nested['dictionary']['char'], loading['dictionary']['char'])
        self.assertTrue(np.all(nested['dictionary']['array'] == loading['dictionary']['array']))
        self.assertTrue(np.all([s == struct for s in loading['list']]))
