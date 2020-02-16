from __future__ import print_function
# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from pyiron_contrib.protocol.graph import Vertex
import numpy as np

"""
Generic vertices fit for many graphs.
"""

__author__ = "Liam Huber, Dominik Gehringer"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "Feb 15, 2020"


class BinarySwitch(Vertex):
    """
    A vertex whose state is either 'true' or 'false' depending on the truth of its input.

    Input channels:
        state (bool): The value being checked.
    """
    def __init__(self, vertex_name=None):
        super(BinarySwitch, self).__init__(vertex_name=vertex_name)
        self.possible_vertex_states = ["true", "false"]
        self.vertex_state = "false"

    def init_io_channels(self):
        self.input.add_channel('state', False)

    def function(self, state):
        if state:
            self.vertex_state = "true"
        else:
            self.vertex_state = "false"

    def execute(self):
        """Just parse the input and do your physics, then store the output."""
        output_data = self.function(**self.input.resolve()) or {}
        self.update_and_archive(output_data)


class Counter(Vertex):
    """
    Increments by one at each execution.

    Output channels:
        n_counts (int): How many executions have passed. (Default is 0.)
    """

    def init_io_channels(self):
        self.output.add_channel('n_counts')

    def function(self):
        return {'n_counts': ~self.output.n_counts[-1] + 1}
