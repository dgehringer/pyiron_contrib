# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from pyiron_base.master.generic import GenericJob
from pyiron_base.generic.datacontainer import DataContainer

import numpy as np
from scipy.stats import norm
from scipy.constants import physical_constants
from scipy.optimize import curve_fit
from os.path import abspath, join, isfile
from os import remove
from shutil import rmtree
from glob import glob
from uncertainties.unumpy import uarray, nominal_values, std_devs

import matplotlib.pyplot as plt

KB = physical_constants['Boltzmann constant in eV/K'][0]
HBAR = physical_constants['reduced Planck constant in eV s'][0]


class FreeEnergy(GenericJob):

    def __init__(self, project, job_name):
        super(FreeEnergy, self).__init__(project, job_name)
        self.__version__ = "0.0.1"
        self.__name__ = "FreeEnergy"
        self._python_only_job = True
        self.input = DataContainer(table_name="job_input")
        self.output = DataContainer(table_name="job_output")
        # general inputs
        self.input.classical_temperature = None
        self.input.quantum_temperature = None
        self.input.structure = None
        self.input.potential = None
        self.input.reference_oscillator = 'einstein_classical'
        # shared inputs
        self.input.temperature_damping_timescale = 100.
        self.input.time_step = 1.
        # md inputs
        self.input.md_steps = 5000
        self.input.md_sampling_steps = 10
        self.input.md_thermalization_steps = 100
        self.input.md_n_bins = 100
        # tild inputs
        self.input.tild_n_lambdas = 5
        self.input.tild_lambda_bias = 0.5
        self.input.tild_steps = 300
        self.input.tild_sampling_steps = 10
        self.input.tild_thermalization_steps = 50
        self.input.tild_convergence_check_steps = 150
        self.input.tild_fe_tol = 1e-3
        self.input.cutoff_factor = 0.5
        self.input.use_reflection = False
        # internal
        self._masses = None
        self._n_atoms = None
        self._thermalize_snapshots = None
        self._npt_job = None
        self._minimized_structure = None
        self._del_harm_to_eam = None
        self._phonopy_job = None
        self._tild_job = None

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

    def run_npt_md(self):
        """
        Run the NPT-MD simulation using Lammps.
        """
        print("Running NPT-MD...")
        npt_md_folder = self.project.create_group("npt_md")
        npt_job = npt_md_folder.create.job.Lammps("npt_job")
        npt_job.structure = self.input.structure.copy()
        npt_job.potential = self.input.potential
        npt_job.calc_md(temperature=self.input.classical_temperature,
                        pressure=0.,
                        temperature_damping_timescale=self.input.temperature_damping_timescale,
                        pressure_damping_timescale=1000.,
                        n_ionic_steps=self.input.md_steps,
                        n_print=self.input.md_sampling_steps,
                        time_step=self.input.time_step,
                        langevin=True)
        npt_job.run()
        self._npt_job = npt_job

    @staticmethod
    def gaus(x, a, mu, sigma):
        return a * np.exp(-(x - mu) ** 2 / (2 * sigma ** 2))

    def run_md_analysis(self, plot=True):
        """
        Returns the Helmholtz to Gibbs correction as described in https://doi.org/10.1103/PhysRevB.97.054102,
            section II D.
        """
        if self._npt_job is None:
            raise ValueError("`run_npt_md()´ needs to be called before `get_A_to_G_correction()´")
        print("Running MD analysis and getting Helmholtz to Gibbs correction...")
        self._thermalize_snapshots = int(self.input.md_thermalization_steps / self.input.md_sampling_steps)
        volumes = self._npt_job.output.volume[self._thermalize_snapshots:-1]
        pd, bins = np.histogram(volumes, bins=self.input.md_n_bins, density=True)
        pd /= pd.sum()
        mu, sigma = norm.fit(volumes)
        bins = (bins[1:] + bins[:-1]) / 2
        popt, pcov = curve_fit(self.gaus, bins, pd, p0=[1, mu, sigma])
        fine_bins = np.linspace(bins[0], bins[-1], 10000)
        best_fit_line = self.gaus(fine_bins, *popt)
        normalized_probability = best_fit_line.max()
        if plot:
            plt.plot(bins, pd / pd.sum(), label='raw')
            plt.plot(fine_bins, best_fit_line, label='fit')
            plt.xlabel('Volumes [$\AA^3$]')
            plt.ylabel('Probability density')
            plt.show()
        self.output.optimum_volume = fine_bins[np.argmax(best_fit_line)]
        self.output.optimum_cell = np.cbrt([self.output.optimum_volume]) * np.eye(3)
        self.output.fe_A_to_G_correction = KB * self.input.classical_temperature * np.log(normalized_probability)

    def get_spring_constants(self):
        print("Getting spring constant...")
        total_displacement = self._npt_job.output.total_displacements[self._thermalize_snapshots:-1]
        msd = [np.mean(np.sum(d ** 2, axis=1), axis=0) for d in total_displacement]
        pd, bins = np.histogram(msd, bins=self.input.md_n_bins, density=True)
        pd /= pd.sum()
        mu, sigma = norm.fit(msd)
        bins = (bins[1:] + bins[:-1]) / 2
        popt, pcov = curve_fit(self.gaus, bins, pd, p0=[1, mu, sigma])
        self.output.spring_constants = 3 * KB * self.input.classical_temperature / np.sum(bins * self.gaus(bins, *popt)) *  \
                                       np.ones(3 * self._n_atoms)

    def minimize_structure(self):
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
        npt_md_folder = self.project.create_group("npt_md")
        min_npt_job = npt_md_folder.create.job.Lammps("min_npt_job")
        min_npt_job.structure = self.input.structure.copy()
        min_npt_job.structure.cell = self.output.optimum_cell
        min_npt_job.potential = self.input.potential
        min_npt_job.calc_minimize(pressure=None)
        min_npt_job.run()
        self.output.minimized_energy = min_npt_job.output.energy_pot[-1]
        self._cleanup_job(min_npt_job)
        self.output.minimized_structure = min_npt_job.get_structure()

    def get_center_of_mass_correction(self):
        print("Getting center of mass correction...")
        self._masses = self.output.minimized_structure.get_masses_dof()
        volume = self.output.minimized_structure.get_volume()
        self._n_atoms = self.output.minimized_structure.get_number_of_atoms()
        Lambda = 17.458218 / np.sqrt(self.input.classical_temperature * np.mean(self._masses))
        self.output.fe_com = -KB * self.input.classical_temperature * (np.log(volume / (self._n_atoms * Lambda ** 3)) +
                                                             1.5 * np.log(self._n_atoms))

    def run_phonopy(self):
        """
        Run Phonopy on the minimized NPT-MD structure.
        """
        if not self.output.minimized_structure:
            raise ValueError("`minimized structure´ is not set. Please run `get_npt_md_structure()´")
        print("Running phonopy...")
        phon_folder = self.project.create_group("phonons")
        phon_ref = phon_folder.create.job.Lammps("phonon_ref_job")
        phon_ref.structure = self.output.minimized_structure.copy()
        phon_ref.potential = self.input.potential
        phonopy_job = phon_ref.create_job(self.project.job_type.PhonopyJob, "phonopy_job")
        phonopy_job.input['interaction_range'] = \
            np.amin(np.linalg.norm(self.output.minimized_structure.cell.array, axis=0)) - 1e-8
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
            therm_prop = self._phonopy_job.get_thermal_properties(temperatures=self.input.quantum_temperature)
        except AttributeError:
            self.output.phonopy_job = self.project.load(self._phonopy_job.job_name)
            therm_prop = self._phonopy_job.get_thermal_properties(temperatures=self.input.quantum_temperature)
        self.output.fe_quantum_harm = therm_prop.free_energies.flatten()
        self.output.force_constants = self._phonopy_job.phonopy.force_constants

    @staticmethod
    def force_constants_reshape(force_constants):
        force_shape = np.shape(force_constants)
        force_reshape = force_shape[0] * force_shape[2]
        return np.transpose(force_constants, (0, 2, 1, 3)).reshape((force_reshape, force_reshape))

    def get_phonopy_spring_constants(self):
        sc, _ = np.linalg.eigh(self.force_constants_reshape(self.output.force_constants))
        self.output.spring_constants = sc

    def get_classical_harmonic_free_energy(self):
        """
        Get the free energy of a classical harmonic oscillator. Temperature is clipped at 1 micro-Kelvin.
        Returns:
            float/np.ndarray: The sum of the free energy of each atom.
        """
        print("Getting reference classical harmonic free energy...")
        ROOT_EV_PER_ANGSTROM_SQUARE_PER_AMU_IN_S = 9.82269385e13
        temperature = np.clip(self.input.classical_temperature, 1e-6, np.inf)
        self.output.fe_classical_harm = 0
        for (spring, mass) in zip(self.output.spring_constants[3:], self._masses[3:]):
            if spring > 1e-4:
                hbar_omega = HBAR * np.sqrt(spring / mass) * ROOT_EV_PER_ANGSTROM_SQUARE_PER_AMU_IN_S
                self.output.fe_classical_harm -= KB * temperature * np.log((KB * temperature) / hbar_omega)

    def get_quantum_harmonic_free_energy(self):
        """
        Get the total free energy of a harmonic oscillator with this frequency and these atoms. Temperatures are clipped
        at 1 micro-Kelvin.
        Returns:
            float/np.ndarray: The sum of the free energy of each atom.
        """
        print("Getting reference quantum harmonic free energy...")
        ROOT_EV_PER_ANGSTROM_SQUARE_PER_AMU_IN_S = 9.82269385e13
        temperature = np.clip(self.input.quantum_temperature, 1e-6, np.inf)
        beta = 1. / (KB * temperature)
        self.output.fe_quantum_harm = 0
        for (spring, mass) in zip(self.output.spring_constants[3:], self._masses[3:]):
            if spring > 1e-4:
                hbar_omega = HBAR * np.sqrt(spring / mass) * ROOT_EV_PER_ANGSTROM_SQUARE_PER_AMU_IN_S
                self.output.fe_quantum_harm += (1. / 2) * hbar_omega + ((1. / beta) * np.log(1 - np.exp(-beta * hbar_omega)))

    def run_reference_to_eam_tild(self):
        """
        Run TILD between the non-interacting harmonic system and the interacting system.
        """
        if self.input.reference_oscillator == 'einstein_classical':
            force_constants = self.output.spring_constants[0]
        elif (self.input.reference_oscillator == 'debye_quantum') or \
                (self.input.reference_oscillator == 'debye_classical'):
            force_constants = self.output.force_constants
        else:
            raise ValueError
        print("Running TILD...")
        tild_folder = self.project.create_group("tild")
        # reference job A -> HessianJob
        ref_job_a = tild_folder.create.job.HessianJob("ref_job_a")
        ref_job_a.structure = self.output.minimized_structure.copy()
        ref_job_a.set_reference_structure(self.output.minimized_structure.copy())
        ref_job_a.set_force_constants(force_constants)
        ref_job_a.save()
        # reference job B -> Lammps
        ref_job_b = tild_folder.create.job.Lammps("ref_job_b")
        ref_job_b.structure = self.output.minimized_structure.copy()
        ref_job_b.potential = self.input.potential
        ref_job_b.save()
        # tild job
        tild_job = tild_folder.create.job.ProtoTILDPar("tild_job")
        tild_job.input.temperature = self.input.classical_temperature
        tild_job.input.ref_job_a_full_path = ref_job_a.path
        tild_job.input.ref_job_b_full_path = ref_job_b.path
        tild_job.input.n_lambdas = self.input.tild_n_lambdas
        tild_job.input.lambda_bias = self.input.tild_lambda_bias
        tild_job.input.n_steps = self.input.tild_steps
        tild_job.input.thermalization_steps = self.input.tild_thermalization_steps
        tild_job.input.sampling_steps = self.input.tild_sampling_steps
        tild_job.input.convergence_check_steps = self.input.tild_convergence_check_steps
        tild_job.input.fe_tol = self.input.tild_fe_tol
        tild_job.input.time_step = self.input.time_step
        tild_job.input.temperature_damping_timescale = self.input.temperature_damping_timescale
        tild_job.input.overheat_fraction = 2.
        tild_job.input.cutoff_factor = self.input.cutoff_factor
        tild_job.input.use_reflection = self.input.use_reflection
        tild_job.input.zero_k_energy = self.output.minimized_energy
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
        self.output.fe_del_harm_to_eam = self._del_harm_to_eam = tild_job.output.tild_free_energy_mean[-1]
        self.output.fe_del_harm_to_eam_se = tild_job.output.tild_free_energy_se[-1]
        if plot_integrands:
            tild_job.plot_tild_integrands()

    def get_G_per_atom(self):
        """
        Return the anharmonic free energy per atom at the input temperature for the input structure.
        """
        if (self.input.reference_oscillator == 'einstein_classical') or \
                (self.input.reference_oscillator == 'debye_classical'):
            fe_ref = self.output.fe_quantum_harm
        elif self.input.reference_oscillator == 'debye_quantum':
            fe_ref = self.output.fe_quantum_harm
        else:
            raise ValueError
        if self._del_harm_to_eam is None:
            raise ValueError("`get_tild_output()´ needs to be called before `get_G_per_atom()´")
        fe_del_harm_to_eam = uarray(self.output.fe_del_harm_to_eam, self.output.fe_del_harm_to_eam_se)
        anharm_fe = fe_ref + self.output.minimized_energy + fe_del_harm_to_eam + self.output.fe_A_to_G_correction + \
                    self.output.fe_com
        anharm_fe_pa = nominal_values(anharm_fe).flatten()[0] / self._n_atoms
        self.output.fe_G_per_atom = anharm_fe_pa
        self.output.fe_G_per_atom_se = std_devs(anharm_fe).flatten()[0]

    def run_static(self):
        """
        Run the methods.
        """
        self.run_npt_md()
        self.run_md_analysis()
        self.minimize_structure()
        self.get_center_of_mass_correction()
        if self.input.reference_oscillator == 'einstein_classical':
            self.get_spring_constants()
        elif (self.input.reference_oscillator == 'debye_classical') or \
                (self.input.reference_oscillator == 'debye_quantum'):
            self.run_phonopy()
            self.get_phonopy_output()
            self.get_phonopy_spring_constants()
        else:
            raise ValueError
        self.get_classical_harmonic_free_energy()
        self.get_quantum_harmonic_free_energy()
        self.run_reference_to_eam_tild()
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
