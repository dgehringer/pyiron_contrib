# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function
from pyiron_contrib.protocol.graph import Graph
from pyiron_contrib.protocol.vertices import BinarySwitch, Counter
from pyiron_contrib.protocol.atomistic.vertices import ExternalHamiltonian, GradientDescent

"""
Protocol for minimizing atomic forces.
"""

__author__ = "Liam Huber, Dominik Gehringer, Jan Janssen"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "Feb 15, 2020"


class Minimize(Graph):
    """
    Run minimization with Lammps. This isn't physically useful, since a regular lammps job is faster it's just a dummy
    class for debugging new code and teaching ideas.

    Input channels:
        ref_job_full_path (str): Path to the pyiron job to use for evaluating forces and energies.
        structure (Atoms): The structure to minimize.
        n_steps (int): How many steps to run for. (Default is 100.)
        f_tol (float): Ionic force convergence (largest atomic force). (Default is 1e-4 eV/angstrom.)
        gamma0 (float): Initial step size as a multiple of the force. (Default is 0.1.)
        fix_com (bool): Whether the center of mass motion should be subtracted off of the position update. (Default is
            True)
        use_adagrad (bool): Whether to have the step size decay according to adagrad. (Default is False)

    Output channels:
        energy_pot (float): Total potential energy of the system in eV.
        max_force (float): The largest atomic force magnitude in eV/angstrom.
        positions (numpy.ndarray): Atomic positions in angstroms.
        forces (numpy.ndarray): Atomic forces in eV/angstrom.
    """

    def init_io_channels(self):
        ichan = self.input.add_channel
        ichan('ref_job_full_path')
        ichan('structure')
        ichan('n_steps', 100)
        ichan('f_tol', 1e-4)
        ichan('gamma0', 0.1)
        ichan('fix_com', True)
        ichan('use_adagrad', False)

        ochan = self.output.add_channel
        ochan('energy_pot')
        ochan('max_force')
        ochan('positions')
        ochan('forces')

    def set_vertices(self):
        v = self.vertices
        v.calc_static = ExternalHamiltonian()
        v.clock = Counter()
        v.check_steps = BinarySwitch()
        v.check_force = BinarySwitch()
        v.gradient_descent = GradientDescent()

    def set_edges(self):
        v = self.vertices
        self.edges.set_flow_chain(
            v.check_steps, 'false',
            v.check_force, 'false',
            v.calc_static,
            v.gradient_descent,
            v.clock,
            v.check_steps
        )
        self.starting_vertex = v.check_steps
        self.restarting_vertex = v.check_steps

    def wire_data_flow(self):
        v = self.vertices
        i = self.input

        v.calc_static.input.ref_job_full_path += i.ref_job_full_path
        v.calc_static.input.structure += i.structure
        v.calc_static.input.positions += i.structure.positions
        v.calc_static.input.positions += v.gradient_descent.output.positions[-1]

        v.check_steps.input.state += False
        v.check_steps.input.state += v.clock.output.n_counts[-1] >= i.n_steps

        v.check_force.input.state += False
        v.check_force.input.state += v.calc_static.output.forces[-1].norm(axis=-1).max() < i.f_tol

        v.gradient_descent.input.positions += i.structure.positions
        v.gradient_descent.input.positions += v.gradient_descent.output.positions[-1]
        v.gradient_descent.input.forces += v.calc_static.output.forces[-1]
        v.gradient_descent.input.gamma0 += i.gamma0
        v.gradient_descent.input.fix_com += i.fix_com
        v.gradient_descent.input.masses += i.structure.get_masses()
        v.gradient_descent.input.use_adagrad += i.use_adagrad

        self.set_clock_for_all_vertices(v.clock.output.n_counts[-1])

    def get_output(self):
        v = self.vertices
        return {
            'energy_pot': ~v.calc_static.output.energy_pot[-1],
            'max_force': ~v.calc_static.forces[-1].norm(axis=-1).max(),
            'positions': ~v.gradient_descent.output.positions[-1],
            'forces': ~v.calc_static.output.forces[-1]
        }
