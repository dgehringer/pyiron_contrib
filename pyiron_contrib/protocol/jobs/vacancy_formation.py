# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import numpy as np
from pyiron_atomistics import Project
from pyiron_contrib.protocol.jobs.vacancy_formation_utility import GenericInput, MDInput, PhononInput
from pyiron_contrib.protocol.jobs.alchemical_vacancy_formation import Alchemical, ThermalExpansion, Phonons
from pyiron_base.generic.datacontainer import DataContainer

__author__ = "Raynol Dsouza"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Raynol Dsouza"
__email__ = "dsouza@mpie.de"
__status__ = "development"
__date__ = "August 02, 2021"


class VacancyFormation:

    def __init__(self, project):
        super().__init__()
        self.project = Project(project)
        self.thermal_exp = ThermalExpansion(project=self.project)
        self.phonon = Phonons(project=self.project)
        # self.alchemical = Alchemical(project=self.project.create_group("alchemical"))
        self.input = DataContainer(table_name='job_input')
        self.input.generic = GenericInput(table_name='generic_input')
        self.input.md = MDInput(table_name='md_input')
        self.input.phon = PhononInput(table_name='phon_input')

    def run_bulk_thermal_expansion(self):
        self.thermal_exp.input.generic = self.input.generic
        self.thermal_exp.input.md = self.input.md
        self.thermal_exp.run_thermal_expansion(group='bulk')

    def process_phase_1(self):
        a = self.thermal_exp.process_thermal_expansion(group='bulk', thermalize_snapshots=20, n_bins=1000)
        return a[2]

    def minimize_structures(self):
        self.phonon.input.generic = self.input.generic
        self.phonon.input.phon = self.input.phon
        self.phonon.minimize_structures(lattice_constants=None, strain=True)
