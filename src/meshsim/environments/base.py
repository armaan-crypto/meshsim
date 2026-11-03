"""Base class for simulation environments."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np

from .._bullet import p

GROUND_RGBA = [0.75, 0.75, 0.72, 1.0]
SURFACE_RGBA = [0.45, 0.55, 0.70, 1.0]


@dataclass(frozen=True)
class Param:
    default: Any
    help: str


@dataclass
class SpawnFrame:
    """Where to place the object at t=0.

    The object is oriented with ``orientation`` (then the user's initial
    orientation on top), and positioned so its lowest point along the frame's
    local +Z axis sits ``gap`` meters above ``origin``.
    """

    origin: np.ndarray
    orientation: np.ndarray
    gap: float


class Environment(ABC):
    """A static world the object is dropped into.

    Subclasses set ``name``, ``description`` and ``params`` and implement
    ``build`` (create static bodies) and ``spawn_frame``.

    Contact friction and restitution in Bullet are the product of the two
    bodies' values. Surfaces default to 1.0 so the object's own friction and
    restitution are the effective values unless a surface value is changed.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    params: ClassVar[dict[str, Param]]

    def __init__(self, **values: Any) -> None:
        unknown = set(values) - set(self.params)
        if unknown:
            raise ValueError(
                f"Unknown parameter(s) for the '{self.name}' environment: {', '.join(sorted(unknown))}. "
                f"Valid: {', '.join(sorted(self.params)) or '(none)'}"
            )
        self.values = {key: spec.default for key, spec in self.params.items()}
        self.values.update(values)
        self.validate()

    def __getattr__(self, item: str) -> Any:
        values = self.__dict__.get("values", {})
        if item in values:
            return values[item]
        raise AttributeError(item)

    def validate(self) -> None:  # noqa: B027 - optional hook, not abstract
        """Raise ValueError for invalid parameter values."""

    @abstractmethod
    def build(self, client) -> None:
        """Create the environment's static bodies in a PyBullet client."""

    @abstractmethod
    def spawn_frame(self, client) -> SpawnFrame:
        """Return where the object starts. Called after ``build``."""

    def describe(self) -> dict[str, Any]:
        def safe(value: Any) -> Any:
            if isinstance(value, np.ndarray):
                return f"<array shape={list(value.shape)}>"
            return value

        return {"name": self.name, "params": {k: safe(v) for k, v in self.values.items()}}


def require_positive(env: Environment, *names: str) -> None:
    for name in names:
        if env.values[name] <= 0:
            raise ValueError(f"{env.name}: {name} must be > 0, got {env.values[name]}")


def require_non_negative(env: Environment, *names: str) -> None:
    for name in names:
        if env.values[name] < 0:
            raise ValueError(f"{env.name}: {name} must be >= 0, got {env.values[name]}")


def set_surface(client, body: int, friction: float, restitution: float) -> None:
    client.changeDynamics(body, -1, lateralFriction=friction, restitution=restitution)


def add_ground(client, friction: float, restitution: float, size: float = 100.0) -> int:
    """Infinite collision plane at z=0 with a large visible slab for rendering."""
    collision = client.createCollisionShape(p.GEOM_PLANE)
    visual = client.createVisualShape(
        p.GEOM_BOX,
        halfExtents=[size / 2, size / 2, 0.01],
        visualFramePosition=[0, 0, -0.01],
        rgbaColor=GROUND_RGBA,
    )
    body = client.createMultiBody(baseMass=0, baseCollisionShapeIndex=collision, baseVisualShapeIndex=visual)
    set_surface(client, body, friction, restitution)
    return body


IDENTITY = np.array([0.0, 0.0, 0.0, 1.0])
