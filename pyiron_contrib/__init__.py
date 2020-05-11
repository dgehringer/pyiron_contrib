# from pyiron_contrib.protocol.generic import Protocol
from pyiron_contrib.protocol.compound.minimize import ProtocolMinimize
from pyiron_contrib.protocol.compound.molecular_dynamics import ProtocolMD, ProtocolConfinedMD, \
    ProtocolConfinedHarmonicMD
from pyiron_contrib.protocol.compound.nudged_elastic_band import ProtocolNEB, ProtocolNEBParallel
# from pyiron_contrib.protocol.compound.tild import HarmonicTILD, VacancyTILD
from pyiron_contrib.protocol.compound.finite_temperature_string import ProtocolStringEvolution, \
    ProtocolVirtualWork, ProtocolVirtualWorkParallel, ProtocolStringEvolutionParallel
from pyiron_contrib.protocol.compound.qmmm import ProtocolQMMM
from pyiron_contrib.protocol.compound.tild import ProtocolHarmonicTILD, ProtocolVacancyTILD, \
    ProtocolHarmonicTILDParallel

# protocol is a magic class after this one we have to Register
# from pyiron_contrib.protocol.utils.types import PyironJobTypeRegistryMetaType
# PyironJobTypeRegistryMetaType.inject_dynamic_types()
__all__ = [
    'ProtocolMinimize',
    'ProtocolMD', 'ProtocolConfinedMD', 'ProtocolConfinedHarmonicMD',
    'ProtocolNEB', 'ProtocolNEBParallel',
    'ProtocolQMMM',
    'ProtocolHarmonicTILD', 'ProtocolVacancyTILD', 'ProtocolHarmonicTILDParallel',
    'ProtocolStringEvolution', 'ProtocolVirtualWork', 'ProtocolVirtualWorkParallel',
    'ProtocolStringEvolutionParallel'
]
