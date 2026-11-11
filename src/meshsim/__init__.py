"""Physics-based testing for 3D designs."""

from ._meta import PROJECT_NAME, __version__
from .config import SimConfig
from .environments import ENVIRONMENTS, Environment, make_environment, register_environment
from .mesh import compute_body_properties, load_mesh
from .simulation import Simulation, SimulationResult
from .stability import TipResult, stable_poses, tip_angles

__all__ = [
    "ENVIRONMENTS",
    "PROJECT_NAME",
    "Environment",
    "SimConfig",
    "Simulation",
    "SimulationResult",
    "TipResult",
    "__version__",
    "compute_body_properties",
    "load_mesh",
    "make_environment",
    "register_environment",
    "stable_poses",
    "tip_angles",
]
