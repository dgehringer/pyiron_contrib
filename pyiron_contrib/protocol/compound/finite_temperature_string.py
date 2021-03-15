# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from pyiron_contrib.protocol.generic import CompoundVertex, Protocol
from pyiron_contrib.protocol.primitive.one_state import CreateJob, Counter, CutoffDistance, Difference, \
    ExternalHamiltonian, InitialPositions, RandomVelocity, SphereReflection, VerletPositionUpdate, \
    VerletVelocityUpdate, Zeros
from pyiron_contrib.protocol.primitive.two_state import AnyVertex, IsGEq, ModIsZero
from pyiron_contrib.protocol.primitive.fts_vertices import CentroidsRunningAverageMix, CentroidsReparameterization, \
    CentroidsSmoothing, CheckConvergence, PositionsRunningAverage, StringRecenter, StringReflect, MilestonePostProcess
from pyiron_contrib.protocol.list import SerialList, ParallelList
from pyiron_contrib.protocol.utils import Pointer

"""
Protocols for the finite temperature string (FTS) method.
"""

__author__ = "Raynol Dsouza, Liam Huber"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "23 July, 2019"


class FTSEvolution(CompoundVertex):
    """
    A serial Finite Temperature String (FTS) protocol to compute migration barriers between two stable system.

    NOTE: 1. This protocol is as of now untested with DFT-type reference jobs, and only works for sure, with
        Lammps-type reference jobs.
          2. Convergence criterion is NOT implemented for this protocol, because it runs serially, and would take
        a VERY long time to achieve a good convergence.

    Input attributes:
        TODO: add a vertex to check if all the necessary inputs are provided.
        ref_job_full_path (string): The path to the saved reference job to use for calculating forces and energies.
        structure_initial (Atoms): The initial structure.
        structure_initial (Atoms): The final structure.
        temperature (float): Temperature to run at in K.
        n_steps (int): How many MD steps to run for. (Default is 100.)
        temperature_damping_timescale (float): Langevin thermostat timescale in fs. (Default is None, which runs NVE.)
        overheat_fraction (float): The fraction by which to overheat the initial velocities. This can be useful for
            more quickly equilibrating a system whose initial structure is its fully relaxed positions -- in which
            case equipartition of energy tells us that the kinetic energy should be initialized to double the
            desired value. (Default is 2.0, assume energy equipartition is a good idea.)
        time_step (float): MD time step in fs. (Default is 1.)
        sampling_period (int): Account output every `sampling_period' for the TI operations. (Default is 1, account
            for every MD step.
        thermalization_steps (int): Number of steps the system is thermalized for to reach equilibrium. (Default is
            10 steps.)
        n_images (int): Number of centroids / images. (Default is 5.)
        initial_positions (list/np.ndarray): The initial positions of the images (preferably from NEB).
            Default is None)
        cutoff_factor (float): The cutoff is obtained by taking the first nearest neighbor distance and multiplying
            it by the cutoff factor. A default value of 0.4 is chosen, because taking a cutoff factor of ~0.5
            sometimes let certain reflections off the hook, and we do not want that to happen. (Default is 0.4.)
        mixing_fraction (float): How much of the images' running average of position to mix into the centroid positions
            each time the mixer is called. (Default is 0.1.)
        relax_endpoints (bool): Whether or not to relax the endpoints of the string. (Default is False.)
        smooth_style (string): Apply 'global' or 'local' smoothing. 'global' smoothing considers an array of n_images
            terms while applying smoothing to each image, while 'local' smoothing only considers the left and right
            neighbor of that image. (Default is 'global'.)
        nominal_smoothing (float): How much smoothing to apply to the updating centroid positions (endpoints are
            not effected). The actual smoothing is the product of this nominal value, the number of images, and the
            mixing fraction, ala Vanden-Eijnden and Venturoli (2009). (Default is 0.1.)
        use_reflection (boolean): Turn on or off `SphereReflection`. Using sphere reflection restricts each atom
            in the simulation cell to evolve within the Wigner-Seitz cell of its reference position. This is
            helpful to restrict atom-hopping in the presence of a vacancy at higher temperatures. (Default is True.)
        n_energy_samples (int): Number of energy samples of each centroid to calculate the std (Default is 10.)
        tolerance (float): The value of std below which the string is considered to be converged (Default is 0.001.)
        anchor_element (int): The centroid number to use as the reference to compute the barrier (Default is 0.)
        use_minima (bool): Whether to use the minima of the energies to compute the barrier (Default is
            False, use the 0th value.)
        store_reflections (bool): If True, stores the reflections matrices (Default for string evolution is False,
            do not store the reflections matrix)

    Output attributes:
        energy_pot (list[float]): Total potential energy of the system in eV.
        positions (list[numpy.ndarray]): Atomic positions in angstroms for each centroid.
        forces (list[numpy.ndarray]): Atomic forces in eV/angstrom for each centroid.
    """

    def __init__(self, **kwargs):
        super(FTSEvolution, self).__init__(**kwargs)

        # Protocol defaults
        id_ = self.input.default
        id_.temperature = 1.
        id_.n_steps = 100
        id_.temperature_damping_timescale = 100.
        id_.overheat_fraction = 2.
        id_.time_step = 1.
        id_.sampling_period = 1
        id_.thermalization_steps = 10
        id_.n_images = 5
        id_.initial_positions = None
        id_.cutoff_factor = 0.5
        id_.mixing_fraction = 0.1
        id_.relax_endpoints = False
        id_.smooth_style = 'global'
        id_.nominal_smoothing = 0.1
        id_.use_reflection = True
        id_.n_energy_samples = 10
        id_.tolerance = 0.001
        id_.anchor_element = 0
        id_.use_minima = False
        id_.store_reflections = False
        id_._divisor = 1
        id_._total_steps = 0
        id_._project_path = None
        id_._job_name = None
        id_._previous_centroid_positions = None
        id_._image_number = None
        id_._tracker_list = None
        id_._reflections_matrix = None
        id_._edge_reflections_matrix = None
        id_._edge_time_matrix = None

    def define_vertices(self):
        # Graph components
        g = self.graph
        g.initialize_images = CreateJob()
        g.initialize_centroids = CreateJob()
        g.initial_positions = InitialPositions()
        g.initial_velocities = SerialList(RandomVelocity)
        g.initial_forces = Zeros()
        g.cutoff = CutoffDistance()
        g.check_steps = IsGEq()
        g.verlet_positions = SerialList(VerletPositionUpdate)
        g.reflect_string = SerialList(StringReflect)
        g.reflect_atoms = SerialList(SphereReflection)
        g.calc_static_images = SerialList(ExternalHamiltonian)
        g.verlet_velocities = SerialList(VerletVelocityUpdate)
        g.running_average_pos = SerialList(PositionsRunningAverage)
        g.check_sampling_period = ModIsZero()
        g.mix = CentroidsRunningAverageMix()
        g.smooth = CentroidsSmoothing()
        g.reparameterize = CentroidsReparameterization()
        g.calc_static_centroids = SerialList(ExternalHamiltonian)
        g.recenter = SerialList(StringRecenter)
        g.clock = Counter()

    def define_execution_flow(self):
        # Execution flow
        g = self.graph
        g.make_pipeline(
            g.initialize_images,
            g.initialize_centroids,
            g.initial_positions,
            g.initial_velocities,
            g.initial_forces,
            g.cutoff,
            g.check_steps, 'false',
            g.verlet_positions,
            g.reflect_string,  # Comes before atomic reflecting so we can actually trigger a full string reflection!
            g.reflect_atoms,  # Comes after, since even if the string doesn't reflect, an atom might have migrated.
            g.calc_static_images,
            g.verlet_velocities,
            g.running_average_pos,
            g.check_sampling_period, 'true',
            g.mix,
            g.smooth,
            g.reparameterize,
            g.calc_static_centroids,
            g.recenter,
            g.clock,
            g.check_steps
        )
        g.make_edge(g.check_sampling_period, g.recenter, 'false')
        g.starting_vertex = g.initialize_images
        g.restarting_vertex = g.check_steps

    def define_information_flow(self):
        # Data flow
        g = self.graph
        gp = Pointer(self.graph)
        ip = Pointer(self.input)

        # initialize_images
        g.initialize_images.input.n_images = ip.n_images
        g.initialize_images.input.ref_job_full_path = ip.ref_job_full_path
        g.initialize_images.input.structure = ip.structure_initial

        # initialize_centroids
        g.initialize_centroids.input.n_images = ip.n_images
        g.initialize_centroids.input.ref_job_full_path = ip.ref_job_full_path
        g.initialize_centroids.input.structure = ip.structure_initial

        # initial_positions
        g.initial_positions.input.structure_initial = ip.structure_initial
        g.initial_positions.input.structure_final = ip.structure_final
        g.initial_positions.input.initial_positions = ip.initial_positions
        g.initial_positions.input.n_images = ip.n_images

        # initial_velocities
        g.initial_velocities.input.n_children = ip.n_images
        g.initial_velocities.direct.temperature = ip.temperature
        g.initial_velocities.direct.masses = ip.structure_initial.get_masses
        g.initial_velocities.direct.overheat_fraction = ip.overheat_fraction

        # cutoff
        g.cutoff.input.structure = ip.structure_initial
        g.cutoff.input.cutoff_factor = ip.cutoff_factor

        # initial_forces
        g.initial_forces.input.shape = ip.structure_initial.positions.shape

        # check_steps
        g.check_steps.input.target = gp.clock.output.n_counts[-1]
        g.check_steps.input.threshold = ip.n_steps

        # verlet_positions
        g.verlet_positions.input.n_children = ip.n_images
        g.verlet_positions.broadcast.default.positions = gp.initial_positions.output.initial_positions[-1]
        g.verlet_positions.broadcast.default.velocities = gp.initial_velocities.output.velocities[-1]
        g.verlet_positions.direct.default.forces = gp.initial_forces.output.zeros[-1]

        g.verlet_positions.broadcast.positions = gp.recenter.output.positions[-1]
        g.verlet_positions.broadcast.velocities = gp.verlet_velocities.output.velocities[-1]
        g.verlet_positions.broadcast.forces = gp.recenter.output.forces[-1]
        g.verlet_positions.direct.masses = ip.structure_initial.get_masses
        g.verlet_positions.direct.time_step = ip.time_step
        g.verlet_positions.direct.temperature = ip.temperature
        g.verlet_positions.direct.temperature_damping_timescale = ip.temperature_damping_timescale

        # reflect_string
        g.reflect_string.input.n_children = ip.n_images
        g.reflect_string.direct.default.all_centroid_positions = \
            gp.initial_positions.output.initial_positions[-1]
        g.reflect_string.broadcast.default.centroid_positions = \
            gp.initial_positions.output.initial_positions[-1]
        g.reflect_string.broadcast.default.previous_positions = \
            gp.initial_positions.output.initial_positions[-1]
        g.reflect_string.broadcast.default.previous_velocities = gp.initial_velocities.output.velocities[-1]

        g.reflect_string.direct.all_centroid_positions = gp.reparameterize.output.all_centroids_positions[-1]
        g.reflect_string.broadcast.centroid_positions = gp.reparameterize.output.all_centroids_positions[-1]
        g.reflect_string.broadcast.previous_positions = gp.recenter.output.positions[-1]
        g.reflect_string.broadcast.previous_velocities = gp.reflect_atoms.output.velocities[-1]
        g.reflect_string.broadcast.positions = gp.verlet_positions.output.positions[-1]
        g.reflect_string.broadcast.velocities = gp.verlet_positions.output.velocities[-1]
        g.reflect_string.direct.structure = ip.structure_initial

        # reflect_atoms
        g.reflect_atoms.input.n_children = ip.n_images
        g.reflect_atoms.broadcast.default.reference_positions = \
            gp.initial_positions.output.initial_positions[-1]
        g.reflect_atoms.broadcast.default.previous_positions = \
            gp.initial_positions.output.initial_positions[-1]
        g.reflect_atoms.broadcast.default.previous_velocities = gp.initial_velocities.output.velocities[-1]
        g.reflect_atoms.direct.default.total_steps = ip._total_steps

        g.reflect_atoms.broadcast.reference_positions = gp.reparameterize.output.all_centroids_positions[-1]
        g.reflect_atoms.broadcast.positions = gp.reflect_string.output.positions[-1]
        g.reflect_atoms.broadcast.velocities = gp.reflect_string.output.velocities[-1]
        g.reflect_atoms.broadcast.previous_positions = gp.recenter.output.positions[-1]
        g.reflect_atoms.broadcast.previous_velocities = gp.reflect_atoms.output.velocities[-1]
        g.reflect_atoms.direct.structure = ip.structure_initial
        g.reflect_atoms.direct.cutoff_distance = gp.cutoff.output.cutoff_distance[-1]
        g.reflect_atoms.direct.use_reflection = ip.use_reflection
        g.reflect_atoms.broadcast.total_steps = gp.reflect_atoms.output.total_steps[-1]

        # calc_static_images
        g.calc_static_images.input.n_children = ip.n_images
        g.calc_static_images.direct.structure = ip.structure_initial
        g.calc_static_images.broadcast.project_path = gp.initialize_images.output.project_path[-1]
        g.calc_static_images.broadcast.job_name = gp.initialize_images.output.job_names[-1]
        g.calc_static_images.broadcast.positions = gp.reflect_atoms.output.positions[-1]

        # verlet_velocities
        g.verlet_velocities.input.n_children = ip.n_images
        g.verlet_velocities.broadcast.velocities = gp.reflect_atoms.output.velocities[-1]
        g.verlet_velocities.broadcast.forces = gp.calc_static_images.output.forces[-1]
        g.verlet_velocities.direct.masses = ip.structure_initial.get_masses
        g.verlet_velocities.direct.time_step = ip.time_step
        g.verlet_velocities.direct.temperature = ip.temperature
        g.verlet_velocities.direct.temperature_damping_timescale = ip.temperature_damping_timescale

        # running_average_positions
        g.running_average_pos.input.n_children = ip.n_images
        g.running_average_pos.direct.default.thermalization_steps = ip.thermalization_steps
        g.running_average_pos.direct.default.total_steps = ip._total_steps
        g.running_average_pos.direct.default.divisor = ip._divisor
        g.running_average_pos.broadcast.default.running_average_positions = \
            gp.initial_positions.output.initial_positions[-1]

        g.running_average_pos.broadcast.total_steps = gp.running_average_pos.output.total_steps[-1]
        g.running_average_pos.broadcast.divisor = gp.running_average_pos.output.divisor[-1]
        g.running_average_pos.broadcast.running_average_positions = \
            gp.running_average_pos.output.running_average_positions[-1]
        g.running_average_pos.broadcast.positions = gp.reflect_atoms.output.positions[-1]
        g.running_average_pos.direct.structure = ip.structure_initial

        # check_sampling_period
        g.check_sampling_period.input.target = gp.clock.output.n_counts[-1]
        g.check_sampling_period.input.default.mod = ip.sampling_period

        # mix
        g.mix.input.default.all_centroids_positions = gp.initial_positions.output.initial_positions[-1]
        g.mix.input.all_centroids_positions = gp.reparameterize.output.all_centroids_positions[-1]
        g.mix.input.mixing_fraction = ip.mixing_fraction
        g.mix.input.relax_endpoints = ip.relax_endpoints
        g.mix.input.running_average_positions = gp.running_average_pos.output.running_average_positions[-1]
        g.mix.input.structure = ip.structure_initial

        # smooth
        g.smooth.input.kappa = ip.nominal_smoothing
        g.smooth.input.dtau = ip.mixing_fraction
        g.smooth.input.structure = ip.structure_initial
        g.smooth.input.smooth_style = ip.smooth_style
        g.smooth.input.all_centroids_positions = gp.mix.output.all_centroids_positions[-1]

        # reparameterize
        g.reparameterize.input.all_centroids_positions = gp.smooth.output.all_centroids_positions[-1]
        g.reparameterize.input.structure= ip.structure_initial

        # calc_static_centroids
        g.calc_static_centroids.input.n_children = ip.n_images
        g.calc_static_centroids.direct.structure = ip.structure_initial
        g.calc_static_centroids.broadcast.project_path = gp.initialize_centroids.output.project_path[-1]
        g.calc_static_centroids.broadcast.job_name = gp.initialize_centroids.output.job_names[-1]
        g.calc_static_centroids.broadcast.positions = gp.reparameterize.output.all_centroids_positions[-1]

        # recenter
        g.recenter.input.n_children = ip.n_images
        g.recenter.direct.default.all_centroid_positions = gp.initial_positions.output.initial_positions[-1]
        g.recenter.broadcast.default.centroid_positions = gp.initial_positions.output.initial_positions[-1]
        g.recenter.direct.default.centroid_forces = gp.initial_forces.output.zeros[-1]

        g.recenter.direct.all_centroid_positions = gp.reparameterize.output.all_centroids_positions[-1]
        g.recenter.broadcast.centroid_positions = gp.reparameterize.output.all_centroids_positions[-1]
        g.recenter.broadcast.centroid_forces = gp.calc_static_centroids.output.forces[-1]
        g.recenter.broadcast.positions = gp.reflect_atoms.output.positions[-1]
        g.recenter.broadcast.forces = gp.calc_static_images.output.forces[-1]
        g.recenter.direct.structure= ip.structure_initial

        self.set_graph_archive_clock(gp.clock.output.n_counts[-1])

    def get_output(self):
        gp = Pointer(self.graph)
        return {
            'energy_pot': ~gp.calc_static_centroids.output.energy_pot[-1],
            'positions': ~gp.reparameterize.output.all_centroids_positions[-1],
            'forces': ~gp.calc_static_centroids.output.forces[-1]
        }

    def _get_energies(self, frame=None):
        if frame is None:
            return self.graph.calc_static_centroids.output.energy_pot[-1]
        else:
            return self.graph.calc_static_centroids.archive.output.energy_pot.data[frame]

    def plot_string(self, ax=None, frame=None, plot_kwargs=None):
        """
        Plot the string at an input frame. Here, frame is a dump of a step in the run. If `fts_job´ is the name
            of the fts job, the number of dumps can be specified by the user while submitting the job, as:

        >>> fts_job.set_output_whitelist(**{'calc_static_centroids': {'energy_pot': 20}})

        and run the job. Here, it dumps (or records a frame) of `energy_pot´ from the `calc_static_centroids´ vertex
            once every 20 steps.

        Default is plot the string at the final frame, as only the final dump is recorded. (unless specified
            otherwise by the user!)
        """
        if ax is None:
            _, ax = plt.subplots()
        if plot_kwargs is None:
            plot_kwargs = {}
        if 'marker' not in plot_kwargs.keys():
            plot_kwargs = {'marker': 'o'}
        energies = np.array(self._get_energies(frame=frame))
        ax.plot(energies - energies[0], **plot_kwargs)
        ax.set_ylabel("Energy")
        ax.set_xlabel("Centroid")
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        plt.show()

    def _get_directional_barrier(self, frame=None, anchor_element=0, use_minima=False):
        energies = np.array(self._get_energies(frame=frame))
        if use_minima:
            reference = energies.min()
        else:
            reference = energies[anchor_element]
        return energies.max() - reference

    def get_forward_barrier(self, frame=None, use_minima=False):
        """
        Get the energy barrier from the 0th image to the highest energy (saddle state).

        Args:
            frame (int): A particular dump. (Default is None, the final dump.)
            use_minima (bool): Whether to use the minima of the energies to compute the barrier. (Default is
                False, use the 0th value.)

        Returns:
            (float): the forward migration barrier.
        """
        return self._get_directional_barrier(frame=frame, use_minima=use_minima)

    def get_reverse_barrier(self, frame=None, use_minima=False):
        """
        Get the energy barrier from the final image to the highest energy (saddle state).

        Args:
            frame (int): A particular dump. (Default is None, the final dump.)
            use_minima (bool): Whether to use the minima of the energies to compute tha barrier. (Default is
                False, use the nth value.)

        Returns:
            (float): the backward migration barrier.
        """
        return self._get_directional_barrier(frame=frame, anchor_element=-1, use_minima=use_minima)

    def get_barrier(self, frame=None, use_minima=True):
        return self.get_forward_barrier(frame=frame, use_minima=use_minima)
    get_barrier.__doc__ = get_forward_barrier.__doc__


class ProtocolFTSEvolution(Protocol, FTSEvolution):
    pass


class _ConstrainedMD(CompoundVertex):
    """
    A sub-protocol for FTSEvolutionParallel for the evolution of each image. The MD is 'Constrained' as the atoms in
        the cells of each image evolve with the following constrains:

            a. If an image gets closer to a centroid which is NOT its parent centroid, reverse the velocities of
            all the atoms in that image, such that the image remains in the Voronoi cell of the parent centroid.
            b. If any atom in an image moves out of its Wigner-Seitz cell, reverse the velocities of all the atoms
            in that image.

    This sub-protocol is executed in parallel over multiple cores using ParallelList.

    NOTE: Presently for use only with Finite Temperature String (FTS) related protocols.
    """

    def define_vertices(self):
        # Graph components
        g = self.graph
        g.check_steps = IsGEq()
        g.verlet_positions = VerletPositionUpdate()
        g.reflect_string = StringReflect()
        g.reflect_atoms = SphereReflection()
        g.calc_static = ExternalHamiltonian()
        g.verlet_velocities = VerletVelocityUpdate()
        g.running_average_pos = PositionsRunningAverage()
        g.clock = Counter()

    def define_execution_flow(self):
        # Execution flow
        g = self.graph
        g.make_pipeline(
            g.check_steps, 'false',
            g.verlet_positions,
            g.reflect_string,
            g.reflect_atoms,
            g.calc_static,
            g.verlet_velocities,
            g.running_average_pos,
            g.clock,
            g.check_steps,
        )
        g.starting_vertex = g.check_steps
        g.restarting_vertex = g.check_steps

    def define_information_flow(self):
        # Data flow
        g = self.graph
        gp = Pointer(self.graph)
        ip = Pointer(self.input)

        # check_steps
        g.check_steps.input.target = gp.clock.output.n_counts[-1]
        g.check_steps.input.threshold = ip.n_steps

        # verlet_positions
        g.verlet_positions.input.default.positions = ip.positions
        g.verlet_positions.input.default.velocities = ip.velocities
        g.verlet_positions.input.default.forces = ip.forces

        g.verlet_positions.input.positions = gp.reflect_atoms.output.positions[-1]
        g.verlet_positions.input.velocities = gp.verlet_velocities.output.velocities[-1]
        g.verlet_positions.input.forces = gp.calc_static.output.forces[-1]
        g.verlet_positions.input.masses = ip.structure.get_masses
        g.verlet_positions.input.time_step = ip.time_step
        g.verlet_positions.input.temperature = ip.temperature
        g.verlet_positions.input.temperature_damping_timescale = ip.temperature_damping_timescale

        # reflect_string
        g.reflect_string.input.default.previous_positions = ip.positions
        g.reflect_string.input.default.previous_velocities = ip.velocities
        g.reflect_string.input.default.total_steps = ip.total_steps
        g.reflect_string.input.default.thermalization_steps = ip.thermalization_steps

        g.reflect_string.input.all_centroid_positions = ip.all_centroid_positions
        g.reflect_string.input.centroid_positions = ip.centroid_positions
        g.reflect_string.input.positions = gp.verlet_positions.output.positions[-1]
        g.reflect_string.input.velocities = gp.verlet_positions.output.velocities[-1]
        g.reflect_string.input.previous_positions = gp.reflect_atoms.output.positions[-1]
        g.reflect_string.input.previous_velocities = gp.verlet_velocities.output.velocities[-1]
        g.reflect_string.input.structure = ip.structure
        g.reflect_string.input.store_reflections = ip.store_reflections
        g.reflect_string.input.default.image_number = ip.image_number
        g.reflect_string.input.default.tracker_list = ip.tracker_list
        g.reflect_string.input.default.reflections_matrix = ip.reflections_matrix
        g.reflect_string.input.default.edge_reflections_matrix = ip.edge_reflections_matrix
        g.reflect_string.input.default.edge_time_matrix = ip.edge_time_matrix
        g.reflect_string.input.image_number = gp.reflect_string.output.image_number[-1]
        g.reflect_string.input.tracker_list = gp.reflect_string.output.tracker_list[-1]
        g.reflect_string.input.reflections_matrix = gp.reflect_string.output.reflections_matrix[-1]
        g.reflect_string.input.edge_reflections_matrix = gp.reflect_string.output.edge_reflections_matrix[-1]
        g.reflect_string.input.edge_time_matrix = gp.reflect_string.output.edge_time_matrix[-1]

        # reflect_atoms
        g.reflect_atoms.input.default.previous_positions = ip.positions
        g.reflect_atoms.input.default.previous_velocities = ip.velocities
        g.reflect_atoms.input.default.total_steps = ip.total_steps

        g.reflect_atoms.input.reference_positions = ip.centroid_positions
        g.reflect_atoms.input.positions = gp.reflect_string.output.positions[-1]
        g.reflect_atoms.input.velocities = gp.reflect_string.output.velocities[-1]
        g.reflect_atoms.input.previous_positions = gp.reflect_atoms.output.positions[-1]
        g.reflect_atoms.input.previous_velocities = gp.verlet_velocities.output.velocities[-1]
        g.reflect_atoms.input.structure = ip.structure
        g.reflect_atoms.input.cutoff_distance = ip.cutoff_distance
        g.reflect_atoms.input.use_reflection = ip.use_reflection
        g.reflect_atoms.input.total_steps = gp.reflect_atoms.output.total_steps[-1]

        # calc_static
        g.calc_static.input.structure = ip.structure
        g.calc_static.input.project_path = ip.project_path
        g.calc_static.input.job_name = ip.job_name
        g.calc_static.input.positions = gp.reflect_atoms.output.positions[-1]

        # verlet_velocities
        g.verlet_velocities.input.velocities = gp.reflect_atoms.output.velocities[-1]
        g.verlet_velocities.input.forces = gp.calc_static.output.forces[-1]
        g.verlet_velocities.input.masses = ip.structure.get_masses
        g.verlet_velocities.input.time_step = ip.time_step
        g.verlet_velocities.input.temperature = ip.temperature
        g.verlet_velocities.input.temperature_damping_timescale = ip.temperature_damping_timescale

        # running_average_positions
        g.running_average_pos.input.default.thermalization_steps = ip.thermalization_steps
        g.running_average_pos.input.default.total_steps = ip.total_steps
        g.running_average_pos.input.default.divisor = ip.divisor
        g.running_average_pos.input.default.running_average_positions = ip.running_average_positions

        g.running_average_pos.input.total_steps = gp.running_average_pos.output.total_steps[-1]
        g.running_average_pos.input.divisor = gp.running_average_pos.output.divisor[-1]
        g.running_average_pos.input.running_average_positions = \
            gp.running_average_pos.output.running_average_positions[-1]
        g.running_average_pos.input.positions = gp.reflect_atoms.output.positions[-1]
        g.running_average_pos.input.structure= ip.structure

        self.set_graph_archive_clock(gp.clock.output.n_counts[-1])

    def get_output(self):
        gp = Pointer(self.graph)
        ip = Pointer(self.input)
        if ~ip.store_reflections:
            return {
                'positions': ~gp.reflect_atoms.output.positions[-1],
                'velocities': ~gp.verlet_velocities.output.velocities[-1],
                'forces': ~gp.calc_static.output.forces[-1],
                'running_average_positions': ~gp.running_average_pos.output.running_average_positions[-1],
                'divisor': ~gp.running_average_pos.output.divisor[-1],
                'total_steps': ~gp.running_average_pos.output.total_steps[-1],
                'clock': ~gp.clock.output.n_counts[-1],
                'image_number': ~gp.reflect_string.output.image_number[-1],
                'tracker_list': ~gp.reflect_string.output.tracker_list[-1],
                'reflections_matrix': ~gp.reflect_string.output.reflections_matrix[-1],
                'edge_reflections_matrix': ~gp.reflect_string.output.edge_reflections_matrix[-1],
                'edge_time_matrix': ~gp.reflect_string.output.edge_time_matrix[-1]
            }
        else:
            return {
                'positions': ~gp.reflect_atoms.output.positions[-1],
                'velocities': ~gp.verlet_velocities.output.velocities[-1],
                'forces': ~gp.calc_static.output.forces[-1],
                'running_average_positions': ~gp.running_average_pos.output.running_average_positions[-1],
                'divisor': ~gp.running_average_pos.output.divisor[-1],
                'total_steps': ~gp.running_average_pos.output.total_steps[-1],
                'clock': ~gp.clock.output.n_counts[-1]
            }


class FTSEvolutionParallel(FTSEvolution):
    """
    A version of FTSEvolution where the evolution of each image is executed in parallel, thus giving a
        substantial speed-up. Maximum efficiency for parallelization can be achieved by setting the number of cores
        the job can use to the number of images, ie., cores / images = 1. Setting the number of cores greater than
        the number of images gives zero gain, and is wasteful if cores % images != 0.

    Input attributes:
      sleep_time (float): A delay in seconds for database access of results. For sqlite, a non-zero delay maybe
            required. (Default is 0 seconds, no delay.)

    For inherited input and output attributes, refer the `FTSEvolution` protocol.
    """

    def __init__(self, **kwargs):
        super(FTSEvolutionParallel, self).__init__(**kwargs)

        id_ = self.input.default
        # Default values
        # The remainder of the default values are inherited from HarmonicTILD
        id_.sleep_time = 0  # A delay for database access of results. For sqlite, a non-zero delay maybe required.

    def define_vertices(self):
        # Graph components
        g = self.graph
        ip = Pointer(self.input)
        g.create_centroids = SerialList(CreateJob)
        g.create_images = SerialList(CreateJob)
        g.initial_positions = InitialPositions()
        g.initial_forces = Zeros()
        g.initial_velocities = SerialList(RandomVelocity)
        g.cutoff = CutoffDistance()
        g.check_steps = IsGEq()
        g.constrained_evo = ParallelList(_ConstrainedMD, sleep_time=ip.sleep_time)
        g.check_thermalized = IsGEq()
        g.mix = CentroidsRunningAverageMix()
        g.smooth = CentroidsSmoothing()
        g.reparameterize = CentroidsReparameterization()
        g.calc_static_centroids = SerialList(ExternalHamiltonian)
        g.recenter = SerialList(StringRecenter)
        g.clock = Counter()
        g.check_convergence = CheckConvergence()
        g.exit = AnyVertex()

    def define_execution_flow(self):
        # Execution flow
        g = self.graph
        g.make_pipeline(
            g.create_centroids,
            g.create_images,
            g.initial_positions,
            g.initial_forces,
            g.initial_velocities,
            g.cutoff,
            g.check_steps, 'false',
            g.constrained_evo,
            g.clock,
            g.check_thermalized, 'true',
            g.mix,
            g.smooth,
            g.reparameterize,
            g.calc_static_centroids,
            g.recenter,
            g.check_convergence, 'false',
            g.exit
        )
        g.make_edge(g.check_thermalized, g.check_steps, 'false')
        g.make_edge(g.check_steps, g.exit, 'true')
        g.make_edge(g.check_convergence, g.exit, 'true')
        g.make_edge(g.exit, g.check_steps, 'false')
        g.starting_vertex = g.create_centroids
        g.restarting_vertex = g.check_steps

    def define_information_flow(self):
        # Data flow
        g = self.graph
        gp = Pointer(self.graph)
        ip = Pointer(self.input)

        # create_centroids
        g.create_centroids.input.n_children = ip.n_images
        g.create_centroids.direct.ref_job_full_path = ip.ref_job_full_path
        g.create_centroids.direct.structure = ip.structure_initial

        # create_images
        g.create_images.input.n_children = ip.n_images
        g.create_images.direct.ref_job_full_path = ip.ref_job_full_path
        g.create_images.direct.structure = ip.structure_initial

        # initial_positions
        g.initial_positions.input.structure_initial = ip.structure_initial
        g.initial_positions.input.structure_final = ip.structure_final
        g.initial_positions.input.initial_positions = ip.initial_positions
        g.initial_positions.input.n_images = ip.n_images

        # initial_forces
        g.initial_forces.input.shape = ip.structure_initial.positions.shape

        # initial_velocities
        g.initial_velocities.input.n_children = ip.n_images
        g.initial_velocities.direct.temperature = ip.temperature
        g.initial_velocities.direct.masses = ip.structure_initial.get_masses
        g.initial_velocities.direct.overheat_fraction = ip.overheat_fraction

        # cutoff
        g.cutoff.input.structure = ip.structure_initial
        g.cutoff.input.cutoff_factor = ip.cutoff_factor

        # check_steps
        g.check_steps.input.target = gp.clock.output.n_counts[-1]
        g.check_steps.input.threshold = ip.n_steps

        # constrained_evolution - initiailze
        g.constrained_evo.input.n_children = ip.n_images

        # constrained_evolution - verlet_positions
        g.constrained_evo.direct.structure = ip.structure_initial
        g.constrained_evo.direct.time_step = ip.time_step
        g.constrained_evo.direct.temperature = ip.temperature
        g.constrained_evo.direct.temperature_damping_timescale = ip.temperature_damping_timescale

        g.constrained_evo.broadcast.default.positions = gp.initial_positions.output.initial_positions[-1]
        g.constrained_evo.broadcast.default.velocities = gp.initial_velocities.output.velocities[-1]
        g.constrained_evo.direct.default.forces = gp.initial_forces.output.zeros[-1]

        g.constrained_evo.broadcast.positions = gp.recenter.output.positions[-1]
        g.constrained_evo.broadcast.velocities = gp.constrained_evo.output.velocities[-1]
        g.constrained_evo.broadcast.forces = gp.recenter.output.forces[-1]

        # constrained_evolution - reflect_string
        g.constrained_evo.direct.default.all_centroid_positions = gp.initial_positions.output.initial_positions[-1]
        g.constrained_evo.broadcast.default.centroid_positions = gp.initial_positions.output.initial_positions[-1]

        g.constrained_evo.direct.all_centroid_positions = gp.reparameterize.output.all_centroids_positions[-1]
        g.constrained_evo.direct.store_reflections = ip.store_reflections
        g.constrained_evo.broadcast.centroid_positions = gp.reparameterize.output.all_centroids_positions[-1]
        g.constrained_evo.direct.default.image_number = ip._image_number
        g.constrained_evo.direct.default.tracker_list = ip._tracker_list
        g.constrained_evo.direct.default.reflections_matrix = ip._reflections_matrix
        g.constrained_evo.direct.default.edge_reflections_matrix = ip._edge_reflections_matrix
        g.constrained_evo.direct.default.edge_time_matrix = ip._edge_time_matrix

        # constrained_evolution - reflect_atoms
        g.constrained_evo.direct.default.total_steps = ip._total_steps
        g.constrained_evo.broadcast.total_steps = gp.constrained_evo.output.total_steps[-1]
        g.constrained_evo.direct.cutoff_distance = gp.cutoff.output.cutoff_distance[-1]

        # constrained_evolution - calc_static
        g.constrained_evo.broadcast.project_path = gp.create_images.output.project_path[-1]
        g.constrained_evo.broadcast.job_name = gp.create_images.output.job_names[-1]

        # constrained_evolution - verlet_velocities
        # takes inputs already specified in verlet_positions

        # constrained_evolution - running_average_positions
        g.constrained_evo.direct.default.thermalization_steps = ip.thermalization_steps
        g.constrained_evo.direct.default.divisor = ip._divisor
        g.constrained_evo.broadcast.default.running_average_positions = \
            gp.initial_positions.output.initial_positions[-1]

        g.constrained_evo.broadcast.divisor = gp.constrained_evo.output.divisor[-1]
        g.constrained_evo.broadcast.running_average_positions = \
            gp.constrained_evo.output.running_average_positions[-1]

        # constrained_evolution - clock
        g.constrained_evo.direct.n_steps = ip.sampling_period

        # clock
        g.clock.input.add_counts = ip.sampling_period

        # check_thermalized
        g.check_thermalized.input.target = gp.constrained_evo.output.total_steps[-1][-1]
        g.check_thermalized.input.threshold = ip.thermalization_steps

        # mix
        g.mix.input.default.all_centroids_positions = gp.initial_positions.output.initial_positions[-1]
        g.mix.input.all_centroids_positions = gp.reparameterize.output.all_centroids_positions[-1]
        g.mix.input.mixing_fraction = ip.mixing_fraction
        g.mix.input.relax_endpoints = ip.relax_endpoints
        g.mix.input.running_average_positions = gp.constrained_evo.output.running_average_positions[-1]
        g.mix.input.structure = ip.structure_initial

        # smooth
        g.smooth.input.kappa = ip.nominal_smoothing
        g.smooth.input.dtau = ip.mixing_fraction
        g.smooth.input.structure = ip.structure_initial
        g.smooth.input.smooth_style = ip.smooth_style
        g.smooth.input.all_centroids_positions = gp.mix.output.all_centroids_positions[-1]

        # reparameterize
        g.reparameterize.input.all_centroids_positions = gp.smooth.output.all_centroids_positions[-1]
        g.reparameterize.input.structure = ip.structure_initial

        # calc_static_centroids
        g.calc_static_centroids.input.n_children = ip.n_images
        g.calc_static_centroids.direct.structure = ip.structure_initial
        g.calc_static_centroids.broadcast.project_path = gp.create_centroids.output.project_path[-1]
        g.calc_static_centroids.broadcast.job_name = gp.create_centroids.output.job_names[-1]
        g.calc_static_centroids.broadcast.positions = gp.reparameterize.output.all_centroids_positions[-1]

        # recenter
        g.recenter.input.n_children = ip.n_images
        g.recenter.direct.default.all_centroid_positions = gp.initial_positions.output.initial_positions[-1]
        g.recenter.broadcast.default.centroid_positions = gp.initial_positions.output.initial_positions[-1]
        g.recenter.broadcast.default.centroid_forces = gp.initial_forces.output.zeros[-1]

        g.recenter.direct.all_centroid_positions = gp.reparameterize.output.all_centroids_positions[-1]
        g.recenter.broadcast.centroid_positions = gp.reparameterize.output.all_centroids_positions[-1]
        g.recenter.broadcast.centroid_forces = gp.calc_static_centroids.output.forces[-1]
        g.recenter.broadcast.positions = gp.constrained_evo.output.positions[-1]
        g.recenter.broadcast.forces = gp.constrained_evo.output.forces[-1]
        g.recenter.direct.structure = ip.structure_initial

        # check_convergence
        g.check_convergence.input.all_centroid_energies = gp.calc_static_centroids.output.energy_pot[-1]
        g.check_convergence.input.all_centroid_positions = gp.reparameterize.output.all_centroids_positions[-1]
        g.check_convergence.input.default.previous_centroid_positions = ip._previous_centroid_positions
        g.check_convergence.input.previous_centroid_positions = \
            gp.check_convergence.output.previous_centroid_positions[-1]
        g.check_convergence.input.structure = ip.structure_initial
        g.check_convergence.input.tolerance = ip.tolerance
        g.check_convergence.input.anchor_element = ip.anchor_element
        g.check_convergence.input.use_minima = ip.use_minima

        # exit
        g.exit.input.vertex_states = [
            gp.check_steps.vertex_state,
            gp.check_convergence.vertex_state
        ]
        g.exit.input.print_strings = [
            'Maximum steps reached',
            'Convergence reached'
        ]

        self.set_graph_archive_clock(gp.clock.output.n_counts[-1])

    def get_output(self):
        gp = Pointer(self.graph)
        return {
            'energy_pot': ~gp.calc_static_centroids.output.energy_pot[-1],
            'positions': ~gp.reparameterize.output.all_centroids_positions[-1],
            'forces': ~gp.calc_static_centroids.output.forces[-1],
            'convergence_list': ~gp.check_convergence.output.convergence_list[-1],
            'total_steps': ~gp.clock.output.n_counts[-1],
            'runtime_list': ~gp.constrained_evo.output.runtime_list[-1],
            'memory_list': ~gp.constrained_evo.output.memory_list[-1]
        }


class ProtocolFTSEvolutionParallel(Protocol, FTSEvolutionParallel):
    pass


class FTSMilestoningParallel(FTSEvolution):
    """
    Calculates the jump frequencies of each centroid to the final centroid, also returns the free energies of each
        Centroid.

    Input attributes:
      sleep_time (float): A delay in seconds for database access of results. For sqlite, a non-zero delay maybe
            required. (Default is 0 seconds, no delay.)

    For inherited input and output attributes, refer the `FTSEvolution` protocol.
    """

    def __init__(self, **kwargs):
        super(FTSMilestoningParallel, self).__init__(**kwargs)

        id_ = self.input.default
        # Default values
        # The remainder of the default values are inherited from HarmonicTILD
        id_.sleep_time = 0  # A delay for database access of results. For sqlite, a non-zero delay maybe required.
        id_.store_reflections = True

    def define_vertices(self):
        # Graph components
        g = self.graph
        ip = Pointer(self.input)
        g.centroid_positions = InitialPositions()
        g.initial_forces = Zeros()
        g.initial_velocities = SerialList(RandomVelocity)
        g.cutoff = CutoffDistance()
        g.check_steps = IsGEq()
        g.create_centroids = SerialList(CreateJob)
        g.constrained_evo = ParallelList(_ConstrainedMD, sleep_time=ip.sleep_time)
        g.diff = Difference()
        g.clock = Counter()
        g.milestone_post = MilestonePostProcess()

    def define_execution_flow(self):
        # Execution flow
        g = self.graph
        g.make_pipeline(
            g.centroid_positions,
            g.initial_forces,
            g.initial_velocities,
            g.cutoff,
            g.check_steps, 'false',
            g.create_centroids,
            g.diff,
            g.constrained_evo,
            g.clock,
            g.check_steps, 'true',
            g.milestone_post
        )
        g.starting_vertex = g.centroid_positions
        g.restarting_vertex = g.check_steps

    def define_information_flow(self):
        # Data flow
        g = self.graph
        gp = Pointer(self.graph)
        ip = Pointer(self.input)

        # centroid_positions
        g.centroid_positions.input.structure_initial = ip.structure_initial
        g.centroid_positions.input.structure_final = ip.structure_final
        g.centroid_positions.input.initial_positions = ip.initial_positions
        g.centroid_positions.input.n_images = ip.n_images

        # initial_forces
        g.initial_forces.input.shape = ip.structure_initial.positions.shape

        # initial_velocities
        g.initial_velocities.input.n_children = ip.n_images
        g.initial_velocities.direct.temperature = ip.temperature
        g.initial_velocities.direct.masses = ip.structure_initial.get_masses
        g.initial_velocities.direct.overheat_fraction = ip.overheat_fraction

        # cutoff
        g.cutoff.input.structure = ip.structure_initial
        g.cutoff.input.cutoff_factor = ip.cutoff_factor

        # check_steps
        g.check_steps.input.target = gp.clock.output.n_counts[-1]
        g.check_steps.input.threshold = ip.n_steps

        # create_centroids
        g.create_centroids.input.n_children = ip.n_images
        g.create_centroids.direct.ref_job_full_path = ip.ref_job_full_path
        g.create_centroids.direct.structure = ip.structure_initial

        # diff
        g.diff.input.a = ip.n_steps
        g.diff.input.default.b = ip._total_steps
        g.diff.input.b = gp.constrained_evo.output.total_steps[-1][-1]

        # constrained_evolution - initiailze
        g.constrained_evo.input.n_children = ip.n_images

        # constrained_evolution - verlet_positions
        g.constrained_evo.direct.structure = ip.structure_initial
        g.constrained_evo.direct.time_step = ip.time_step
        g.constrained_evo.direct.temperature = ip.temperature
        g.constrained_evo.direct.temperature_damping_timescale = ip.temperature_damping_timescale

        g.constrained_evo.broadcast.default.positions = gp.centroid_positions.output.initial_positions[-1]
        g.constrained_evo.broadcast.default.velocities = gp.initial_velocities.output.velocities[-1]
        g.constrained_evo.direct.default.forces = gp.initial_forces.output.zeros[-1]

        g.constrained_evo.broadcast.positions = gp.constrained_evo.output.positions[-1]
        g.constrained_evo.broadcast.velocities = gp.constrained_evo.output.velocities[-1]
        g.constrained_evo.broadcast.forces = gp.constrained_evo.output.forces[-1]

        # constrained_evolution - reflect_string
        g.constrained_evo.direct.default.all_centroid_positions = gp.centroid_positions.output.initial_positions[-1]
        g.constrained_evo.direct.default.store_reflections = ip.store_reflections
        g.constrained_evo.broadcast.default.centroid_positions = gp.centroid_positions.output.initial_positions[-1]
        g.constrained_evo.direct.default.image_number = ip._image_number
        g.constrained_evo.direct.default.tracker_list = ip._tracker_list
        g.constrained_evo.direct.default.reflections_matrix = ip._reflections_matrix
        g.constrained_evo.direct.default.edge_reflections_matrix = ip._edge_reflections_matrix
        g.constrained_evo.direct.default.edge_time_matrix = ip._edge_time_matrix

        g.constrained_evo.broadcast.image_number = gp.constrained_evo.output.image_number[-1]
        g.constrained_evo.broadcast.tracker_list = gp.constrained_evo.output.tracker_list[-1]
        g.constrained_evo.broadcast.reflections_matrix = gp.constrained_evo.output.reflections_matrix[-1]
        g.constrained_evo.broadcast.edge_reflections_matrix = gp.constrained_evo.output.edge_reflections_matrix[-1]
        g.constrained_evo.broadcast.edge_time_matrix = gp.constrained_evo.output.edge_time_matrix[-1]

        # constrained_evolution - reflect_atoms
        g.constrained_evo.direct.default.total_steps = ip._total_steps
        g.constrained_evo.broadcast.total_steps = gp.constrained_evo.output.total_steps[-1]
        g.constrained_evo.direct.cutoff_distance = gp.cutoff.output.cutoff_distance[-1]

        # constrained_evolution - calc_static
        g.constrained_evo.broadcast.project_path = gp.create_centroids.output.project_path[-1]
        g.constrained_evo.broadcast.job_name = gp.create_centroids.output.job_names[-1]

        # constrained_evolution - verlet_velocities
        # takes inputs already specified in verlet_positions

        # constrained_evolution - running_average_positions
        g.constrained_evo.direct.default.thermalization_steps = ip.thermalization_steps
        g.constrained_evo.direct.default.divisor = ip._divisor
        g.constrained_evo.broadcast.default.running_average_positions = \
            gp.centroid_positions.output.initial_positions[-1]

        g.constrained_evo.broadcast.divisor = gp.constrained_evo.output.divisor[-1]
        g.constrained_evo.broadcast.running_average_positions = \
            gp.constrained_evo.output.running_average_positions[-1]

        # constrained_evolution - clock
        g.constrained_evo.direct.n_steps = gp.diff.output.diff[-1]

        # clock
        g.clock.input.add_counts = gp.diff.output.diff[-1]

        # milestone_post
        g.milestone_post.input.time_step = ip.time_step
        g.milestone_post.input.reflections_matrix = gp.constrained_evo.output.reflections_matrix[-1]
        g.milestone_post.input.edge_reflections_matrix = gp.constrained_evo.output.edge_reflections_matrix[-1]
        g.milestone_post.input.edge_time_matrix = gp.constrained_evo.output.edge_time_matrix[-1]
        g.milestone_post.input.n_images = ip.n_images
        g.milestone_post.input.temperature = ip.temperature

        self.set_graph_archive_clock(gp.clock.output.n_counts[-1])

    def get_output(self):
        gp = Pointer(self.graph)
        return {
            'equilibrium_probability': ~gp.milestone_post.output.equilibrium_probability[-1],
            'free_energies': ~gp.milestone_post.output.free_energies[-1],
            'jump_frequencies': ~gp.milestone_post.output.jump_frequencies[-1],
            'mean_first_passage_times': ~gp.milestone_post.output.mean_first_passage_times[-1],
            'reflections_matrix': ~gp.milestone_post.output.reflections_matrix[-1],
            'edge_reflections_matrix': ~gp.milestone_post.output.edge_reflections_matrix[-1],
            'edge_time_matrix': ~gp.milestone_post.output.edge_time_matrix[-1],
            'total_steps': ~gp.constrained_evo.output.total_steps[-1],
            'running_average_positions': ~gp.constrained_evo.output.running_average_positions[-1]
        }


class ProtocolFTSMilestoningParallel(Protocol, FTSMilestoningParallel):
    pass
