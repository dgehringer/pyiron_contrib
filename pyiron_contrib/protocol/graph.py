from __future__ import print_function
# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from pyiron_contrib.protocol.utils import LoggerMixin
# from pyiron_contrib.protocol.utils.types import PyironJobTypeRegistry
from abc import ABC

"""
The goal here is to abstract and simplify the graph functionality.
"""


__author__ = "Liam Huber, Dominik Gehringer"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "Feb 10, 2020"


class Vertex(LoggerMixin, ABC):
    pass


class Graph(dict, LoggerMixin):
    pass


class Vertices(dict):
    pass


class Edges(dict):
    pass
