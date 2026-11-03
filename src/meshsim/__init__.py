"""Physics-based testing for 3D designs."""

from ._meta import PROJECT_NAME, __version__
from .config import SimConfig
from .environments import ENVIRONMENTS, Environment, make_environment, register_environment
from .mesh import compute_body_properties, load_mesh
from .simulation import Simulation, SimulationResult

__all__ = [
    "ENVIRONMENTS",
    "PROJECT_NAME",
    "Environment",
    "SimConfig",
    "Simulation",
    "SimulationResult",
    "__version__",
    "compute_body_properties",
    "load_mesh",
    "make_environment",
    "register_environment",
]
