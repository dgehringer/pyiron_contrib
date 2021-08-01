# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from pyiron_contrib.protocol.compound.thermodynamic_integration import ProtoTILDPar
from pyiron_base.master.generic import GenericJob
from pyiron_base.generic.datacontainer import DataContainer

import numpy as np
from scipy import stats, constants
from os.path import abspath, join, isfile
from os import remove
from shutil import rmtree
from glob import glob
from time import sleep
from uncertainties.unumpy import uarray, nominal_values, std_devs

KB = constants.physical_constants['Boltzmann constant in eV/K'][0]


class FreeEnergy(GenericJob):

    def __init__(self, project, job_name):
        super(FreeEnergy, self).__init__(project, job_name)
        self.__version__ = "0.0.1"
        self.__name__ = "FreeEnergy"
        self._python_only_job = True
        self.input = DataContainer(table_name="job_input")
        self.output = DataContainer(table_name="job_output")
        self.input.temperature = None
        self.input.structure = None
        self.input.potential = None
        self._npt_job = None
        self._minimized_structure = None
        self._phonopy_job = None
        self._force_constants = None
        self._del_harm_to_eam = None
        self._tild_job = None

    @property
    def structure(self):
        return self.input.structure

    @structure.setter
    def structure(self, basis):
        self.input.structure = basis

    @staticmethod
    def _cleanup_job(job):
        """
        Removes all the child jobs (files AND folders) to save disk space and reduce file count, and only keeps
        the hdf file.
        """
        for f in glob(abspath(join(job.working_directory, '../..')) + '/' + job.job_name + '_*'):
            if isfile(f):
                remove(f)
            else:
                rmtree(f)

    def run_npt_md(self, pressure=0., temperature_damping_timescale=100., pressure_damping_timescale=1000.,
                   n_ionic_steps=5000, n_print=100, time_step=1., langevin=True):
        """
        Run an NPT-MD simulation using Lammps.
        """
        print("Running NPT-MD...")
        npt_md_folder = self.project.create_group("npt_md")
        npt_job = npt_md_folder.create.job.Lammps("npt_job")
        npt_job.structure = self.input.structure.copy()
        npt_job.potential = self.input.potential
        npt_job.calc_md(temperature=self.input.temperature,
                        pressure=pressure,
                        temperature_damping_timescale=temperature_damping_timescale,
                        pressure_damping_timescale=pressure_damping_timescale,
                        n_ionic_steps=n_ionic_steps,
                        n_print=n_print,
                        time_step=time_step,
                        langevin=langevin)
        npt_job.server.cores = self.server.cores
        npt_job.run()
        self._npt_job = npt_job

    def get_npt_md_structure(self, thermalize_snapshots=20):
        """
        Returns a minimized structure with cell and atom positions corresponding to the average structure from
            the NPT-MD simulation.
        """
        if self._npt_job is None:
            raise ValueError("`run_npt_md()´ needs to be called before `get_npt_md_structure()´")
        elif self._npt_job.status != "finished":
            raise ValueError("the NPT-MD job is not finished")
        else:
            self._cleanup_job(self._npt_job)
        print("Minimizing NPT-MD structure...")
        average_cell = np.mean(self._npt_job.output.cells[thermalize_snapshots:-1], axis=0)
        npt_md_folder = self.project.create_group("npt_md")
        min_npt_job = npt_md_folder.create.job.Lammps("min_npt_job")
        min_npt_job.structure = self.input.structure.copy()
        min_npt_job.structure.cell = average_cell
        min_npt_job.potential = self.input.potential
        min_npt_job.calc_minimize(pressure=None)
        min_npt_job.run()
        self._cleanup_job(min_npt_job)
        self.output.minimized_structure = self._minimized_structure = min_npt_job.get_structure()

    def get_A_to_G_correction(self, thermalize_snapshots=20, n_bins=100):
        """
        Returns the Helmholtz to Gibbs correction as described in https://doi.org/10.1103/PhysRevB.97.054102,
            section II D.
        """
        if self._npt_job is None:
            raise ValueError("`run_npt_md()´ needs to be called before `get_A_to_G_correction()´")
        print("Getting Helmholtz to Gibbs correction...")
        volumes = self._npt_job.output.volume[thermalize_snapshots:-1]
        _, bins = np.histogram(volumes, bins=n_bins, density=True)
        mu, sigma = stats.norm.fit(volumes)
        bins = (bins[1:] + bins[:-1]) / 2
        best_fit_line = stats.norm.pdf(bins, mu, sigma)
        normalized_probability = (best_fit_line / best_fit_line.sum()).max()
        self.output.A_to_G_correction = KB * self.input.temperature * np.log(normalized_probability)

    def run_phonopy(self):
        """
        Run Phonopy on the minimized NPT-MD structure.
        """
        if not self._minimized_structure:
            raise ValueError("`minimized structure´ is not set. Please run `get_npt_md_structure()´")
        print("Running phonopy...")
        phon_folder = self.project.create_group("phonons")
        phon_ref = phon_folder.create.job.Lammps("phonon_ref_job")
        phon_ref.structure = self._minimized_structure.copy()
        phon_ref.potential = self.input.potential
        phonopy_job = phon_ref.create_job(self.project.job_type.PhonopyJob, "phonopy_job")
        phonopy_job.input['interaction_range'] = \
            np.amin(np.linalg.norm(self._minimized_structure.cell.array, axis=0)) - 1e-8
        # phonopy_job.server.cores = self.server.cores
        phonopy_job.run()
        self._phonopy_job = phonopy_job

    def get_phonopy_output(self):
        """
        Return the force constants matrix and the analytical Quasi-Harmonic free energy from the Phonopy job.
        """
        if self._phonopy_job is None:
            raise ValueError("`run_phonopy()´ needs to be called before `get_phonopy_output()´")
        elif self._phonopy_job.status != "finished":
            raise ValueError("the Phonopy job is not finished")
        else:
            self._cleanup_job(self._phonopy_job)
        print("Getting force constants and reference QH free energy...")
        try:
            therm_prop = self._phonopy_job.get_thermal_properties(temperatures=self.input.temperature)
        except AttributeError:
            self.output.phonopy_job = self.project.load(self._phonopy_job.job_name)
            therm_prop = self._phonopy_job.get_thermal_properties(temperatures=self.input.temperature)
        self.output.qh_free_energy = therm_prop.free_energies.flatten()
        self.output.force_constants = self._force_constants = self._phonopy_job.phonopy.force_constants

    def run_harmonic_to_eam_tild(self, n_lambdas=5, lambda_bias=0.5, n_steps=3000, thermalization_steps=500,
                                 sampling_steps=100, convergence_check_steps=1000, fe_tol=0.5e-3, time_step=1.,
                                 temperature_damping_timescale=100., overheat_fraction=2., cutoff_factor=0.5,
                                 use_reflection=False, zero_k_energy=0.):
        """
        Run TILD between the non-interacting harmonic system and the interacting system.
        """
        if self._force_constants is None:
            raise ValueError("`force constants´ are not set. Please run `get_phonopy_output()´")
        print("Running TILD...")
        tild_folder = self.project.create_group("tild")
        # reference job A -> HessianJob
        ref_job_a = tild_folder.create.job.HessianJob("ref_job_a")
        ref_job_a.structure = self._minimized_structure.copy()
        ref_job_a.set_reference_structure(self._minimized_structure.copy())
        ref_job_a.set_force_constants(self._force_constants)
        ref_job_a.save()
        # reference job B -> Lammps
        ref_job_b = tild_folder.create.job.Lammps("ref_job_b")
        ref_job_b.structure = self._minimized_structure.copy()
        ref_job_b.potential = self.input.potential
        ref_job_b.save()
        # tild job
        tild_job = tild_folder.create_job(ProtoTILDPar, "tild_job")
        tild_job.input.temperature = self.input.temperature
        tild_job.input.ref_job_a_full_path = ref_job_a.path
        tild_job.input.ref_job_b_full_path = ref_job_b.path
        tild_job.input.n_lambdas = n_lambdas
        tild_job.input.lambda_bias = lambda_bias
        tild_job.input.n_steps = n_steps
        tild_job.input.thermalization_steps = thermalization_steps
        tild_job.input.sampling_steps = sampling_steps
        tild_job.input.convergence_check_steps = convergence_check_steps
        tild_job.input.fe_tol = fe_tol
        tild_job.input.time_step = time_step
        tild_job.input.temperature_damping_timescale = temperature_damping_timescale
        tild_job.input.overheat_fraction = overheat_fraction
        tild_job.input.cutoff_factor = cutoff_factor
        tild_job.input.use_reflection = use_reflection
        tild_job.input.zero_k_energy = zero_k_energy
        # tild_job.server.queue = self.server.queue
        # tild_job.server.cores = self.server.cores
        # if self.server.run_time is not None:
        #     tild_job.server.run_time = self.server.run_time
        # else:
        #     tild_job.server.run_time = 43200
        tild_job.run()
        self._tild_job = tild_job

    def get_tild_output(self, plot_integrands=True):
        """
        Return the free energy difference between the non-interacting harmonic system and the interacting system.
        """
        if self._tild_job is None:
            raise ValueError("`run_harmonic_to_eam_tild()´ needs to be called before `get_tild_output()´")
        elif self._tild_job.status != "finished":
            raise ValueError("the TILD job is not finished")
        else:
            self._cleanup_job(self._tild_job)
        print("Getting free energy between reference and EAM...")
        try:
            tild_job = self._tild_job
            hasattr(tild_job.output, 'tild_free_energy_mean')
        except KeyError:
            tild_job = self.project.load(self._tild_job.job_name)
        self.output.del_harm_to_eam = self._del_harm_to_eam = tild_job.output.tild_free_energy_mean[-1]
        self.output.del_harm_to_eam_se = tild_job.output.tild_free_energy_se[-1]
        if plot_integrands:
            tild_job.plot_tild_integrands()

    def get_G_per_atom(self):
        """
        Return the anharmonic free energy per atom at the input temperature for the input structure.
        """
        if self._del_harm_to_eam is None:
            raise ValueError("`get_tild_output()´ needs to be called before `get_G_per_atom()´")
        del_harm_to_eam = uarray(self.output.del_harm_to_eam, self.output.del_harm_to_eam_se)
        anharm_fe = self.output.qh_free_energy + del_harm_to_eam + self.output.A_to_G_correction
        anharm_fe_pa = anharm_fe / len(self.output.minimized_structure)
        self.output.anharm_G = nominal_values(anharm_fe_pa)
        self.output.anharm_G_se = std_devs(anharm_fe_pa)

    def run_static(self):
        """
        Run the methods.
        """
        self.run_npt_md()
        self.get_npt_md_structure()
        self.get_A_to_G_correction()
        self.run_phonopy()
        self.get_phonopy_output()
        self.run_harmonic_to_eam_tild()
        while self._tild_job.status != "finished":
            sleep(30)
        self.get_tild_output(plot_integrands=True)
        self.get_G_per_atom()
        self.to_hdf(self.project_hdf5)
        print("DONE")

    def to_hdf(self, hdf=None, group_name=None):
        """
        Store the FreeEnergy object in the HDF5 File.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        super(FreeEnergy, self).to_hdf(hdf=hdf, group_name=group_name)
        self.input.to_hdf(self.project_hdf5)
        self.output.to_hdf(self.project_hdf5)

    def from_hdf(self, hdf=None, group_name=None):
        """
        Restore the FreeEnergy object from the HDF5 File.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        super(FreeEnergy, self).from_hdf(hdf=hdf, group_name=group_name)
        self.input.from_hdf(self.project_hdf5)
        self.output.from_hdf(self.project_hdf5)
