
from pyiron import Project
from pyiron.base.job.jobtype import JOB_CLASS_DICT

# Make classes available for new pyiron version
JOB_CLASS_DICT['ProtoMinimize'] = 'pyiron_contrib.protocol.compound.minimize'
JOB_CLASS_DICT['ProtoMD'] = 'pyiron_contrib.protocol.compound.md'
JOB_CLASS_DICT['ProtoHarmonicMD'] = 'pyiron_contrib.protocol.compound.md'
JOB_CLASS_DICT['ProtoConfinedMD'] = 'pyiron_contrib.protocol.compound.md'
JOB_CLASS_DICT['ProtoConfinedHarmonicMD'] = 'pyiron_contrib.protocol.compound.md'
JOB_CLASS_DICT['ProtoNEB'] = 'pyiron_contrib.protocol.compound.neb'
JOB_CLASS_DICT['ProtoNEBParallel'] = 'pyiron_contrib.protocol.compound.neb'
JOB_CLASS_DICT['ProtoQMMM'] = 'pyiron_contrib.protocol.compound.qmmm'
JOB_CLASS_DICT['ProtoHarmonicTILD'] = 'pyiron_contrib.protocol.compound.tild'
JOB_CLASS_DICT['ProtoHarmonicTILDParallel'] = 'pyiron_contrib.protocol.compound.tild'
JOB_CLASS_DICT['ProtoVacancyTILD'] = 'pyiron_contrib.protocol.compound.tild'
JOB_CLASS_DICT['ProtoVacancyTILDParallel'] = 'pyiron_contrib.protocol.compound.tild'
JOB_CLASS_DICT['ProtoStringEvolution'] = 'pyiron_contrib.protocol.compound.fts'
JOB_CLASS_DICT['ProtoStringEvolutionParallel'] = 'pyiron_contrib.protocol.compound.fts'
JOB_CLASS_DICT['ImageJob'] = 'pyiron_contrib.image.job'
JOB_CLASS_DICT['ProtoATILDParallel'] = 'pyiron_contrib.protocol.compound.tild'
