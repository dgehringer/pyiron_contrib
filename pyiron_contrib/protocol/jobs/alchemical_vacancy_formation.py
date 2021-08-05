# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import numpy as np
from scipy import stats, constants

from pyiron_atomistics import Project
from pyiron_base.generic.datacontainer import DataContainer

from pyiron_contrib.protocol.jobs.vacancy_formation_utility import cleanup_job, GenericInput, MDInput, PhononInput

from uncertainties.unumpy import uarray, nominal_values, std_devs

KB = constants.physical_constants['Boltzmann constant in eV/K'][0]
HBAR = constants.physical_constants['Planck constant over 2 pi in eV s'][0]
ROOT_EV_PER_ANGSTROM_SQUARE_PER_AMU_IN_S = 9.82269385e13

__author__ = "Raynol Dsouza"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Raynol Dsouza"
__email__ = "dsouza@mpie.de"
__status__ = "development"
__date__ = "August 02, 2021"


class ThermalExpansion:

    def __init__(self, project):
        super().__init__()
        self.project = Project(project)
        self.input = DataContainer(table_name='job_input')
        self.input.generic = GenericInput(table_name='generic_input')
        self.input.md = MDInput(table_name='md_input')
        self.output = DataContainer(table_name='job_output')

    def _npt_md(self, project, temperature, structure):
        """
        Run an NPT-MD simulation at the input temperature using Lammps.
        """
        npt_job = project.create.job.Lammps("npt_" + str(temperature).replace(".", "_"))
        npt_job.structure = structure.copy()
        npt_job.potential = self.input.generic.potential
        npt_job.calc_md(temperature=temperature,
                        pressure=0.,
                        temperature_damping_timescale=self.input.md.temperature_damping_timescale,
                        time_step=self.input.md.time_step,
                        n_ionic_steps=self.input.md.steps,
                        n_print=self.input.md.sampling_steps,
                        langevin=True)
        npt_job.server.queue = self.input.generic.queue
        npt_job.server.cores = self.input.md.cores
        npt_job.server.runtime = self.input.md.runtime
        npt_job.run()
        return npt_job

    def run_thermal_expansion(self, group='bulk'):
        structure = self.input.generic.initial_structure.copy()
        if group == 'bulk':
            name = 'bulk_thermal_expansion'
        elif group == 'vacancy':
            name = 'vacancy_thermal_expansion'
            structure.pop(0)
        else:
            name = None
        pr_therm_exp = self.project.create_group(name)
        for temp in self.input.generic.temperatures:
            self._npt_md(project=pr_therm_exp, temperature=temp, structure=structure)

    def _inspect_npt_jobs(self, group):
        if group == 'bulk':
            name = 'bulk_thermal_expansion'
        elif group == 'vacancy':
            name = 'vacancy_thermal_expansion'
        else:
            name = None
        pr_therm_exp = self.project.create_group(name)
        npt_jobs = []
        for temp in self.input.generic.temperatures:
            npt_jobs.append(pr_therm_exp.inspect("npt_" + str(temp).replace(".", "_")))
        return npt_jobs

    def process_thermal_expansion(self, group, thermalize_snapshots, n_bins):
        npt_jobs = self._inspect_npt_jobs(group=group)
        all_bins = []
        all_normed_pds = []
        all_means = []
        all_sigmas = []
        for job in npt_jobs:
            if job.status == 'finished':
                volumes = job['output/generic/volume'][thermalize_snapshots:-1]
                _, bins = np.histogram(volumes, bins=n_bins, density=True)
                mu, sigma = stats.norm.fit(volumes)
                all_bins.append((bins[:-1] + bins[1:]) / 2)
                all_normed_pds.append(stats.norm.pdf(all_bins[-1], mu, sigma))
                all_means.append(mu)
                all_sigmas.append(sigma)
                cleanup_job(job)
            else:
                raise RuntimeError(job.name + " is " + job.status)
        return all_bins, all_normed_pds, all_means, all_sigmas

    @staticmethod
    def _find_gaussian_intersection(mean_1, mean_2, std_1, std_2):
        a = 1 / (2 * std_1 ** 2) - 1 / (2 * std_2 ** 2)
        b = mean_2 / (std_2 ** 2) - mean_1 / (std_1 ** 2)
        c = mean_1 ** 2 / (2 * std_1 ** 2) - mean_2 ** 2 / (2 * std_2 ** 2) - np.log(std_2 / std_1)
        roots = np.roots([a, b, c])
        return roots[np.argmin(np.abs(roots - np.mean([mean_1, mean_2])))]

    def run_get_optimum_volumes(self):
        self.run_thermal_expansion(group='bulk')
        self.run_thermal_expansion(group='vacancy')

    def get_optimum_volumes_rhos(self, thermalize_snapshots=20, n_bins=1000):
        self.output.bulk_all_bins, self.output.bulk_all_pdfs, b_means, b_sigmas = self.process_thermal_expansion(
            group='bulk',
            thermalize_snapshots=thermalize_snapshots,
            n_bins=n_bins)
        self.output.vac_all_bins, self.output.vac_all_pdfs, v_means, v_sigmas = self.process_thermal_expansion(
            group='vacancy',
            thermalize_snapshots=thermalize_snapshots,
            n_bins=n_bins)
        self.output.bulk_lattice_constants = np.cbrt(b_means) / self.input.generic.supercell_size
        self.output.vac_lattice_constants = np.cbrt(v_means) / self.input.generic.supercell_size
        self.output.optimum_volumes = []
        self.output.optimum_rhos = []
        for i in np.arange(len(self.input.generic.temperatures)):
            self.output.optimum_volumes.append(self._find_gaussian_intersection(
                mean_1=b_means[i], mean_2=v_means[i], std_1=b_sigmas[i], std_2=v_sigmas[i]))
            self.output.optimum_rhos.append(self.output.bulk_all_pdfs[i][np.argmin(
                np.abs(self.output.bulk_all_bins[i] - self.output.optimum_volumes[-1]))])
        self.output.optimum_rhos = np.array(self.output.optimum_rhos)
        self.output.optimum_lattice_constants = np.cbrt(self.output.optimum_volumes) / self.input.generic.supercell_size
        # n_atoms = self.input.generic.initial_structure.get_number_of_atoms()
        # self.output.del_A_form_to_G_form = KB * self.temperatures * np.log(self.output.optimum_rhos ** (1 / n_atoms))


class Phonons:

    def __init__(self, project):
        super().__init__()
        self.project = Project(project)
        self.input = DataContainer(table_name='job_input')
        self.input.generic = GenericInput(table_name='generic_input')
        self.input.phon = PhononInput(table_name='phon_input')
        self.output = DataContainer(table_name='job_output')

    def minimize_structures(self, lattice_constants, group='bulk', strain=False):
        min_folder = self.project.create_group('minimize_structures')
        group_folder = min_folder.create_group(group)
        self.output.optimized_structures = []
        self.output.zero_k_energies = []
        structures = self._generate_structures(lattice_constants, strain=strain)
        for temp, struct in zip(self.input.generic.temperatures, structures):
            min_job = group_folder.create.job.Lammps("min_" + str(temp).replace(".", "_"))
            min_job.structure = struct
            if group == 'vacancy':
                min_job.structure.pop(0)
            min_job.potential = self.input.generic.potential
            min_job.calc_minimize(pressure=None)
            min_job.run()
            self.output.optimized_structures.append(min_job.get_structure())
            self.output.zero_k_energies.append(min_job.output.energy_pot[-1])
            cleanup_job(min_job)

    def _generate_structures(self, lattice_constants, strain=False):
        x = np.argmax(list(self.input.generic.initial_structure.analyse.pyscal_cna_adaptive().values()))
        element = self.input.generic.initial_structure.get_species_symbols()[0]
        structures = []
        if strain and (lattice_constants is None):
            strain_list = np.linspace(self.input.phon.strain_low, self.input.phon.strain_high,
                                      self.input.phon.n_strains)
            if x in [1, 3]:
                struct = self.project.create.structure.bulk(element, cubic=True)
                struct = struct.repeat(self.input.generic.supercell_size)
            else:
                struct = None
            for strain in strain_list:
                strained_structure = struct.copy().apply_strain(strain, return_box=True)
                structures.append(strained_structure)
        elif (lattice_constants is not None) and not strain:
            for latt in lattice_constants:
                if x in [1, 3]:
                    struct = self.project.create.structure(element, a=latt, cubic=True)
                    structures.append(struct.repeat(self.input.generic.supercell_size))
        return structures

class Alchemical:

    def __init__(self, project):
        super().__init__()
        self.project = Project(project)
        self._bulk_npt_jobs = None
        self._vac_npt_jobs = None
        self._phon_jobs = None
        self._harm_to_eam_jobs = None
        self._eam_to_dec_jobs = None
        self.harm_to_eam_jobs_done = False
        self.eam_to_dec_jobs_done = False
        self.input = DataContainer(table_name='job_input')
        self.input.generic = GenericInput(table_name='generic_input')
        self.input.md = MDInput(table_name='md_input')



    def _run_phonopy(self):
        pr_phon = self.project.create_group('optimum_structure_phonons')
        for temp, struct in zip(self.temperatures, self.output.optimized_structures):
            print("Running phonopy @ {} K...".format(temp))
            phon_ref = pr_phon.create.job.Lammps("phon_ref_" + str(temp).replace(".", "_"))
            phon_ref.structure = struct.copy()
            phon_ref.potential = self.potential
            phonopy_job = phon_ref.create_job(self.project.job_type.PhonopyJob, "phon_" + str(temp).replace(".", "_"))
            phonopy_job.input['interaction_range'] = \
                np.amin(np.linalg.norm(struct.cell.array, axis=0)) - 1e-8
            phonopy_job.server.queue = self.queue
            phonopy_job.server.cores = self.phon_cores
            phonopy_job.server.runtime = self.phon_runtime
            phonopy_job.run()

    def _load_phonopy_jobs(self):
        pr_phon = self.project.create_group('optimum_structure_phonons')
        self._phon_jobs = []
        for temp in self.temperatures:
            self._phon_jobs.append(pr_phon.load("phon_" + str(temp).replace(".", "_")))

    def run_phase_2(self):
        self._minimize_structures()
        self._run_phonopy()

    def process_phase_2(self):
        self._load_phonopy_jobs()
        self.output.qh_fes = []
        self.output.force_constants = []
        for temp, phon_job in zip(self.temperatures, self._phon_jobs):
            if phon_job.status == 'finished':
                therm_prop = phon_job.get_thermal_properties(temperatures=temp)
                self.output.qh_fes.append(therm_prop.free_energies.flatten())
                self.output.force_constants.append(phon_job.phonopy.force_constants)
                cleanup_job(phon_job)
        self.output.qh_fes = np.array(self.output.qh_fes).flatten()

    def _run_harm_to_eam_tild(self):
        pr_harm_tild = self.project.create_group('harmonic_to_eam_free_energy')
        if not self.harm_to_eam_jobs_done:
            for temp, struct, fc, en in zip(self.temperatures, self.output.optimized_structures,
                                            self.output.force_constants, self.output.zero_k_energies):
                pr_temp = pr_harm_tild.create_group(str(temp).replace(".", "_"))
                ref_job_a = pr_temp.create.job.HessianJob("ref_job_a")
                ref_job_a.structure = struct.copy()
                ref_job_a.set_reference_structure(struct.copy())
                ref_job_a.set_force_constants(fc)
                ref_job_a.save()

                ref_job_b = pr_temp.create.job.Lammps("ref_job_b")
                ref_job_b.structure = struct.copy()
                ref_job_b.potential = self.potential
                ref_job_b.save()

                tild_job = pr_temp.create.job.ProtoTILDPar("tild_job")
                tild_job.input.temperature = temp
                tild_job.input.ref_job_a_full_path = ref_job_a.path
                tild_job.input.ref_job_b_full_path = ref_job_b.path
                tild_job.input.n_lambdas = self.tild_lambdas
                tild_job.input.n_steps = self.tild_n_steps
                tild_job.input.thermalization_steps = self.tild_thermalization_steps
                tild_job.input.sampling_steps = self.tild_sampling_steps
                tild_job.input.convergence_check_steps = self.tild_convergence_steps
                tild_job.input.fe_tol = self.tild_fe_tol
                tild_job.input.zero_k_energy = en
                tild_job.input.time_step = self.time_step
                tild_job.input.temperature_damping_timescale = self.temperature_damping_timescale
                tild_job.input.sleep_time = self.sleep_time
                tild_job.server.cores = self.tild_cores
                tild_job.server.queue = self.queue
                tild_job.server.run_time = self.tild_run_time
                tild_job.run()
            self._harm_to_eam_jobs_done = True

    def _run_eam_to_dec_osc_tild(self):
        pr_dec_tild = self.project.create_group('eam_to_decoupled_oscillator_free_energy')
        if not self.eam_to_dec_jobs_done:
            for temp, struct in zip(self.temperatures, self.output.optimized_structures):
                pr_temp = pr_dec_tild.create_group(str(temp).replace(".", "_"))
                ref_job_a = pr_temp.create.job.Lammps("ref_job_a")
                ref_job_a.structure = struct.copy()
                ref_job_a.potential = self.potential
                ref_job_a.save()

                ref_job_for_b = pr_temp.create.job.Lammps("ref_job_for_b")
                ref_job_for_b.structure = struct.copy()
                ref_job_for_b.potential = self.potential
                ref_job_for_b.save()
                ref_job_b = pr_temp.create.job.DecoupledOscillators("ref_job_b")
                ref_job_b.input.ref_job_full_path = ref_job_for_b.path
                ref_job_b.input.structure = struct.copy()
                ref_job_b.input.oscillators_id_list = [0]
                ref_job_b.input.spring_constants_list = [self.spring_constant] * len(ref_job_b.input.oscillators_id_list)
                ref_job_b.save()

                tild_job = pr_temp.create.job.ProtoTILDPar("tild_job")
                tild_job.input.temperature = temp
                tild_job.input.ref_job_a_full_path = ref_job_a.path
                tild_job.input.ref_job_b_full_path = ref_job_b.path
                tild_job.input.n_lambdas = self.tild_lambdas
                tild_job.input.lambda_bias = self.lambda_bias
                tild_job.input.n_steps = self.tild_n_steps
                tild_job.input.thermalization_steps = self.tild_thermalization_steps
                tild_job.input.sampling_steps = self.tild_sampling_steps
                tild_job.input.convergence_check_steps = self.tild_convergence_steps
                tild_job.input.fe_tol = self.tild_fe_tol
                tild_job.input.time_step = self.time_step
                tild_job.input.temperature_damping_timescale = self.temperature_damping_timescale
                tild_job.input.sleep_time = self.sleep_time
                tild_job.server.cores = self.tild_cores
                tild_job.server.queue = self.queue
                tild_job.server.run_time = self.tild_run_time
                tild_job.run()
            self._eam_to_dec_jobs_done = True

    def run_phase_3(self):
        self._run_harm_to_eam_tild()
        self._run_eam_to_dec_osc_tild()

    def _inspect_tild_jobs(self, group):
        if group == 'harm_to_eam':
            name = 'harmonic_to_eam_free_energy'
        elif group == 'eam_to_dec':
            name = 'eam_to_decoupled_oscillator_free_energy'
        else:
            name = None
        pr_tild = self.project.create_group(name)
        tild_jobs = []
        for temp in self.temperatures:
            pr_temp = pr_tild.create_group(str(temp).replace(".", "_"))
            tild_jobs.append(pr_temp.inspect("tild_job"))
        return tild_jobs

    @staticmethod
    def _get_tild_output(job):
        tild_fe = uarray(job['output/tild_free_energy_mean'][-1], job['output/tild_free_energy_se'][-1])
        fep_fe = uarray(job['output/fep_free_energy_mean'][-1], job['output/fep_free_energy_se'][-1])
        return tild_fe, fep_fe

    def _get_quantum_harmonic_free_energy(self, temperature, spring_constant):
        temperature = np.clip(temperature, 1e-6, np.inf)
        beta = 1. / (KB * temperature)
        masses = self.initial_structure.get_masses()
        hbar_omega = HBAR * np.sqrt(spring_constant / masses[0]) * ROOT_EV_PER_ANGSTROM_SQUARE_PER_AMU_IN_S
        return (3. / 2) * hbar_omega + ((3. / beta) * np.log(1 - np.exp(-beta * hbar_omega)))

    def process_phase_3(self):
        self._harm_to_eam_jobs = self._inspect_tild_jobs(group='harm_to_eam')
        self._eam_to_dec_jobs = self._inspect_tild_jobs(group='eam_to_dec')
        self.output.del_qh_to_eam_tild = []
        self.output.del_qh_to_eam_fep = []
        self.output.del_eam_to_dec_tild = []
        self.output.del_eam_to_dec_fep = []
        A_form_tild = []
        A_form_fep = []
        for i, temp in enumerate(self.temperatures):
            h_tild_fe, h_fep_fe = self._get_tild_output(self._harm_to_eam_jobs[i])
            d_tild_fe, d_fep_fe = self._get_tild_output(self._eam_to_dec_jobs[i])
            self.output.del_qh_to_eam_tild.append(h_tild_fe)
            self.output.del_qh_to_eam_fep.append(h_fep_fe)
            self.output.del_eam_to_dec_tild.append(d_tild_fe)
            self.output.del_eam_to_dec_fep.append(d_fep_fe)
            n_atoms = self.initial_structure.get_number_of_atoms()
            osc_fe = self._get_quantum_harmonic_free_energy(temp, self.spring_constant)
            A_form_tild.append((self.output.zero_k_energies[i] + self.output.qh_fes[i] + h_tild_fe) / n_atoms +
                               (d_tild_fe - osc_fe))
            A_form_fep.append((self.output.zero_k_energies[i] + self.output.qh_fes[i] + h_fep_fe) / n_atoms +
                              (d_fep_fe - osc_fe))
        self.output.A_form_tild = np.array(A_form_tild)
        self.output.A_form_fep = np.array(A_form_fep)
        G_form_tild = self.output.A_form_tild + self.output.del_A_form_to_G_form
        G_form_fep = self.output.A_form_fep + self.output.del_A_form_to_G_form
        self.output.G_form_tild = nominal_values(G_form_tild)
        self.output.G_form_tild_se = std_devs(G_form_tild)
        self.output.G_form_fep = nominal_values(G_form_fep)
        self.output.G_form_fep_se = std_devs(G_form_fep)
