from pyiron_contrib.protocol.generic import CompoundVertex, Protocol
from pyiron_contrib.protocol.primitive.one_state import Counter, ExternalHamiltonian, Max, Norm, BFGS
from pyiron_contrib.protocol.primitive.two_state import IsGEq
from pyiron_contrib.protocol.utils import Pointer


class MinimizeBFGS(CompoundVertex):
    """
    Run minimization with Lammps. This isn't physically useful, since a regular lammps job is faster it's just a dummy
    class for debugging new code and teaching ideas.

    Input attributes:
        ref_job_full_path (str): Path to the pyiron job to use for evaluating forces and energies.
        structure (Atoms): The structure to minimize.
        n_steps (int): How many steps to run for. (Default is 100.)
        f_tol (float): Ionic force convergence (largest atomic force). (Default is 1e-4 eV/angstrom.)
        gamma0 (float): Initial step size as a multiple of the force. (Default is 0.1.)
        fix_com (bool): Whether the center of mass motion should be subtracted off of the position update. (Default is
            True)
        use_adagrad (bool): Whether to have the step size decay according to adagrad. (Default is False)

    Output attributes:
        energy_pot (float): Total potential energy of the system in eV.
        max_force (float): The largest atomic force magnitude in eV/angstrom.
        positions (numpy.ndarray): Atomic positions in angstroms.
        forces (numpy.ndarray): Atomic forces in eV/angstrom. Note: These are the potential gradient forces; thermostat
            forces (if any) are not saved.
    """

    DefaultWhitelist = {
        'calc_static': {
            'output': {
                'energy_pot': 1
            }
        },
        'max_force': {
            'output': {
                'amax': 1
            }
        }
    }

    def __init__(self, **kwargs):
        super(MinimizeBFGS, self).__init__(**kwargs)

        # Protocol defaults
        id_ = self.input.default
        id_.n_steps = 100
        id_.f_tol = 1e-4
        id_.gamma0 = 0.1
        id_.fix_com = True
        id_.use_adagrad = False

    def define_vertices(self):
        # Graph components
        g = self.graph
        g.calc_static = ExternalHamiltonian()
        g.clock = Counter()
        g.check_steps = IsGEq()
        g.force_norm = Norm()
        g.max_force = Max()
        g.check_force = IsGEq()
        g.gradient_descent = BFGS()

    def define_execution_flow(self):
        # Execution flow
        g = self.graph
        g.make_pipeline(
            g.check_steps, 'false',
            g.calc_static,
            g.force_norm,
            g.max_force,
            g.check_force, 'true',
            g.gradient_descent,
            g.clock,
            g.check_steps
        )
        g.starting_vertex = self.graph.check_steps
        g.restarting_vertex = self.graph.check_steps

    def define_information_flow(self):
        # Data flow
        g = self.graph
        gp = Pointer(self.graph)
        ip = Pointer(self.input)

        g.calc_static.input.ref_job_full_path = ip.ref_job_full_path
        g.calc_static.input.structure = ip.structure
        g.calc_static.input.positions = gp.gradient_descent.output.positions[-1]

        g.check_steps.input.target = gp.clock.output.n_counts[-1]
        g.check_steps.input.threshold = ip.n_steps

        g.force_norm.input.x = gp.calc_static.output.forces[-1]
        g.force_norm.input.ord = 2
        g.force_norm.input.axis = -1

        g.max_force.input.a = gp.force_norm.output.n[-1]

        g.check_force.input.target = gp.max_force.output.amax[-1]
        g.check_force.input.threshold = ip.f_tol

        g.gradient_descent.input.default.positions = ip.structure.positions
        g.gradient_descent.input.forces = gp.calc_static.output.forces[-1]
        g.gradient_descent.input.positions = gp.gradient_descent.output.positions[-1]


        self.set_graph_archive_clock(gp.clock.output.n_counts[-1])

    def get_output(self):
        gp = Pointer(self.graph)
        return {
            'energy_pot': ~gp.calc_static.output.energy_pot[-1],
            'max_force': ~gp.max_force.output.amax[-1],
            'positions': ~gp.gradient_descent.output.positions[-1],
            'forces': ~gp.calc_static.output.forces[-1]
        }


class ProtocolMinimizeBFGS(Protocol, MinimizeBFGS):
    pass
