# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function
from os.path import abspath, join, isfile
from os import remove
from shutil import rmtree
from glob import glob
import numpy as np

from pyiron_base.generic.datacontainer import DataContainer

__author__ = "Raynol Dsouza"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Raynol Dsouza"
__email__ = "dsouza@mpie.de"
__status__ = "development"
__date__ = "August 02, 2021"


def cleanup_job(job):
    """
    Removes all the child jobs (files AND folders) to save disk space and reduce file count, and only retains
    the hdf file.
    """
    for f in glob(abspath(join(job.working_directory, "../..")) + "/" + job.job_name + "_*"):
        if isfile(f):
            remove(f)
        else:
            rmtree(f)


class Input(DataContainer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.generic = GenericInput(table_name='generic_input')
        self.md = MDInput(table_name='md_input')


class GenericInput(DataContainer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._temperatures = None
        self.initial_structure = None
        self.supercell_size = 2
        self.potential = None
        self.queue = None
        self.tild_lambdas = 3
        self.tild_n_steps = 100
        self.tild_thermalization_steps = 10
        self.tild_sampling_steps = 1
        self.tild_convergence_steps = 5
        self.tild_fe_tol = 1e-3
        self.sleep_time = 0.01
        self.tild_cores = 1
        self.tild_runtime = 3600
        self.spring_constant = 2.
        self.lambda_bias = 0.65

    @property
    def temperatures(self):
        return self._temperatures

    @temperatures.setter
    def temperatures(self, value):
        if isinstance(value, (float, int)):
            value = np.array([value])
        elif isinstance(value, list):
            value = np.array(value)
        self._temperatures = value


class MDInput(DataContainer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.temperature_damping_timescale = 100.
        self.time_step = 1.
        self.steps = 1000
        self.sampling_steps = 1
        self.cores = 1
        self.runtime = 3600


class PhononInput(DataContainer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.strain_low = -0.07
        self.strain_high = 0.07
        self.n_strains = 5
        self.fit_polynomial = 4
        self.cores = 1
        self.runtime = 3600
