"""Built-in environments and a small registry."""

from __future__ import annotations

from typing import Any

from .base import Environment, Param, SpawnFrame
from .drop import DropTest
from .flat import FlatGround
from .ramp import Ramp
from .terrain import Terrain, load_heightmap

ENVIRONMENTS: dict[str, type[Environment]] = {}


def register_environment(cls: type[Environment]) -> type[Environment]:
    """Register an Environment subclass under ``cls.name``. Usable as a decorator."""
    ENVIRONMENTS[cls.name] = cls
    return cls


for _cls in (FlatGround, Ramp, DropTest, Terrain):
    register_environment(_cls)


def make_environment(env: str | Environment, params: dict[str, Any] | None = None) -> Environment:
    if isinstance(env, Environment):
        if params:
            raise ValueError("Pass parameters to the Environment constructor, not as env_params")
        return env
    if env not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment '{env}'. Available: {', '.join(sorted(ENVIRONMENTS))}")
    return ENVIRONMENTS[env](**(params or {}))


__all__ = [
    "ENVIRONMENTS",
    "DropTest",
    "Environment",
    "FlatGround",
    "Param",
    "Ramp",
    "SpawnFrame",
    "Terrain",
    "load_heightmap",
    "make_environment",
    "register_environment",
]
