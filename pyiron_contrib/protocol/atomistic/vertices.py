# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function
from pyiron_contrib.protocol.graph import Vertex
import numpy as np
from pyiron import Project
from pyiron.atomistics.job.interactive import GenericInteractive
from pyiron.lammps.lammps import LammpsInteractive
from os.path import split

"""
Vertices designed for atomistic simulations.
"""

__author__ = "Liam Huber, Dominik Gehringer, Raynol Dsouza"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "Feb 15, 2020"


class ExternalHamiltonian(Vertex):
    """
    Manages calls to an external interpreter (e.g. Lammps, Vasp, Sphinx...) to produce energies, forces, and possibly
    other properties.

    The collected output can be expanded beyond forces and energies (e.g. to magnetic properties or whatever else the
    interpreting code produces) by modifying the `interesting_keys` in the input. The property must have a corresponding
    interactive getter for this property.

    Input channels:
        ref_job_full_path (string): The full path to the hdf5 file of the job to use as a reference template.
        structure (Atoms): The structure for initializing the external Hamiltonian. Overwrites the reference job
            structure when provided. (Default is None, the reference job needs to have its structure set.)
        interesting_keys (list[str]): String codes for output properties of the underlying job to collect. (Default is
            ['forces', 'energy_pot'].)
        positions (numpy.ndarray): New positions to evaluate. Shape must match the shape of the structure. (Not set by
            default, only necessary if positions are being updated.)

    Output channels:

    """

    def __init__(self, vertex_name=None):
        super(ExternalHamiltonian, self).__init__(vertex_name=vertex_name)
        self._fast_lammps_mode = True  # Set to false only to intentionally be slow for comparison purposes
        self._job = None
        self._job_project_path = None
        self._job_name = None

    def init_io_channels(self):
        ichan = self.input.add_channel
        ichan('ref_job_full_path')
        ichan('structure')
        ichan('interesting_keys', ['forces', 'energy_pot'])
        ichan('positions', None)

        # TODO: More careful handling of interesting keys and output channels. Right now ONLY forces and energy_pot work
        ochan = self.output.add_channel
        ochan('forces')
        ochan('energy_pot')

    def function(self, ref_job_full_path, structure, interesting_keys, positions):
        if self._job_project_path is None:
            self._initialize(ref_job_full_path, structure)
        elif self._job is None:
            self._reload()
        elif not self._job.interactive_is_activated():
            self._job.status.running = True
            self._job.interactive_open()
            self._job.interactive_initialize_interface()

        if isinstance(self._job, LammpsInteractive) and self._fast_lammps_mode:
            # Run Lammps 'efficiently'
            if positions is not None:
                self._job.interactive_positions_setter(positions)

            self._job._interactive_lib_command(self._job._interactive_run_command)
        elif isinstance(self._job, GenericInteractive):
            # DFT codes are slow enough that we can run them the regular way and not care
            # Also we might intentionally run Lammps slowly for comparison purposes
            if positions is not None:
                self._job.structure.positions = positions

            self._job.calc_static()
            self._job.run()
        else:
            raise TypeError('Job of class {} is not compatible.'.format(self._job.__class__))

        return {key: self.get_interactive_value(key) for key in interesting_keys}

    def _initialize(self, ref_job_full_path, structure):
        loc = self.get_graph_location()
        name = loc + '_job'
        project_path, ref_job_path = split(ref_job_full_path)
        pr = Project(path=project_path)
        ref_job = pr.load(ref_job_path)
        job = ref_job.copy_to(
            project=pr,
            new_job_name=name,
            input_only=True,
            new_database_entry=True
        )

        if structure is not None:
            job.structure = structure

        if isinstance(job, GenericInteractive):
            job.interactive_open()

            if isinstance(job, LammpsInteractive) and self._fast_lammps_mode:
                # Note: This might be done by default at some point in LammpsInteractive, and could then be removed here
                job.interactive_flush_frequency = 10**10
                job.interactive_write_frequency = 10**10
                self._disable_lmp_output = True

            job.calc_static()
            job.run(run_again=True)
            # TODO: Running is fine for Lammps, but wasteful for DFT codes! Get the much cheaper interface
            #  initialization working -- right now it throws a (passive) TypeError due to database issues
        else:
            raise TypeError('Job of class {} is not compatible.'.format(ref_job.__class__))
        self._job = job
        self._job_name = name
        self._job_project_path = project_path

    def _reload(self):
        pr = Project(path=self._job_project_path)
        self._job = pr.load(self._job_name)
        self._job.interactive_open()
        self._job.interactive_initialize_interface()
        self._job.calc_static()
        self._job.run(run_again=True)

    def get_interactive_value(self, key):
        if key == 'positions':
            val = np.array(self._job.interactive_positions_getter())
        elif key == 'forces':
            val = np.array(self._job.interactive_forces_getter())
        elif key == 'energy_pot':
            val = self._job.interactive_energy_pot_getter()
        elif key == 'cells':
            val = np.array(self._job.interactive_cells_getter())
        else:
            raise NotImplementedError
        return val

    def finish(self):
        super(ExternalHamiltonian, self).finish()
        if self._job is not None:
            self._job.interactive_close()

    # def to_hdf(self, hdf=None, group_name=None):
    #     super(ExternalHamiltonian, self).to_hdf(hdf=hdf, group_name=group_name)
    #     hdf[group_name]["fastlammpsmode"] = self._fast_lammps_mode
    #     hdf[group_name]["jobname"] = self._job_name
    #     hdf[group_name]["jobprojectpath"] = self._job_project_path
    #
    # def from_hdf(self, hdf=None, group_name=None):
    #     super(ExternalHamiltonian, self).from_hdf(hdf=hdf, group_name=group_name)
    #     self._fast_lammps_mode = hdf[group_name]["fastlammpsmode"]
    #     self._job_name = hdf[group_name]["jobname"]
    #     self._job_project_path = hdf[group_name]["jobprojectpath"]


class GradientDescent(Vertex):
    """
    Simple gradient descent update for positions in `flex_output` and structure.

    Input channels:
        positions (numpy.ndarray): Per-atom atomic positions.
        forces (numpy.ndarray): Per-atom atomic forces.
        gamma0 (float): Initial step size as a multiple of the force. (Default is 0.1.)
        fix_com (bool): Whether the center of mass motion should be subtracted off of the position update. (Default is
            True)
        masses (numpy.ndarray/list): Per-atom masses to be used if `fix_com` is true. (Default is None.)
        use_adagrad (bool): Whether to have the step size decay according to adagrad. (Default is False.)
        output_displacements (bool): Whether to return the per-atom displacement vector in the output dictionary.
            (Default is False.)

    Output channels:
        positions (numpy.ndarray): New, positions closer to minima.
        displacements (numpy.ndarray): The displacements from this step. Present if `output_displacements` was true.

    TODO:
        Fix adagrad bug when GradientDescent is passed as a Serial vertex
    """
    def __init__(self, vertex_name=None):
        super(GradientDescent, self).__init__(vertex_name=vertex_name)
        self._accumulated_force = 0

    def init_io_channels(self):
        ichan = self.input.add_channel
        ichan('positions')
        ichan('forces')
        ichan('gamma0', 0.1)
        ichan('fix_com', True)
        ichan('masses', None)
        ichan('use_adagrad', False)
        ichan('output_displacements', False)

        ochan = self.output.add_channel
        ochan('positions')
        ochan('displacements')

    def function(self, positions, forces, gamma0, use_adagrad, fix_com, masses, output_displacements):
        positions = np.array(positions)
        forces = np.array(forces)

        if use_adagrad:
            self._accumulated_force += np.sqrt(np.sum(forces * forces))
            gamma0 /= self._accumulated_force

        pos_change = gamma0 * np.array(forces)

        if fix_com:
            masses = np.array(masses)[:, np.newaxis]
            total_mass = np.sum(masses)
            com_change = np.sum(pos_change * masses, axis=0) / total_mass
            pos_change -= com_change
        # TODO: fix angular momentum

        new_pos = positions + pos_change

        output = {'positions': new_pos}
        if output_displacements:
            output['displacements'] = pos_change

        return output

    # def to_hdf(self, hdf=None, group_name=None):
    #     super(GradientDescent, self).to_hdf(hdf=hdf, group_name=group_name)
    #     hdf[group_name]["accumulatedforce"] = self._accumulated_force
    #
    # def from_hdf(self, hdf=None, group_name=None):
    #     super(GradientDescent, self).from_hdf(hdf=hdf, group_name=group_name)
    #     self._accumulated_force = hdf[group_name]["accumulatedforce"]