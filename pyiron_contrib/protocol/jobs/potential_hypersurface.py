# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import numpy as np
from scipy.integrate import cumtrapz

from pyiron_base.master.generic import GenericJob
from pyiron_base.generic.datacontainer import DataContainer

class _ParentPotential(GenericJob):

    def __init__(self, project, job_name):
        super(_ParentPotential, self).__init__(project, job_name)
        self.input = DataContainer(table_name="job_input")
        self.output = DataContainer(table_name="job_output")

    def to_hdf(self, hdf=None, group_name=None):
        """
        Store the object in the HDF5 File.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        super(_ParentPotential, self).to_hdf(hdf=hdf, group_name=group_name)
        self.input.to_hdf(self.project_hdf5)
        self.output.to_hdf(self.project_hdf5)

    def from_hdf(self, hdf=None, group_name=None):
        """
        Restore the object from the HDF5 File.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        super(_ParentPotential, self).from_hdf(hdf=hdf, group_name=group_name)
        self.input.from_hdf(self.project_hdf5)
        self.output.from_hdf(self.project_hdf5)

class MurnaghanPotential(_ParentPotential):
    """
    Returns a Murnaghan type potential hypersurface, which is obtained by applying a hydrostatic strain on the input
        structure and measuring the potential energy per atom.

    Input attributes:
        structure (Atoms): The structure for evaluation.
        potential (str): The potential file string.
        strain_low (float): Lower bound of the strain to be applied to the structure. A value of 0. corresponds to
            no strain.
        strain_high (float): Upper bound of the strain to be applied to the structure. A value of 0. corresponds to
            no strain.
        samples (int): Number of potential energy data points required for the output.

    Output attributes:
        energy_pot (numpy.array): The potential hypersurface
        lattice_constant_a (numpy.array): The corresponding lattice constant value.
    """

    def __init__(self, project, job_name):
        super(MurnaghanPotential, self).__init__(project, job_name)
        self.__version__ = "0.0.1"
        self.__name__ = "MurnaghanPotential"
        self._python_only_job = True
        # general inputs
        self.input.structure = None
        self.input.potential = None
        self.input.strain_low = -0.12
        self.input.strain_high = 1.3
        self.input.samples = 100

    def run_static(self):
        pr = self.project.create_group("murnaghan_potential")
        strains = np.linspace(self.input.strain_low, self.input.strain_high, self.input.samples)
        job = pr.create.job.Lammps("pot_job", delete_existing_job=True)
        job.structure = self.input.structure.copy()
        job.potential = self.input.potential
        job.interactive_open()
        job.interactive_initialize_interface()
        self.output.energy_pot = []
        self.output.lattice_constant_a = []
        for strain in strains:
            new_struct = self.input.structure.copy().apply_strain(strain, return_box=True)
            self.output.lattice_constant_a.append(new_struct.get_symmetry_dataset()['std_lattice'][0][0])
            job.interactive_structure_setter(new_struct)
            job._interactive_lib_command(job._interactive_run_command)
            self.output.energy_pot.append(job.interactive_energy_pot_getter() / len(self.input.structure))
        job.finished = True
        self.output.energy_pot = np.array(self.output.energy_pot)
        self.output.lattice_constant_a = np.array(self.output.lattice_constant_a)
        self.to_hdf()

# class Glensk:
#     """
#     Runs a Glensk-type potential. Atom 1 is displaced along an input direction and the corresponding force on atom 0
#         is obtained. The Glensk potential is the integral of this force along the input direction.
#
#     A disp_(hi or low) value of 0 corresponds to 0 displacement of atom 1.
#     """
#     def __init__(self, project, structure, potential, disp_low=-0.12, disp_hi=2., samples=100,
#                  direction=np.array([0., 1 / np.sqrt(2), 1 / np.sqrt(2)]), tag="long"):
#         self.project = project
#         self.structure = structure
#         self.potential = potential
#         self.disp_low = disp_low
#         self.disp_hi = disp_hi
#         self.samples = samples
#         self.direction = direction
#         self.tag = tag
#
#     def displace_atom(self, positions_of_the_atom):
#         """
#         Displace ´positions_of_the_atom´ along the input direction.
#         """
#         pos_low = positions_of_the_atom.copy() + (self.direction * (self.disp_low - 1))
#         pos_hi = positions_of_the_atom.copy() + (self.direction * self.disp_hi)
#         return np.linspace(pos_low, pos_hi, self.samples)
#
#     def __call__(self):
#         pr = self.project.create_group("glensk_potential")
#         job = pr.create.job.Lammps("glensk_" + self.tag + "_potential", delete_existing_job=True)
#         job.structure = self.structure.copy()
#         job.potential = self.potential
#         job.interactive_open()
#         job.interactive_initialize_interface()
#         positions_of_atom_1 = self.displace_atom(positions_of_the_atom=self.structure.positions[1])
#         force_on_atom_0 = []
#         energy_pot_0 = []
#         for pos in positions_of_atom_1:  # move 1st atom
#             new_pos = job.structure.positions.copy()
#             new_pos[1] = pos
#             job.interactive_positions_setter(new_pos)
#             job._interactive_lib_command(job._interactive_run_command)
#             force_on_atom_0.append(job.interactive_forces_getter()[0])
#             energy_pot_0.append(job.interactive_energy_pot_getter()[0])
#         job.status.finished = True
#         force_on_atom_0 = np.array(force_on_atom_0)
#         force_on_atom_0 -= force_on_atom_0[np.argmin(np.linalg.norm(force_on_atom_0, axis=1))]
#         force_along_direction = np.dot(force_on_atom_0, np.array(self.direction))
#         nn_dists = np.dot(positions_of_atom_1, np.array(self.direction))
#         energy_pot = cumtrapz(y=force_along_direction, x=nn_dists)
#         nn_dists = nn_dists[1:]
#         return nn_dists, energy_pot
