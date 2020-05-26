# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function
from pyiron_contrib.protocol.graph import Graph
from pyiron.base.job.generic import GenericJob
from pyiron_contrib.protocol.atomistic.graphs.minimize import Minimize
from pyiron.base.generic.hdfio import ProjectHDFio

"""
Connect graphs and pyiron jobs.
"""

__author__ = "Liam Huber, Dominik Gehringer, Jan Janssen"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "Feb 15, 2020"


class Protocol(GenericJob, Graph):
    """
    A parent class for graphs which are being instantiated as regular pyiron jobs, i.e. the highest level graph in
    their context.

    Example: if `X` inherits from `Graph` and performs the desired logic, then
    ```
    class ProtocolX(Protocol, X):
        pass
    ```
    can be added to the `pyiron_contrib`-level `__init__` file and jobs performing X-logic can be instantiated with
    in a project `pr` with the name `job_name` using `pr.create_job(pr.job_type.ProtocolX, job_name)`.
    """

    def __init__(self, project=None, job_name=None):
        super(Protocol, self).__init__(project=project, job_name=job_name)
        self.vertex_name = job_name
        self.hdf = self.project_hdf5

    def execute(self):
        super(Protocol, self).execute()

    def run_static(self):
        """If this Graph is the highest level, it can be run as a regular pyiron job."""
        self.status.running = True
        self.execute()
        self.status.collect = True  # Assume modal for now
        self.run()  # This is an artifact of inheriting from GenericJob, to get all that run functionality

    def run(self, run_again=False, repair=False, debug=False, run_mode=None, continue_run=False):
        """A wrapper for the run which allows us to simply keep going with a new variable `continue_run`"""
        if continue_run:
            self.status.created = True
        super(Protocol, self).run(run_again=run_again, repair=repair, debug=debug, run_mode=run_mode)

    def collect_output(self):
        # Dear Reader: This feels like a hack, but it works. Sincerely, -Liam
        self.to_hdf()

    def write_input(self):
        # Dear Reader: I looked at base/master/list and /parallel where this appears, but it's still not clear to me
        # what I should be using this for. But, I get a NotImplementedError if I leave it out, so here it is. -Liam
        pass

    def to_hdf(self, hdf=None, group_name=None):
        """
        Store the Protocol in an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        if hdf is None:
            hdf = self.project_hdf5
        GenericJob.to_hdf(self, hdf=hdf, group_name=group_name)
        Graph.to_hdf(self, hdf=hdf, group_name=group_name)

    def from_hdf(self, hdf=None, group_name=None):
        """
        Load the Protocol from an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        if hdf is None:
            hdf = self.project_hdf5
        GenericJob.from_hdf(self, hdf=hdf, group_name=group_name)
        Graph.from_hdf(self, hdf=hdf, group_name=group_name)


class ProtocolNewMinimize(Protocol, Minimize):
    def __init__(self, *args, **kwargs):
        Minimize.__init__(self, *args, **kwargs)
        Protocol.__init__(self, *args, **kwargs)
