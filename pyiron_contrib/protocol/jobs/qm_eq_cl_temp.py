# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from pyiron_base.master.generic import GenericJob
from pyiron_base.generic.datacontainer import DataContainer
import numpy as np
from scipy.constants import physical_constants
from scipy.integrate import cumtrapz
from scipy.sparse.linalg import eigsh, LinearOperator

from shutil import rmtree

import matplotlib.pyplot as plt

# unit conversions
EV_TO_HARTREE = physical_constants['electron volt-hartree relationship'][0]
ANG_TO_BOHR = 1e-10 / physical_constants['Bohr radius'][0]
KB_HARTREE_PER_KELVIN = physical_constants['Boltzmann constant in eV/K'][0] * EV_TO_HARTREE
AMU_TO_ELECTRON_MASS = 1 / physical_constants['electron relative atomic mass'][0]


class Schroedinger_1D:
    def __init__(self, x, pot, n_states=10, mass=26.98):
        self.x = x
        self.dx = np.diff(x)[0]
        self.pot = pot
        self.n_states = n_states
        self.mass = mass
        self.eigenvectors = []
        self.eigenvalues = []

    def laplace(self, psi):
        return (np.roll(psi, 1) + np.roll(psi, -1) - 2 * psi) / self.dx ** 2

    def ham_psi(self, psi):
        # the units are in Hartree atomic units. In this unit system, the mass of an electron (m_e) is 1.
        # since we want to solve the equation for an atom, we need to convert the mass of this atom to
        # electron mass.
        return -0.5 / (self.mass * AMU_TO_ELECTRON_MASS) * self.laplace(psi) + self.pot * psi

    def solve(self):
        # Now we are about to use the LinearOperator function which needs two major arguments.
        # The first argument is a tuple with generates the shape of a matrix, and the second
        # is the FUNCTION which returns a flattened vector (in this case self.ham_psi). Notice
        # how the second input argument to this function is another function.
        A = LinearOperator((len(self.x), len(self.x)), self.ham_psi)
        ew, ev = eigsh(A, which='SA', k=self.n_states)
        self.eigenvectors = ev.T
        self.eigenvalues = ew
        return self.eigenvalues, self.eigenvectors

    def plot(self):
        plt.plot(self.x, self.pot, 'k')
        if not len(self.eigenvalues):
            print("WARNING: Only showing the potential. Please run self.solve() to populate eigenvectors/values.")
        for i in range(len(self.eigenvalues)):
            plt.plot(self.x, self.eigenvectors[i] + self.eigenvalues[i])
            plt.plot(self.x, self.eigenvectors[i] * 0 + self.eigenvalues[i], 'k--')
        plt.show()


class QuantumToClassicalTemperature(GenericJob):

    def __init__(self, project, job_name):
        super(QuantumToClassicalTemperature, self).__init__(project, job_name)
        self.__version__ = "0.0.1"
        self.__name__ = "QunatumToClassicalTemperature"
        self._python_only_job = True
        self.input = DataContainer(table_name="job_input")
        self.output = DataContainer(table_name="job_output")
        # general inputs
        self.input.temperatures = None
        self.input.structure = None
        self.input.potential = None
        self.input.potential_type = "murnaghan"
        # potential generation
        self.input.potential_samples = 201
        self.input.strain_low = -0.2
        self.input.strain_high = 1.7
        self.input.displacement_low = 0.8
        self.input.displacement_high = 1.25
        self.input.displacement_axis = [0., 2.025, 2.025]
        # internal
        self._atomic_mass = None
        self._n_atoms = None
        self.pd_classical_all = None
        self.pd_quantum_all = None

    def validate_ready_to_run(self):
        self._atomic_mass = self.input.structure.get_masses()[0]
        self._n_atoms = self.input.structure.get_number_of_atoms()

    @staticmethod
    def create_diatom(structure):
        new_struct = structure.copy()
        for _ in np.arange(len(structure) - 2):  # leave 2 atoms
            new_struct.pop(2)
        new_struct.pbc = [False, False, False]
        return new_struct

    def generate_diatom_potential(self):
        pr = self.project.create_group(self.job_name)
        self.output.diatom_structure = self.create_diatom(self.input.structure)
        base_pos = self.output.diatom_structure.positions.copy()
        displacements = np.linspace(self.input.displacement_low, self.input.displacement_high,
                                    self.input.potential_samples)
        pos_atom_1 = np.array([base_pos[1] * disp for disp in displacements])
        pot_job = pr.create.job.Lammps('pot_job')
        pot_job.structure = self.output.diatom_structure.copy()
        pot_job.potential = self.input.potential
        pot_job.interactive_open()
        pot_job.interactive_initialize_interface()
        energy_pot = []
        for p in pos_atom_1:
            new_pos = base_pos.copy()
            new_pos[1] = p
            pot_job.interactive_positions_setter(new_pos)
            pot_job._interactive_lib_command(pot_job._interactive_run_command)
            energy_pot.append(pot_job.interactive_energy_pot_getter())
        self.status.finished = True
        self.output.nn_dist_ang = np.linalg.norm(pos_atom_1, axis=1)
        self.output.potential_ev = np.array(energy_pot).flatten()
        self.output.potential_ev -= self.output.potential_ev.min()

    def generate_murnaghan_potential(self):
        pr = self.project.create_group(self.job_name)
        strains = np.linspace(self.input.strain_low, self.input.strain_high, self.input.potential_samples)
        pot_job = pr.create.job.Lammps('pot_job')
        pot_job.structure = self.input.structure.copy()
        pot_job.potential = self.input.potential
        pot_job.interactive_open()
        pot_job.interactive_initialize_interface()
        energy_pot = []
        nn_dist = []
        for strain in strains:
            new_struct = self.input.structure.copy().apply_strain(strain, return_box=True)
            nn_dist.append(np.linalg.norm(new_struct.positions[1]))
            pot_job.interactive_structure_setter(new_struct)
            pot_job._interactive_lib_command(pot_job._interactive_run_command)
            energy_pot.append(pot_job.interactive_energy_pot_getter() / self._n_atoms)
        self.status.finished = True
        self.output.nn_dist_ang = np.array(nn_dist).flatten()
        self.output.potential_ev = np.array(energy_pot).flatten()
        self.output.potential_ev -= self.output.potential_ev.min()

    def generate_glensk_potential(self):
        pr = self.project.create_group(self.job_name)
        base_pos = self.input.structure.positions.copy()
        displacements = np.linspace(self.input.displacement_low, self.input.displacement_high,
                                    self.input.potential_samples)
        pos_atom_1 = np.array([base_pos[1] * disp for disp in displacements])
        pot_job = pr.create.job.Lammps('pot_job')
        pot_job.structure = self.input.structure.copy()
        pot_job.potential = self.input.potential
        pot_job.interactive_open()
        pot_job.interactive_initialize_interface()
        force_atom_0 = []
        for p in pos_atom_1:
            new_pos = base_pos.copy()
            new_pos[1] = p
            pot_job.interactive_positions_setter(new_pos)
            pot_job._interactive_lib_command(pot_job._interactive_run_command)
            force_atom_0.append(pot_job.interactive_forces_getter()[0])
        self.status.finished = True
        force_atom_0 = np.array(force_atom_0)
        force_along_011 = np.dot(force_atom_0, np.array(self.input.displacement_axis))
        self.output.nn_dist_ang = np.linalg.norm(pos_atom_1, axis=1)
        self.output.potential_ev = cumtrapz(force_along_011, x=self.output.nn_dist_ang)
        self.output.potential_ev -= self.output.potential_ev.min()
        self.output.nn_dist_ang = self.output.nn_dist_ang[1:]

    @staticmethod
    def convert_pyiron_to_atomic_units(distance=None, energy=None):
        if (distance is not None) and (energy is None):
            return distance * ANG_TO_BOHR
        elif (energy is not None) and (distance is None):
            return energy * EV_TO_HARTREE
        elif (distance is not None) and (energy is not None):
            return distance * ANG_TO_BOHR, energy * EV_TO_HARTREE

    @staticmethod
    def convert_atomic_to_pyiron_units(distance=None, energy=None):
        if (distance is not None) and (energy is None):
            return distance / ANG_TO_BOHR
        elif (energy is not None) and (distance is None):
            return energy / EV_TO_HARTREE
        elif (distance is not None) and (energy is not None):
            return distance / ANG_TO_BOHR, energy / EV_TO_HARTREE

    def get_classical_pd(self):
        self.output.nn_dist_bohr, self.output.potential_H = self.convert_pyiron_to_atomic_units(self.output.nn_dist_ang,
                                                                                                self.output.potential_ev)
        self.output.pd_classical_all = []
        for temp in self.input.temperatures:
            pd_boltz = np.exp(-(self.output.potential_H - self.output.potential_H.min()) /
                              (KB_HARTREE_PER_KELVIN * temp))
            self.output.pd_classical_all.append(pd_boltz / pd_boltz.sum())
        self.output.pd_classical_all = np.array(self.output.pd_classical_all)

    def solve_TISD(self):
        if self.input.potential_style == "glensk":
            n_states = self.input.potential_samples - 2
        else:
            n_states = self.input.potential_samples - 1
        ham = Schroedinger_1D(x=self.output.nn_dist_bohr, pot=self.output.potential_H,
                              n_states=n_states, mass=self._atomic_mass)
        self.output.eigenvalues, self.output.eigenvectors = ham.solve()

    @staticmethod
    def _get_boltzmann_weighted_pd(eigenvalues, eigenvectors, potential, temperature):
        # truncate the eigens to that the eigenvalues are not greater than the maxima of the tail end of the potential
        trunc_eigenvalues = eigenvalues[eigenvalues <= potential[-1]]
        trunc_eigenvectors = eigenvectors[eigenvalues <= potential[-1]]
        # get the occupation probability of each state - Boltzmann weighting
        boltzmann = np.exp(-(eigenvalues - potential.min()) / (KB_HARTREE_PER_KELVIN * temperature))
        boltzmann_weight = boltzmann / np.sum(boltzmann)  # !partition function!
        # get the weighted probability density
        weight_pd = np.sum(boltzmann_weight[:, np.newaxis] * eigenvectors ** 2,
                           axis=0)  # probability density, which is square of the wavefunction
        # also return just the ground state for comparison
        ground_pd = eigenvectors[0] ** 2
        return weight_pd, ground_pd, boltzmann_weight

    def get_quantum_pd(self):
        self.output.pd_quantum_all = []
        for temp in self.input.temperatures:
            pd, _, _ = self._get_boltzmann_weighted_pd(self.output.eigenvalues, self.output.eigenvectors,
                                                       self.output.potential_H, temp)
            self.output.pd_quantum_all.append(pd)
        self.output.pd_quantum_all = np.array(self.output.pd_quantum_all)

    def get_expectations(self):
        self.output.energy_classical_H = np.sum(self.output.pd_classical_all * self.output.potential_H, axis=1)
        self.output.energy_quantum_H = np.sum(self.output.pd_quantum_all * self.output.potential_H, axis=1)
        self.output.energy_classical_ev = self.convert_atomic_to_pyiron_units(energy=self.output.energy_classical_H)
        self.output.energy_quantum_ev = self.convert_atomic_to_pyiron_units(energy=self.output.energy_quantum_H)

    @staticmethod
    def get_Tc(E_q, temperatures, expec_E_c):
        return temperatures[expec_E_c.searchsorted(E_q, 'left')]

    def get_equivalent_classical_temperature(self):
        fit_eqn = np.poly1d(np.polyfit(self.input.temperatures, self.output.energy_classical_ev, 4))
        fine_temperatures = np.linspace(self.input.temperatures[0], self.input.temperatures[-1] + 1000,
                                        100000, endpoint=True)
        fine_expec_E_c = fit_eqn(fine_temperatures)
        self.output.equivalent_classical_temperatures = self.get_Tc(self.output.energy_quantum_ev, fine_temperatures,
                                                                    fine_expec_E_c)

    def run_static(self):
        if self.input.potential_style == "diatom":
            self.generate_diatom_potential()
        elif self.input.potential_style == "murnaghan":
            self.generate_murnaghan_potential()
        elif self.input.potential_style == "glensk":
            self.generate_glensk_potential()
        self.get_classical_pd()
        self.solve_TISD()
        self.get_quantum_pd()
        self.get_expectations()
        self.get_equivalent_classical_temperature()
        self.to_hdf(self.project_hdf5)

    def to_hdf(self, hdf=None, group_name=None):
        """
        Store the FreeEnergy object in the HDF5 File.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        super(QuantumToClassicalTemperature, self).to_hdf(hdf=hdf, group_name=group_name)
        # self.input.to_hdf(self.project_hdf5)
        self.output.to_hdf(self.project_hdf5)

    def from_hdf(self, hdf=None, group_name=None):
        """
        Restore the FreeEnergy object from the HDF5 File.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        super(QuantumToClassicalTemperature, self).from_hdf(hdf=hdf, group_name=group_name)
        self.input.from_hdf(self.project_hdf5)
        self.output.from_hdf(self.project_hdf5)



