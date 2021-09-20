# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import numpy as np
from scipy.integrate import cumtrapz


class Murnaghan:
    """
    Returns a Murnaghan type potential, which is obtained by applying a hydrostatic strain on the input cell.
        The output is the lattice constant as a function of the applied strain and the corresponding potential energy
        per atom.

    A strain_(hi or low) value of 0 corresponds to 0 strain on the structure.
    """
    def __init__(self, project, structure, potential, strain_low=-0.12, strain_hi=1.3, samples=100):
        self.project = project
        self.structure = structure
        self.potential = potential
        self.strain_low = strain_low
        self.strain_hi = strain_hi
        self.samples = samples

    def __call__(self):
        pr = self.project.create_group("murnaghan_potential")
        strains = np.linspace(self.strain_low, self.strain_hi, self.samples)
        job = pr.create.job.Lammps("pot_job", delete_existing_job=True)
        job.structure = self.structure.copy()
        job.potential = self.potential
        job.interactive_open()
        job.interactive_initialize_interface()
        energy_pot = []
        a = []
        for strain in strains:
            new_struct = self.structure.copy().apply_strain(strain, return_box=True)
            a.append(new_struct.get_symmetry_dataset()['std_lattice'][0][0])
            job.interactive_structure_setter(new_struct)
            job._interactive_lib_command(job._interactive_run_command)
            energy_pot.append(job.interactive_energy_pot_getter() / len(self.structure))
        job.finished = True
        return np.array(a), np.array(energy_pot)


class Glensk:
    """
    Runs a Glensk-type potential. Atom 1 is displaced along an input direction and the corresponding force on atom 0
        is obtained. The Glensk potential is the integral of this force along the input direction.

    A disp_(hi or low) value of 0 corresponds to 0 displacement of atom 1.
    """
    def __init__(self, project, structure, potential, disp_low=-0.12, disp_hi=2., samples=100,
                 direction=np.array([0., 1 / np.sqrt(2), 1 / np.sqrt(2)]), tag="long"):
        self.project = project
        self.structure = structure
        self.potential = potential
        self.disp_low = disp_low
        self.disp_hi = disp_hi
        self.samples = samples
        self.direction = direction
        self.tag = tag

    def displace_atom(self, positions_of_the_atom):
        """
        Displace ´positions_of_the_atom´ along the input direction.
        """
        pos_low = positions_of_the_atom.copy() + (self.direction * (self.disp_low - 1))
        pos_hi = positions_of_the_atom.copy() + (self.direction * self.disp_hi)
        return np.linspace(pos_low, pos_hi, self.samples)

    def __call__(self):
        pr = self.project.create_group("glensk_potential")
        job = pr.create.job.Lammps("glensk_" + self.tag + "_potential", delete_existing_job=True)
        job.structure = self.structure.copy()
        job.potential = self.potential
        job.interactive_open()
        job.interactive_initialize_interface()
        positions_of_atom_1 = self.displace_atom(positions_of_the_atom=self.structure.positions[1])
        force_on_atom_0 = []
        energy_pot_0 = []
        for pos in positions_of_atom_1:  # move 1st atom
            new_pos = job.structure.positions.copy()
            new_pos[1] = pos
            job.interactive_positions_setter(new_pos)
            job._interactive_lib_command(job._interactive_run_command)
            force_on_atom_0.append(job.interactive_forces_getter()[0])
            energy_pot_0.append(job.interactive_energy_pot_getter()[0])
        job.status.finished = True
        force_on_atom_0 = np.array(force_on_atom_0)
        force_on_atom_0 -= force_on_atom_0[np.argmin(np.linalg.norm(force_on_atom_0, axis=1))]
        force_along_direction = np.dot(force_on_atom_0, np.array(self.direction))
        nn_dists = np.dot(positions_of_atom_1, np.array(self.direction))
        energy_pot = cumtrapz(y=force_along_direction, x=nn_dists)
        nn_dists = nn_dists[1:]
        return nn_dists, energy_pot
