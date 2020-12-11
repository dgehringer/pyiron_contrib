# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

"""
A job class for performing finite element simulations using the [FEniCS](https://fenicsproject.org) code.
"""

import fenics as FEN
import mshr
from pyiron_base import GenericJob, InputList, PyironFactory
from os.path import join
import warnings

__author__ = "Muhammad Hassani, Liam Huber"
__copyright__ = (
    "Copyright 2020, Max-Planck-Institut für Eisenforschung GmbH - "
    "Computational Materials Design (CM) Department"
)
__version__ = "0.1"
__maintainer__ = "Muhammad Hassani"
__email__ = "hassani@mpie.de"
__status__ = "development"
__date__ = "Dec 6, 2020"


class Fenics(GenericJob):
    """
    The job provides an interface to the [FEniCS project](https://fenicsproject.org) PDE solver using the finite element
    method (FEM).

    The objective is to streamline and simplify regular usage and connect FEniCS calculations to the full job management
    and execution distribution capabilities of pyiron, without losing the power or flexibility of the underlying fenics
    library.

    Flexibility and power are currently maintained by directly exposing the underlying `fenics` and `mshr` libraries as
    attributes of the job for power users.

    Ease of use is underway, e.g. elements, trial and test functions, and the mesh are automatically populated based on
    the provided domain. Quality of life will be continuously improved as pyiron and fenics get to know each other.

    TODO: Integration with pyiron's job and data management is incomplete, as some input data types (domains and
          boundary conditions) are not yet compatible with HDF5 storage. This is a simple problem to describe, but might
          be a pain to solve with sufficient flexibility. We also need to consider storing more sophisticated output.

    TODO: Full power and flexibility still needs to be realized by allowing (a) variable function space types, (b)
          variable number of elements and trial/test functions, and (c) multiple solve types.
          (a) Is a simple input option, we just need to be smart about how to limit the choices to existing fenics
              classes.
          (b) Can probably be nicely realized by subclassing off the main job type to allow for two sets of functions --
              `V:(u,v), Q:(p,q)` -- and a variable number of functions -- `V[0]:(u[0], v[0]),...,V[n]:(u[n], v[n])` --
              which are automatically populated during mesh generation and which are accessible for building the
              equation.
          (c) Solution types just means linear system `solve(A, x, b, ...)`, linear variational problems
              `solve(a == L, u, ...)`, and nonlinear variational problems `solve(F == 0, u, ...)`. This is probably also
              going to be pretty easy to control through an input parameter with a few fixed options an a bit of
              modification to how the LHS and RHS of equations are provided, and what actually is called during `run`.
              Currently the linear variational problem is hardcoded.

    Attributes:
        input (InputList): The input parameters controlling the run.
        output (InputList): The output from the run, i.e. data that comes from `solve`ing the PDE.
        domain (?): The spatial domain on which to build the mesh. To be provided prior to running the job.
        BC (?): The boundary conditions for the mesh. To be provided prior to running the job.

    Input:
        mesh_resolution (int): How dense the mesh should be (larger values = denser mesh). (Default is 2.)
        element_type (str): What type of element should be used. (Default is 'P'.) TODO: Restrict choices.
        element_order (int): What order the elements have. (Default is 1.)  TODO: Better description.

    Output:
        u (numpy.ndarray): The solved function values evaluated at the mesh points.

    Example:
        >>> job = pr.create.job.Fenics('fenics_job')
        >>> job.input.mesh_resolution = 64
        >>> job.input.element_type = 'P'
        >>> job.input.element_order = 2
        >>> job.domain = job.create.domain.circle((0, 0), 1)
        >>> job.BC = job.create.bc.dirichlet_bc(job.Constant(0))
        >>> p = job.Expression('4*exp(-pow(beta, 2)*(pow(x[0], 2) + pow(x[1] - R0, 2)))', degree=1, beta=8, R0=0.6)
        >>> job.LHS = job.dot(job.grad(job.u), job.grad(job.v)) * job.dx
        >>> job.RHS = p * job.v * job.dx
        >>> job.run()
        >>> job.plot_u()
    """

    def __init__(self, project, job_name):
        super(Fenics, self).__init__(project, job_name)
        self._python_only_job = True
        self.create = Creator(self)

        self.input = InputList(table_name='input')
        self.input.mesh_resolution = 2
        self.input.element_type = 'P'
        self.input.element_order = 1
        # TODO?: Make input sub-classes to catch invalid input?

        self.output = InputList(table_name='output')
        self.output.u = None

        self.domain = self.create.domain()  # the domain  TODO: Get this into the input and saving/loading properly
        self.BC = None  # the boundary condition  TODO: Get this into the input and saving/loading properly
        self.LHS = None  # the left hand side of the equation; FEniCS function
        self.RHS = None  # the right hand side of the equation; FEniCS function
        # TODO: Get LHS and RHS into the input and saving/loading properly
        #       (maybe with a softlink directly at the job level given the importance of this feature?

        self._mesh = None  # the discretization mesh
        self._V = None  # finite element volume space
        self._u = None  # u is the unkown function
        self._v = None  # the test function
        self._vtk_filename = join(self.project_hdf5.path, 'output.pvd')

    def generate_mesh(self):
        if any([v is not None for v in [self.BC, self.LHS, self.RHS]]):
            warnings.warn("The mesh is being generated, but at least one of the boundary conditions or equation sides"
                          "is already defined -- please re-define these values since the mesh is updated")
        self._mesh = mshr.generate_mesh(self.domain, self.input.mesh_resolution)
        # TODO?: Accommodate uniform meshes like fenics.SquareMesh?
        self._V = FEN.FunctionSpace(self.mesh, self.input.element_type, self.input.element_order)
        # TODO: Allow changing what type of function space is used (VectorFunctionSpace, MultiMeshFunctionSpace...)
        # TODO: Allow having multiple sets of spaces and test/trial functions
        self._u = FEN.TrialFunction(self.V)
        self._v = FEN.TestFunction(self.V)

    def refresh(self):
        self.generate_mesh()

    @property
    def mesh(self):
        if self._mesh is None:
            self.refresh()
        return self._mesh

    @property
    def V(self):
        if self._V is None:
            self.refresh()
        return self._V

    @property
    def u(self):
        if self._u is None:
            self.refresh()
        return self._u

    @property
    def v(self):
        if self._v is None:
            self.refresh()
        return self._v
    # TODO: Do all this refreshing with a simple decorator instead of duplicate code

    @property
    def F(self):
        try:
            return self.LHS - self.RHS
        except TypeError:
            return self.LHS

    @F.setter
    def F(self, new_equation):
        self.LHS = FEN.lhs(new_equation)
        self.RHS = FEN.rhs(new_equation)

    def _write_vtk(self):
        """
        Write the output to a .vtk file.
        """
        vtkfile = FEN.File(self._vtk_filename)
        vtkfile << self.u

    def validate_ready_to_run(self):
        if self.mesh is None:
            raise ValueError("No mesh is defined")
        if self.RHS is None:
            raise ValueError("The bilinear form (RHS) is not defined")
        if self.LHS is None:
            raise ValueError("The linear form (LHS) is not defined")
        if self.V is None:
            raise ValueError("The volume is not defined; no V defined")
        if self.BC is None:
            raise ValueError("The boundary condition(s) (BC) is not defined")

    def run_static(self):
        """
        Solve a PDE based on 'LHS=RHS' using u and v as trial and test function respectively. Here, u is the desired
        unknown and RHS is the known part.
        """
        self.status.running = True
        self._u = FEN.Function(self.V)
        FEN.solve(self.LHS == self.RHS, self.u, self.BC)
        self.status.collect = True
        self.run()

    def collect_output(self):
        self.output.u = self.u.compute_vertex_values(self.mesh)
        self._write_vtk()  # TODO: Get the output files so they're all tarballed after successful runs, like other codes
        self.to_hdf()
        self.status.finished = True
    
    def plot_u(self):
        FEN.plot(self.u)

    def plot_mesh(self):
        FEN.plot(self.mesh)

    def to_hdf(self, hdf=None, group_name=None):
        super().to_hdf(hdf=hdf, group_name=group_name)
        self.input.to_hdf(hdf=self.project_hdf5)
        self.output.to_hdf(hdf=self.project_hdf5)

    def from_hdf(self, hdf=None, group_name=None):
        super().from_hdf(hdf=hdf, group_name=group_name)
        self.input.from_hdf(hdf=self.project_hdf5)
        self.output.from_hdf(hdf=self.project_hdf5)

    # Convenience bindings:
    @property
    def fenics(self):
        return FEN

    @property
    def mshr(self):
        return mshr

    def grad(self, arg):
        return FEN.grad(arg)
    grad.__doc__ = FEN.grad.__doc__  # TODO: Is there a nice way to do this with a decorator?

    def Constant(self, value):
        return FEN.Constant(value)
    Constant.__doc__ = FEN.Constant.__doc__

    def dot(self, arg1, arg2):
        return FEN.dot(arg1, arg2)
    dot.__doc__ = FEN.dot.__doc__

    @property
    def dx(self):
        return FEN.dx
    dx.__doc__ = FEN.dx.__doc__

    def Expression(self, *args, **kwargs):
        return FEN.Expression(*args, **kwargs)
    Expression.__doc__ = FEN.Expression.__doc__


class Creator:
    def __init__(self, job):
        self._job = job
        self._domain = DomainFactory()
        self._bc = BoundaryConditionFactory(job)

    @property
    def domain(self):
        return self._domain

    @property
    def bc(self):
        return self._bc


class DomainFactory(PyironFactory):

    def circle(self, center, radius):
        return mshr.Circle(FEN.Point(*center), radius)
    circle.__doc__ = mshr.Circle.__doc__

    def square(self, length, origin=None):
        if origin is None:
            x, y = 0, 0
        else:
            x, y = origin[0], origin[1]
        return mshr.Rectangle(FEN.Point(0 + x, 0 + y), FEN.Point(length + x, length + y))
    square.__doc__ = mshr.Rectangle.__doc__

    def __call__(self):
        return self.square(1.)


class BoundaryConditionFactory(PyironFactory):
    def __init__(self, job):
        self._job = job

    @staticmethod
    def _default_bc_fnc(x, on_boundary):
        return on_boundary

    def dirichlet_bc(self, expression, bc_fnc=None):
        """
        This function defines Dirichlet boundary condition based on the given expression on the boundary.

        Args:
            expression (string): The expression used to evaluate the value of the unknown on the boundary.
            bc_fnc (fnc): The function which evaluates which nodes belong to the boundary to which the provided
                expression is applied as displacement.
        """
        bc_fnc = bc_fnc or self._default_bc_fnc
        return FEN.DirichletBC(self._job.V, expression, bc_fnc)
