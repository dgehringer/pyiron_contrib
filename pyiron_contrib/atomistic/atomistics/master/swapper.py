from pyiron.atomistics.job.interactivewrapper import InteractiveWrapper
from pyiron_base import InputList, ParallelMaster, JobGenerator
from pyiron_base.master.flexible import FlexibleMaster
from pyiron.atomistics.job.interactive import GenericInteractive
import numpy as np

"""
Job classes for seeing how the potential energy changes when you swap species in a binary way at many different sites.
The intent is to use this to estimate semi-grand-canonical chemical potential targets.
"""


class SpeciesSwapper(InteractiveWrapper):
    """
    Using a given structure, swaps two species multiple times (reverting back to the original chemistry each time) and
    evaluates the resulting change in energy. Swaps in both directions are checked, but the swapping is directional
    and the energy change is reversed for reverse swaps.

    The intent is to approximate the chemical potential difference between two species in a complex structure by a
    series of static calculations.

    Attributes:
        ref_job (pyiron.atomistics.job.interactive.GenericInteractive): The reference -- including structure to alter.
        input (pyiron_base.InputList): The input.
        output (pyiron_base.InputList): The output.

    Input:
        swap_to (str): The symbol of the species to change *to* when finding ids to swap and evaluating the energy
            difference.
        swap_from (str): The symbol of the species to change *from* when finding ids to swap and evaluating the energy
            difference.
        n_swaps (int): How many swaps to perform. These will be chosen randomly but proportionally from available
            forward and reverse swaps. Must not be more than the sum total of all sites belonging to either the
            forward or reverse species! (Default is 3.)

    Output:
        swap_energies (numpy.ndarray): The energies (or negative energy for reverse swaps) of swapping the species at
            the randomly chosen sites.

    Warning:
        There must be at least two of all species in the cell. This is because Lammps will complain if a species goes
        totally missing, and instead of taking careful care of this I just fail early. Feel free to improve the class
        by fixing this constraint, I'm pretty sure it's possible.
    """
    def __init__(self, project, job_name):
        super().__init__(project, job_name)
        self.__name__ = "SpeciesSwapper"
        self.__version__ = "0.1"
        self.__hdf_version__ = "0.2.0"
        self._ref_job = None

        self.input = InputList(table_name='input')
        self.input.swap_to = None
        self.input.swap_from = None
        self.input.n_swaps = 3

        self.output = InputList(table_name='output')
        self.output.forward_swap_energies = None
        self.output.reverse_swap_energies = None

        self._python_only_job = True  # So I don't need to implement write_input, because our architecture is dumb.

        self._n_forward_swaps = None
        self._n_reverse_swaps = None

    def validate_ready_to_run(self):
        super().validate_ready_to_run()
        if not isinstance(self.ref_job, GenericInteractive):
            raise ValueError("Reference job must inherit from GenericInteractive but got {}".format(
                type(GenericInteractive))
            )

        n_swaps_available = len(self._forward_ids) + len(self._reverse_ids)
        if self.input.n_swaps > n_swaps_available:
            raise ValueError("input n_swaps was {}, but only {} swaps are available between {} and {}".format(
                self.input.n_swaps,
                n_swaps_available,
                self.input.swap_from,
                self.input.swap_to
            ))

        # The method breaks if a species that was there at one point totally disappears
        # Instead of fixing it, I will just patch over it with an early exception, since I know this doesn't effect
        # my current situation and I'm pressed for time. It's a bit douchy, but at least it fails honestly this way
        if np.any([v[1] < 2 for v in self.ref_job.structure.get_number_species_atoms().items()]):
            raise ValueError("This method only works when there are at least two of every type of atom.")

        old_ref = self.pop(-1)
        new_ref = old_ref.copy_to(
            project=self.project_hdf5,
            new_database_entry=False,
            new_job_name=self.job_name + '_c'
        )
        self._ref_job = new_ref

    @property
    def _forward_ids(self):
        return self._get_element_ids(self.input.swap_from)

    @property
    def _reverse_ids(self):
        return self._get_element_ids(self.input.swap_to)

    def _get_element_ids(self, target_symbol):
        return np.where(self.ref_job.structure.get_chemical_symbols() == target_symbol)[0]

    def run_static(self):
        self.status.running = True

        self.ref_job_initialize()
        self.ref_job.calc_static()
        self.ref_job.interactive_open()
        self.ref_job.run()  # Reference energy before any swapping

        forward_swap_ids, reverse_swap_ids = self._get_swap_ids()
        self._run_forwards_swaps(forward_swap_ids)
        self._run_reverse_swaps(reverse_swap_ids)

        self.ref_job.interactive_close()
        self.ref_job.to_hdf()
        self.status.collect = True
        self.collect_output()

    def _get_swap_ids(self):
        n_forward = len(self._forward_ids)
        n_reverse = len(self._reverse_ids)
        if n_forward > n_reverse:
            self._n_forward_swaps = min(n_forward, int(0.5 * self.input.n_swaps))
            self._n_reverse_swaps = self.input.n_swaps - self._n_forward_swaps
        else:
            self._n_reverse_swaps = min(n_reverse, int(0.5 * self.input.n_swaps))
            self._n_forward_swaps = self.input.n_swaps - self._n_reverse_swaps

        if self._n_forward_swaps > n_forward or self._n_reverse_swaps > n_reverse:
            raise ValueError("Too many swaps requested.")

        return (
            np.random.choice(self._forward_ids, self._n_forward_swaps, replace=False),
            np.random.choice(self._reverse_ids, self._n_reverse_swaps, replace=False)
        )

    def _run_forwards_swaps(self, ids):
        self._swap_and_run(ids, self.input.swap_to, self.input.swap_from)

    def _run_reverse_swaps(self, ids):
        self._swap_and_run(ids, self.input.swap_from, self.input.swap_to)

    def _swap_and_run(self, ids, swap_to, swap_back_to):
        for i in ids:
            self.ref_job.structure[i] = swap_to
            self.ref_job.run()
            self.ref_job.structure[i] = swap_back_to

    def collect_output(self):
        ref_energy = self.ref_job.output.energy_pot[0]
        forward_energies = self.ref_job.output.energy_pot[1:self._n_forward_swaps + 1]
        reverse_energies = self.ref_job.output.energy_pot[self._n_forward_swaps + 1:]

        self.output.forward_swap_energies = np.sort(forward_energies - ref_energy)
        self.output.reverse_swap_energies = np.sort(reverse_energies - ref_energy)
        self.output.to_hdf(self.project_hdf5)
        self.status.finished = True

    def to_hdf(self, hdf=None, group_name=None):
        """
        Store the SpeciesSwapper in an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        super().to_hdf(hdf=hdf, group_name=group_name)
        self.output.to_hdf(self.project_hdf5)

    def from_hdf(self, hdf=None, group_name=None):
        """
        Restore the SpeciesSwapper from an HDF5 file.

        Args:
            hdf (ProjectHDFio): HDF5 group object - optional
            group_name (str): HDF5 subgroup name - optional
        """
        super().from_hdf(hdf=hdf, group_name=group_name)
        self.output.from_hdf(self.project_hdf5)


class _SpeciesSwapperGenerator(JobGenerator):
    """Generates jobs with different compositions."""

    @property
    def parameter_list(self):
        return self._master.input.positions

    def modify_job(self, job, parameter):
        job.structure.positions = parameter
        return job

    def job_name(self, parameter):
        return '_'.join([self._master.ref_job.job_name, str(self._childcounter)])


class PSpeciesSwapper(ParallelMaster):
    """
    Runs a series of species swaps over different positions.

    The intent is to approximate the chemical potential by using species swapping over snapshots from an MD trajectory.

    Attributes:
        ref_job (SpeciesSwapper): The reference job, with its own respective reference.
        input (pyiron_base.InputList): The input.
        output (pyiron_base.OutputList): The output.

    Input:
        positions (numpy.ndarray): (n_frames, n_atoms, 3) particle coordinates. Warning: The number of atoms *must*
            match the number in the structure of the reference job's underlying reference job!

    Output:
        swap_energies (numpy.ndarray): The flattened swapping results across all swaps for all positions frames.
    """
    def __init__(self, project, job_name):
        super().__init__(project, job_name=job_name)
        self.__name__ = "PSpeciesSwapper"
        self.__version__ = "0.1"
        self.__hdf_version__ = "0.2.0"

        self.input = InputList(table_name='input')
        self.input.positions = None
        self.output = InputList(table_name='output')
        self.output.forward_swap_energies = None
        self.output.reverse_swap_energies = None

        self._job_generator = _SpeciesSwapperGenerator(self)
        self._python_only_job = True

    def validate_ready_to_run(self):
        if not self.input.positions.shape[1] == len(self.ref_job.ref_job.structure):
            raise ValueError("Positions must have same shape as underlying reference.")
        super().validate_ready_to_run()

    def to_hdf(self, hdf=None, group_name=None):
        super().to_hdf(hdf, group_name)
        self.input.to_hdf(self._hdf5)
        self.output.to_hdf(self._hdf5)

    def from_hdf(self, hdf=None, group_name=None):
        super().from_hdf(hdf, group_name)
        self.input.from_hdf(self._hdf5)
        self.output.from_hdf(self._hdf5)
        self.collect_output()

    def collect_output(self):
        self.output.forward_swap_energies = np.sort(
            np.array([job['output/data']['forward_swap_energies'] for job in self._children]).flatten()
        )
        self.output.reverse_swap_energies = np.sort(
            np.array([job['output/data']['reverse_swap_energies'] for job in self._children]).flatten()
        )
        self.output.to_hdf(self.project_hdf5)

    @property
    def _children(self):
        return [self[self.child_names[n]] for n in np.sort(self.child_ids)]


def _md2swap(md_job, swap_master):
    swap_master.input.positions = md_job.output.positions[1:]


class ChemPotEstimator(FlexibleMaster):
    """
    A class for estimating the chemical potential difference between two species by swapping their identity one at a
    time in snapshots of an MD run.

    Attributes:
        ref_md (pyiron.atomistics.job.interactive.GenericInteractive): An MD reference job.
        ref_swap (PSpeciesSwapper): A reference job for swapping species (with its own underlying references filled).
        input (pyiron_base.InputList): Input.
        output (pyiron_base.InputList): Output.

    Input:

    Output:
        forward/reverse_swap_energies (numpy.ndarray): The energies of swapping the species at the randomly chosen
            sites.

    Warning:
        There must be at least two of all species in the cell. This is because Lammps will complain if a species goes
        totally missing, and instead of taking careful care of this I just fail early. Feel free to improve the class
        by fixing this constraint, I'm pretty sure it's possible.
    """
    def __init__(self, project, job_name):
        super().__init__(project, job_name=job_name)
        self.__name__ = "ChemPotEstimator"
        self.__version__ = "0.1"
        self.__hdf_version__ = "0.2.0"

        self.ref_md = None
        self.ref_swap = None

        self.input = InputList(table_name='input')
        self.output = InputList(table_name='output')
        self.output.forward_swap_energies = None
        self.output.reverse_swap_energies = None
        self.output._swap_job_name = None

    def validate_ready_to_run(self):
        self._create_pipeline()
        super().validate_ready_to_run()

    def _create_pipeline(self):
        self.append(self._instantiate_md())
        self.function_lst.append(_md2swap)
        self.append(self._instantiate_swap())

    def _instantiate_md(self):
        md_job = self.ref_md.copy_to(
            project=self.project_hdf5,
            new_database_entry=False,
            new_job_name=self.job_name + '_md'
        )
        return md_job

    def _instantiate_swap(self):
        swap_master = self.ref_swap.copy_to(
            project=self.project_hdf5,
            new_database_entry=False,
            new_job_name=self.job_name + '_s'
        )
        self.output._swap_job_name = swap_master.job_name
        return swap_master

    def run_static(self):
        super().run_static()
        # Flexible master does not use output collection, but we want that so let's force the issue:
        self.status.collect = True
        self.run()

    def collect_output(self):
        if self.output._swap_job_name is not None:
            data = self.project.inspect(self.output._swap_job_name)['output/data']
            self.output.forward_swap_energies = data['forward_swap_energies']
            self.output.reverse_swap_energies = data['reverse_swap_energies']
            self.output.to_hdf(self.project_hdf5)

    def to_hdf(self, hdf=None, group_name=None):
        super().to_hdf(hdf, group_name)
        self.output.to_hdf(hdf=self.project_hdf5)

    def from_hdf(self, hdf=None, group_name=None):
        super().from_hdf(hdf, group_name)
        self.output.from_hdf(hdf=self.project_hdf5)
        try:
            self.collect_output()
        except TypeError:  # `NoneType` object is not subscriptable in collect output if the job is loaded before run
            pass
