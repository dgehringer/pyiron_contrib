# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from pyiron_base.master.generic import GenericJob
from pyiron_base.generic.datacontainer import DataContainer

import numpy as np
from scipy.constants import physical_constants
from scipy.interpolate import CubicSpline

from pyiron_continuum.schroedinger.mesh import RectMesh
from pyiron_continuum.schroedinger.schroedinger import TISE

# physical constants
KB = physical_constants['Boltzmann constant in eV/K'][0]

class QuantumEquivalentTemperature(GenericJob):

    def __init__(self, project, job_name):
        super(QuantumEquivalentTemperature, self).__init__(project, job_name)
        self.__version__ = "0.0.1"
        self.__name__ = "QuantumEquivalentTemperature"
        self._python_only_job = True
        self.input = DataContainer(table_name="job_input")
        self.output = DataContainer(table_name="job_output")
        # general inputs
        self.input.potential = None
        self.input.mesh = None
        self.input.temperatures = None
        self.input.mass = None
        # internal
        self._tise_job = None

    def validate_ready_to_run(self):
        pass

    def get_classical_pd(self):
        self.output.pd_classical = []
        for temp in self.input.temperatures:
            pd_boltz = np.exp(-(self.input.potential - self.input.potential.min()) / (KB * temp))
            self.output.pd_classical.append(pd_boltz / pd_boltz.sum())
        self.output.pd_classical = np.array(self.output.pd_classical)

    def run_TISE_job(self):
        self._tise_job = self.project.create_job(TISE, 'tise_job', delete_existing_job=True)
        self._tise_job.input.potential = self.input.potential
        self._tise_job.input.mesh = RectMesh(bounds=[[self.input.mesh[0], self.input.mesh[-1]]],
                                          divisions=len(self.input.potential))
        self._tise_job.input.n_states = len(self.input.potential) - 1
        self._tise_job.input.mass = self.input.mass
        self._tise_job.run()

    def get_TISE_job_output(self):
        if self._tise_job is None:
            self._tise_job = self.project.load('tise_job')
        self.output.pd_quantum = []
        for temp in self.input.temperatures:
            pd_schroed = self._tise_job.output.get_boltzmann_rho(temperature=temp)
            self.output.pd_quantum.append(pd_schroed)
        self.output.pd_quantum = np.array(self.output.pd_quantum)

    def get_expectations(self):
        self.output.ex_mesh_classical = np.sum(self.output.pd_classical * self.input.mesh, axis=1)
        self.output.ex_mesh_quantum = np.sum(self.output.pd_quantum * self.input.mesh, axis=1)

    @staticmethod
    def get_equivalent_temperature(temperatures, class_x, quant_x):
        fit_eqn = CubicSpline(x=temperatures, y=class_x)
        fine_temperatures = np.linspace(temperatures[0], temperatures[-1] + 200, 100000, endpoint=True)
        fine_class_x = fit_eqn(fine_temperatures)
        return np.array([fine_temperatures[np.argmin(np.abs(fine_class_x - q))] for q in quant_x])

    def get_equivalent_classical_temperature(self):
        self.output.equivalent_classical_temperatures = self.get_equivalent_temperature(self.input.temperatures,
                                                                                        self.output.ex_mesh_classical,
                                                                                        self.output.ex_mesh_quantum)

    def run_static(self):
        self.get_classical_pd()
        self.run_TISE_job()
        self.get_TISE_job_output()
        self.get_expectations()
        self.get_equivalent_classical_temperature()
        self.to_hdf(self.project_hdf5)

    def to_hdf(self, hdf=None, group_name=None):
        """
        Store the object in the HDF5 File.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        super(QuantumEquivalentTemperature, self).to_hdf(hdf=hdf, group_name=group_name)
        self.input.to_hdf(self.project_hdf5)
        self.output.to_hdf(self.project_hdf5)

    def from_hdf(self, hdf=None, group_name=None):
        """
        Restore the object from the HDF5 File.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        super(QuantumEquivalentTemperature, self).from_hdf(hdf=hdf, group_name=group_name)
        self.input.from_hdf(self.project_hdf5)
        self.output.from_hdf(self.project_hdf5)



