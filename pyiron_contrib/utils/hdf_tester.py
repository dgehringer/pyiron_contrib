# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

"""
A class for multiple testing classes to inherit from, so we need it somewhere in the python path eh.
"""

from __future__ import print_function
import os
import unittest
from pyiron import Project
from pyiron.base.generic.hdfio import ProjectHDFio


class TestHasProjectHDF(unittest.TestCase):
    """Re-use setup and teardowns"""

    @classmethod
    def setUpClass(cls):
        cls.execution_path = os.path.dirname(os.path.abspath(cls.__module__))
        cls.project = Project(os.path.join(cls.execution_path, cls.__name__ + "_tests"))
        cls.hdf = ProjectHDFio(cls.project, cls.__name__)

    @classmethod
    def tearDownClass(cls):
        cls.execution_path = os.path.dirname(os.path.abspath(cls.__module__))
        project = Project(os.path.join(cls.execution_path, cls.__name__ + "_tests"))
        project.remove(enable=True)
