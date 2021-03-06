# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function
from pyiron_contrib.protocol.generic import PrimitiveVertex
from pyiron_contrib.protocol.primitive.two_state import BoolVertex
import numpy as np
from abc import abstractmethod
from scipy.linalg import toeplitz
from scipy.constants import physical_constants, femto

KB = physical_constants['Boltzmann constant in eV/K'][0]

"""
Vertices whose present application extends only to finite temperature string-based protocols.
"""

__author__ = "Raynol Dsouza, Liam Huber"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "20 July, 2019"


class _StringDistances(PrimitiveVertex):
    """
    A parent class for vertices which care about the distance from an image to various centroids on the string.
    """
    def __init__(self, name=None):
        super(PrimitiveVertex, self).__init__(name=name)
        self.input.default.eps = 1e-6

    @abstractmethod
    def command(self, *args, **kwargs):
        pass

    @staticmethod
    def check_closest_to_parent(structure, positions, centroid_positions, all_centroid_positions, eps):
        """
        Checks which centroid the image is closest too, then measures whether or not that closest centroid is sufficiently
            close to the image's parent centroid.
        Args:
            structure (Atoms): The reference structure.
            positions (numpy.ndarray): Atomic positions of this image
            centroid_positions (numpy.ndarray): The positions of the image's centroid
            all_centroid_positions (list/numpy.ndarray): A list of positions for all centroids in the string
            eps (float): The maximum distance between the closest centroid and the parent centroid to be considered a
                match (i.e. no recentering necessary)
        Returns:
            (bool): Whether the image is closest to its own parent centroid
        """
        distances = [np.linalg.norm(structure.find_mic(c_pos - positions)) for c_pos in all_centroid_positions]
        closest_centroid_positions = all_centroid_positions[np.argmin(distances)]
        match_distance = np.linalg.norm(structure.find_mic(closest_centroid_positions - centroid_positions))
        return distances, match_distance < eps


class StringRecenter(_StringDistances):
    """
    If not, the image's positions and forces are reset to match its centroid.

    Input attributes:
        positions (numpy.ndarray): Atomic positions of the image
        forces (numpy.ndarray): Atomic forces on the image
        centroid_positions (numpy.ndarray): The positions of the image's centroid
        centroid_forces (numpy.ndarray): The forces on the image's centroid
        all_centroid_positions (list/numpy.ndarray): A list of positions for all centroids in the string
        structure (Atoms): The reference structure
        eps (float): The maximum distance between the closest centroid and the parent centroid to be considered a match
            (i.e. no recentering necessary). (Default is 1e-6.)

    Output attributes:
        positions (numpy.ndarray): Either the original positions passed in, or the centroid positions
        forces (numpy.ndarray): Either the original forces passed in, or the centroid forces
        recentered (bool): Whether or not the image got recentered
    """
    def command(self, structure, positions, forces, centroid_positions, centroid_forces, all_centroid_positions, eps):
        _, recenter = self.check_closest_to_parent(structure, positions, centroid_positions,
                                                   all_centroid_positions, eps)
        if recenter:
            return {
                'positions': positions,
                'forces': forces,
                'recentered': False,
            }
        else:
            return {
                'positions': centroid_positions,
                'forces': centroid_forces,
                'recentered': True
            }


class StringReflect(_StringDistances):
    """
    If not, the image's positions and forces are reset to match its centroid

    Input attributes:
        positions (numpy.ndarray): Atomic positions of the image
        velocities (numpy.ndarray): Atomic velocities of the image
        previous_positions (numpy.ndarray): Atomic positions of the image from the previous timestep
        previous_velocities (numpy.ndarray): Atomic velocities of the image from the previous timestep
        centroid_positions (numpy.ndarray): The positions of the image's centroid
        all_centroid_positions (list/numpy.ndarray): A list of positions for all centroids in the string
        structure (Atoms): The reference structure
        eps (float): The maximum distance between the closest centroid and the parent centroid to be considered a match
            (i.e. no recentering necessary). (Default is 1e-6.)

    Output attributes:
        positions (numpy.ndarray): Either the original positions passed in, or the previous ones
        forces (numpy.ndarray): Either the original forces passed in, or the previous ones
        reflected (bool): Whether or not the image got recentered
    """
    def __init__(self, name=None):
        super(StringReflect, self).__init__(name=name)
        id_ = self.input.default
        id_.store_reflections = False
        id_.image_number = None
        id_.tracker_list = None
        id_.reflections_matrix = None
        id_.edge_reflections_matrix = None
        id_.edge_time_matrix = None

    # def command(self, structure, positions, velocities, previous_positions, previous_velocities, centroid_positions,
    #             all_centroid_positions, eps):
    #     if self.check_closest_to_parent(structure, positions, centroid_positions, all_centroid_positions, eps):
    #         return {
    #             'positions': positions,
    #             'velocities': velocities,
    #             'reflected': False
    #         }
    #     else:
    #         return {
    #             'positions': previous_positions,
    #             'velocities': -previous_velocities,
    #             'reflected': True
    #         }

    def command(self, structure, positions, velocities, previous_positions, previous_velocities, centroid_positions,
                all_centroid_positions, eps, store_reflections, thermalization_steps, image_number, tracker_list,
                reflections_matrix, edge_reflections_matrix, edge_time_matrix, total_steps):

        n_images = len(all_centroid_positions)
        n_edges = int(n_images * (n_images - 1) / 2)
        current_step = total_steps + self.archive.clock

        if (current_step == 0) and store_reflections:  # clock always starts from 1
            # form the matrices
            distances, _ = self.check_closest_to_parent(structure, centroid_positions, centroid_positions,
                                                        all_centroid_positions, eps)
            image_number = np.argmin(distances)
            tracker_list = [[None, None] for _ in np.arange(n_images)]
            reflections_matrix = np.zeros((n_images, n_images))
            edge_reflections_matrix = np.array([np.zeros((n_edges, n_edges)) for _ in np.arange(n_images)])
            edge_time_matrix = np.array([np.zeros(n_edges) for _ in np.arange(n_images)])

        # Find distance between positions and each of the centroids
        distances, check = self.check_closest_to_parent(structure, positions, centroid_positions,
                                                        all_centroid_positions, eps)
        closest_centroid_id = np.argmin(distances)

        if store_reflections:
            tracker = tracker_list[image_number]

        if check:
            # Return current positions and velocities
            reflected_positions = positions
            reflected_velocities = velocities

            if (current_step > thermalization_steps) and store_reflections:
                # Start reflection tracking
                if tracker[1] is not None:  # If no reflections, increment time
                    edge_time_matrix[image_number][tracker[1]] += 1
                # End reflection tracking
        elif not check:
            # Update to previous positions and velocities, if positions are not closest to parent centroid
            reflected_positions = previous_positions
            reflected_velocities = -previous_velocities

            if (current_step > thermalization_steps) and store_reflections:
                # Start reflection tracking
                reflections_matrix[image_number, closest_centroid_id] += 1  # Save the reflection
                indices = np.zeros((n_images, n_images))  # images x images
                indices[image_number, closest_centroid_id] = 1  # Record the edge
                ind = np.tril(indices) + np.triu(indices).T  # Convert to triangular matrix
                # Record the index of the edge (N_j)
                n_j = int(np.nonzero(ind[np.tril_indices(n_images, k=-1)])[0][0])

                if tracker[1] is None:
                    tracker[1] = n_j  # Initialize N_j
                elif tracker[1] == n_j:
                    edge_time_matrix[image_number][n_j] += 1
                else:
                    tracker[0] = tracker[1]  # If reflecting off a different edge, change N_j to N_i
                    tracker[1] = n_j  # Set new N_j
                    edge_reflections_matrix[image_number][tracker[0], tracker[1]] += 1
                    # End reflection tracking

                tracker_list[image_number] = tracker
        else:
            raise ValueError

        if not store_reflections:
            return {
                'positions': reflected_positions,
                'velocities': reflected_velocities,
                'image_number': image_number,
                'tracker_list': tracker_list,
                'reflections_matrix': reflections_matrix,
                'edge_reflections_matrix': edge_reflections_matrix,
                'edge_time_matrix': edge_time_matrix
            }
        else:
            return {
                'positions': reflected_positions,
                'velocities': reflected_velocities,
                'image_number': image_number,
                'tracker_list': tracker_list,
                'reflections_matrix': reflections_matrix,
                'edge_reflections_matrix': edge_reflections_matrix,
                'edge_time_matrix': edge_time_matrix
            }


class PositionsRunningAverage(PrimitiveVertex):
    """
    Calculates the running average of input positions at each call.

    Input attributes:
        positions (list/numpy.ndarray): The instantaneous position, which will be updated to the running average
        running_average_positions (list/numpy.ndarray): The running average of positions
        total_steps (int): The total number of times `SphereReflectionPerAtom` is called so far (Default is 0.)
        thermalization_steps (int): Number of steps the system is thermalized for to reach equilibrium (Default is
            10 steps.)
        divisor (int): The divisor for the running average positions. Increments by 1, each time the vertex is
            called (Default is 1.)
        structure (Atoms): The reference structure

    Output attributes:
        running_average_positions (list/numpy.ndarray): The updated running average list
        divisor (int): The updated divisor

    TODO:
        Handle non-static cells, or at least catch them.
    """

    def __init__(self, name=None):
        super(PositionsRunningAverage, self).__init__(name=name)
        id_ = self.input.default
        id_.total_steps = 0
        id_.thermalization_steps = 10
        id_.divisor = 1

    def command(self, structure, positions, running_average_positions, total_steps, thermalization_steps, divisor):
        total_steps += 1
        if total_steps > thermalization_steps:
            divisor += 1  # On the first step, divide by 2 to average two positions
            weight = 1. / divisor  # How much of the current step to mix into the average
            displacement = structure.find_mic(positions - running_average_positions)
            new_running_average = running_average_positions + (weight * displacement)
            return {
                'running_average_positions': new_running_average,
                'total_steps': total_steps,
                'divisor': divisor,
            }
        else:
            return {
                'running_average_positions': running_average_positions,
                'total_steps': total_steps,
                'divisor': divisor,
            }


class CentroidsRunningAverageMix(PrimitiveVertex):
    """
    Mix in the running average of the positions to the centroid, moving the centroid towards that
        running average by a fraction.

    Input attributes:
        mixing_fraction (float): The fraction of the running average to mix into centroid (Default is 0.1)
        all_centroids_positions (list/numpy.ndarray): List of all the centroids along the string
        running_average_list (list/numpy.ndarray): List of running averages
        structure (Atoms): The reference structure
        relax_endpoints (bool): Whether or not to relax the endpoints of the string (Default is False.)

    Output attributes:
        all_centroids_positions (list/numpy.ndarray): List centroids updated towards the running average
    """

    def __init__(self, name=None):
        super(CentroidsRunningAverageMix, self).__init__(name=name)
        self.input.default.mixing_fraction = 0.1
        self.input.default.relax_endpoints = False

    def command(self, structure, mixing_fraction, all_centroids_positions, running_average_positions, relax_endpoints):

        all_centroids_positions = np.array(all_centroids_positions)
        running_average_positions = np.array(running_average_positions)

        updated_centroids = []

        for i, (cent, avg) in enumerate(zip(all_centroids_positions, running_average_positions)):
            if (i == 0 or i == (len(all_centroids_positions) - 1)) and not relax_endpoints:
                updated_centroids.append(cent)
            else:
                displacement = structure.find_mic(avg - cent)
                update = mixing_fraction * displacement
                updated_centroids.append(cent + update)

        return {
            'all_centroids_positions': updated_centroids
        }


class CentroidsSmoothing(PrimitiveVertex):
    """
    Global / local smoothing following Vanden-Eijnden and Venturoli (2009). The actual smoothing strength is the
        product of the nominal smoothing strength (`kappa`), the number of images, and the mixing fraction
        (`dtau`).

    Input Attributes:
        kappa (float): Nominal smoothing strength (Default is 0.1)
        dtau (float): Mixing fraction (from updating the string towards the moving average of the image positions)
        all_centroids_positions (list/numpy.ndarray): List of all the centroid positions along the string
        structure (Atoms): The reference structure
        smooth_style (string): Apply 'global' or 'local' smoothing (Default is 'global'.)

    Output Attributes:
        all_centroid_positions (list/numpy.ndarray): List of smoothed centroid positions
    """

    def __init__(self, name=None):
        super(CentroidsSmoothing, self).__init__(name=name)
        id_ = self.input.default
        id_.kappa = 0.1
        id_.dtau = 0.1
        id_.smooth_style = 'global'

    def command(self, structure, kappa, dtau, all_centroids_positions, smooth_style):
        n_images = len(all_centroids_positions)
        smoothing_strength = kappa * n_images * dtau
        if smooth_style == 'global':
            smoothing_matrix = self._get_smoothing_matrix(n_images, smoothing_strength)
            # smoothed_centroid_positions = all_centroids_positions + \
            #                               np.tensordot(smoothing_matrix, all_centroids_positions, axes=1)
            smoothed_centroid_positions = np.tensordot(smoothing_matrix, all_centroids_positions, axes=1)
        elif smooth_style == 'local':
            smoothed_centroid_positions = self._locally_smoothed(structure, smoothing_strength,
                                                                 all_centroids_positions)
        else:
            raise TypeError('Smoothing: choose style = "global" or "local"')
        return {
            'all_centroids_positions': smoothed_centroid_positions
        }

    @staticmethod
    def _get_smoothing_matrix(n_images, smoothing_strength):
        """
        A function that returns the smoothing matrix used in global smoothing.

        Attributes:
            n_images (int): Number of images
            smoothing_strength (float): The smoothing penalty

        Returns:
            smoothing_matrix
        """
        toeplitz_rowcol = np.zeros(n_images)
        toeplitz_rowcol[0] = -2
        toeplitz_rowcol[1] = 1
        second_order_deriv = toeplitz(toeplitz_rowcol, toeplitz_rowcol)
        second_order_deriv[0] = np.zeros(n_images)
        second_order_deriv[-1] = np.zeros(n_images)
        smooth_mat_inv = np.eye(n_images) - smoothing_strength * second_order_deriv
        # smoothing_matrix = smoothing_strength * second_order_deriv

        return np.linalg.inv(smooth_mat_inv)
        # return smoothing_matrix

    @staticmethod
    def _locally_smoothed(structure, smoothing_strength, all_centroids_positions):
        """
        A function that applies local smoothing by taking into account immediate neighbors.

        Attributes:
            structure (Atoms): The reference structure
            smoothing_strength (float): The smoothing penalty
            all_centroids_positions (list): The list of centroids

        Returns:
            smoothed_centroid_positions
        """
        smoothed_centroid_positions = [all_centroids_positions[0]]
        for i, cent in enumerate(all_centroids_positions[1:-1]):
            left = all_centroids_positions[i]
            right = all_centroids_positions[i+2]
            disp_left = structure.find_mic(cent - left)
            disp_right = structure.find_mic(right - cent)
            # switch = (1 + np.cos(np.pi * np.tensordot(disp_left, disp_right) / (
            #             np.linalg.norm(disp_left) * (np.linalg.norm(disp_right))))) / 2
            # r_star = smoothing_strength * switch * (disp_right - disp_left)
            r_star = smoothing_strength * (disp_right - disp_left)
            smoothed_centroid_positions.append(cent + r_star)
        smoothed_centroid_positions.append(all_centroids_positions[-1])

        return np.array(smoothed_centroid_positions)


class CentroidsReparameterization(PrimitiveVertex):
    """
    Use linear interpolation to equally space the jobs between the first and last job in 3N dimensional space,
        using a piecewise function.

    Input attributes:
        all_centroids_positions (list/numpy.ndarray): List of all the centroids along the string
        structure (Atoms): The reference structure

    Output attributes:
        all_centroids_positions (list/numpy.ndarray): List of equally spaced centroids
    """

    def __init__(self, name=None):
        super(CentroidsReparameterization, self).__init__(name=name)

    def command(self, structure, all_centroids_positions):
        # How long is the piecewise parameterized path to begin with?
        lengths = self._find_lengths(all_centroids_positions, structure)
        length_tot = lengths[-1]
        length_per_frame = length_tot / (len(all_centroids_positions) - 1)

        # Find new positions for the re-parameterized jobs
        reparameterized_centroids = [all_centroids_positions[0]]
        for n_left, cent in enumerate(all_centroids_positions[1:-1]):
            n = n_left + 1
            length_target = n * length_per_frame

            # Find the last index not in excess of the target length
            try:
                all_not_over = np.argwhere(lengths < length_target)
                highest_not_over = np.amax(all_not_over)
            except ValueError:
                # If all_not_over is empty
                highest_not_over = 0

            # Interpolate from the last position not in excess
            start = all_centroids_positions[highest_not_over]
            end = all_centroids_positions[highest_not_over + 1]
            disp = structure.find_mic(end - start)
            interp_dir = disp / np.linalg.norm(disp)
            interp_mag = length_target - lengths[highest_not_over]

            reparameterized_centroids.append(start + interp_mag * interp_dir)
        reparameterized_centroids.append(all_centroids_positions[-1])

        return {
            'all_centroids_positions': reparameterized_centroids
        }

    @staticmethod
    def _find_lengths(a_list, structure):
        """
        Finds the cummulative distance from job to job.

        Attribute:
            a_list (list/numpy.ndarray): List of positions whose lengths are to be calculated
            structure (Atoms): The reference structure

        Returns:
            lengths (list): Lengths of the positions in the list
        """
        length_cummulative = 0
        lengths = [length_cummulative]
        # First length is zero, all other lengths are wrt the first position in the list
        for n_left, term in enumerate(a_list[1:]):
            disp = structure.find_mic(term - a_list[n_left])
            length_cummulative += np.linalg.norm(disp)
            lengths.append(length_cummulative)
        return lengths


class CheckConvergence(BoolVertex):
    """
    Check if the energies for each of the centroids are below a threshold.

    Input attributes:
        all_centroid_energies (list): List of all the centroid energies along the string
        n_energy_samples (int): Number of energy samples of each centroid to calculate the std (Default is 10.)
        tolerance (float): The value of std below which the string is considered to be converged (Default is 0.001.)
        recent_energy_list (list): List of recent energies considered to compute the std
        anchor_element (int): The centroid number to use as the reference to compute the barrier (Default is 0.)
        use_minima (bool): Whether to use the minima of the energies to compute the barrier (Default is
                False, use the 0th value.)

    Output attributes:
        recent_energy_list (list): List of recent energies considered to compute the std
    """

    def __init__(self, name=None):
        super(CheckConvergence, self).__init__(name=name)
        self.input.default.tolerance = 0.001
        self.input.default.anchor_element = 0
        self.input.default.use_minima = True
        self.input.default.previous_centroid_positions = None

    def command(self, all_centroid_energies, all_centroid_positions, previous_centroid_positions, structure,
                tolerance, anchor_element, use_minima):

        if previous_centroid_positions is None:
            self.vertex_state = "false"
            convergence_list = None
        else:
            all_centroid_positions = np.array(all_centroid_positions)
            previous_centroid_positions = np.array(previous_centroid_positions)
            disp = structure.find_mic(all_centroid_positions - previous_centroid_positions)
            convergence_list = []
            for diff in disp:
                convergence_list.append(np.linalg.norm(diff))

            # check if converged
            if len(convergence_list) != 0:
                if np.amax(convergence_list) < tolerance:
                    self.vertex_state = "true"
            else:
                self.vertex_state = "false"

        previous_centroid_positions = all_centroid_positions

        if use_minima:
            reference = np.array(all_centroid_energies).min()
        else:
            reference = all_centroid_energies[anchor_element]
        barrier = np.array(all_centroid_energies).max() - reference
        print('Migration Barrier : {}'.format(barrier))

        return {
            'previous_centroid_positions': previous_centroid_positions,
            'convergence_list': convergence_list
        }


class MilestonePostProcess(PrimitiveVertex):
    """
    Generates jump frequencies of each centroid to the final centroid form the reflections matrix, edge reflections
        matrix, and the edge time matrix stored by the milestoning vertex.

    Returns:
        (float): The mean time of first passage from the 0th image to the final image.
        (list): `n_images - 1` mean times of passage from the 0th Voronoi cell to the final cell.
        (list): Respective equilibrium probabilities to find the system in each Voronoi cell.

    TODO: Convert the final frequency to THz?
    """

    def command(self, time_step, reflections_matrix, edge_reflections_matrix, edge_time_matrix, n_images,
                temperature):
        n_edges = int(n_images * (n_images - 1) / 2)
        reflections_matrix = np.sum(reflections_matrix, axis=0)
        edge_reflections_matrix = np.sum(edge_reflections_matrix, axis=0)
        edge_time_matrix = np.sum(edge_time_matrix, axis=0)
        pis = self._get_pi(reflections_matrix, n_images)
        free_energies = -KB * temperature * np.log(pis)

        # for terminology, refer the following paper: https://doi.org/10.1063/1.3129843
        n_ij = np.zeros((n_edges, n_edges))
        r_i = np.zeros(n_edges)
        for img in np.arange(n_images):
            n = pis[img] * edge_reflections_matrix[img]
            r = pis[img] * edge_time_matrix[img]
            n_ij += n
            r_i += r

        # The paper uses shows ways to calculate the mean free passage time. The following section is
        # commented out, as it is redundant. May come in handy for a consistency check?

        # q_ij = []
        # for i in np.arange(n_edges):
        #     if r_i[i] != 0:
        #         q_ij += [n_ij[i] / r_i[i]]
        #     else:
        #         q_ij += [np.zeros(n_edges)]
        #
        # q_ij = np.array(q_ij)

        p_ij = []
        tau_i = []
        n_ji = n_ij.T
        with np.errstate(invalid='ignore'):  # just ignores the divide by zero error
            for i in np.arange(n_edges):
                p_ij += [n_ji[i] / np.sum(n_ji[i])]
                tau_i += [r_i[i] / np.sum(n_ji[i])]
        for i in np.arange(n_edges):
            for j in np.arange(n_edges):
                if np.isnan(p_ij[i][j]):
                    p_ij[i][j] = 0
                    tau_i[i] = 0
        p_ij = np.array(p_ij)
        p_new = np.delete(p_ij, n_edges - 1, 0)
        p_new = np.delete(p_new, n_edges - 1, 1)
        tau_new = np.delete(tau_i, n_edges - 1, 0)

        t_n = np.linalg.lstsq(np.eye(n_edges - 1) - p_new, tau_new, rcond=None)[0] * time_step * femto

        summation = 0
        mean_first_passage_times = [t_n[summation]]
        for i in np.arange(1, len(t_n)):
            summation += i
            if summation < len(t_n):
                mean_first_passage_times.append(t_n[summation])
        mean_first_passage_times = np.array(mean_first_passage_times)
        jump_frequencies = 1. / mean_first_passage_times

        return {
            'equilibrium_probability': pis,
            'free_energies': free_energies,
            'jump_frequencies': jump_frequencies,
            'mean_first_passage_times': mean_first_passage_times,
            'reflections_matrix': reflections_matrix,
            'edge_reflections_matrix': edge_reflections_matrix,
            'edge_time_matrix': edge_time_matrix,
        }

    @staticmethod
    def _get_pi(reflections_matrix, n_images):
        dia = np.eye(n_images) * np.sum(reflections_matrix, axis=1)
        pi_mat_a = np.append(reflections_matrix.T - dia, [np.ones(n_images)], axis=0)
        pi_vec_b = np.append(np.zeros(n_images), [1])

        return np.linalg.lstsq(pi_mat_a, pi_vec_b, rcond=None)[0]