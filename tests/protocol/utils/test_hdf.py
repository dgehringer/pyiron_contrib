# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from pyiron_contrib.utils.hdf import open_if_group, generic_to_hdf, generic_from_hdf
from pyiron_contrib.utils.hdf_tester import TestHasProjectHDF


class TestOpenIfGroup(TestHasProjectHDF):

    def test(self):
        without_group = open_if_group(self.hdf, None)
        with_group = open_if_group(self.hdf, 'group')
        self.assertEqual(without_group.h5_path, '/')
        self.assertEqual(with_group.h5_path, '/group')
