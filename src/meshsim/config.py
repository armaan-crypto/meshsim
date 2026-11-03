"""Simulation configuration: defaults, YAML loading and overrides.

Precedence, lowest to highest: built-in defaults < YAML file < explicit overrides
(CLI flags or keyword arguments to ``Simulation``).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any

import yaml

from ._meta import PROJECT_NAME


@dataclass(frozen=True)
class SimConfig:
    """All tunable simulation parameters. Units are SI (m, kg, s) unless noted."""

    env: str = "flat"
    """Environment name: flat, ramp, drop or terrain."""
    env_params: dict[str, Any] = field(default_factory=dict)
    """Environment-specific parameters, e.g. {"angle": 25} for the ramp."""

    duration: float = 5.0
    """Simulated time in seconds."""
    timestep: float = 1.0 / 240.0
    """Physics step in seconds. PyBullet is tuned for 1/240."""
    gravity: float = 9.81
    """Gravitational acceleration magnitude in m/s^2, acting along -Z."""

    scale: float = 1.0
    """Multiplier applied to mesh coordinates to get meters (0.001 for a mm STL)."""
    mass: float | None = None
    """Body mass in kg. If set, overrides density."""
    density: float = 1000.0
    """Material density in kg/m^3, used when mass is not set."""
    friction: float = 0.5
    """Object's lateral friction coefficient."""
    restitution: float = 0.2
    """Object's coefficient of restitution (bounciness), 0..1."""
    linear_damping: float = 0.0
    angular_damping: float = 0.0

    initial_orientation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Roll, pitch, yaw in degrees, relative to the environment's spawn frame."""
    initial_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Initial linear velocity of the center of mass in m/s (world frame)."""

    settle_speed: float = 0.01
    """Speed (m/s) below which the object counts as at rest."""
    settle_angular_speed: float = 0.05
    """Angular speed (rad/s) below which the object counts as at rest."""
    settle_window: float = 0.25
    """Seconds the object must stay at rest at the end of the run to count as settled."""

    output_dir: str = f"{PROJECT_NAME}_output"
    plot: bool = True
    render: bool = False
    """Also write an animation of the run."""
    render_format: str = "gif"
    """gif (needs only Pillow) or mp4 (needs the 'video' extra)."""
    render_fps: int = 30
    render_size: tuple[int, int] = (480, 360)

    def __post_init__(self) -> None:
        # Normalize sequences coming from YAML lists.
        object.__setattr__(self, "initial_orientation", _vec3(self.initial_orientation, "initial_orientation"))
        object.__setattr__(self, "initial_velocity", _vec3(self.initial_velocity, "initial_velocity"))
        size = tuple(int(v) for v in self.render_size)
        if len(size) != 2 or min(size) <= 0:
            raise ValueError("render_size must be two positive integers [width, height]")
        object.__setattr__(self, "render_size", size)
        object.__setattr__(self, "env_params", dict(self.env_params or {}))
        self._validate()

    def _validate(self) -> None:
        positive = ["duration", "timestep", "scale", "density", "render_fps", "settle_window"]
        for name in positive:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be > 0, got {getattr(self, name)}")
        if self.mass is not None and self.mass <= 0:
            raise ValueError(f"mass must be > 0, got {self.mass}")
        non_negative = [
            "gravity", "friction", "linear_damping", "angular_damping", "settle_speed", "settle_angular_speed",
        ]
        for name in non_negative:
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0, got {getattr(self, name)}")
        if not 0.0 <= self.restitution <= 1.0:
            raise ValueError(f"restitution must be between 0 and 1, got {self.restitution}")
        if self.timestep > self.duration:
            raise ValueError("timestep must be smaller than duration")
        if self.render_format not in ("gif", "mp4"):
            raise ValueError(f"render_format must be 'gif' or 'mp4', got {self.render_format!r}")

    @classmethod
    def field_names(cls) -> set[str]:
        return {f.name for f in fields(cls)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SimConfig:
        unknown = set(data) - cls.field_names()
        if unknown:
            raise ValueError(
                f"Unknown config key(s): {', '.join(sorted(unknown))}. "
                f"Valid keys: {', '.join(sorted(cls.field_names()))}"
            )
        return cls(**data)

    @classmethod
    def from_yaml(cls, path: str | Path) -> SimConfig:
        path = Path(path)
        with path.open() as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a mapping of config keys at the top level")
        return cls.from_dict(data)

    @classmethod
    def load(cls, source: SimConfig | dict | str | Path | None = None) -> SimConfig:
        """Build a config from a SimConfig, a dict, a YAML path, or None (defaults)."""
        if source is None:
            return cls()
        if isinstance(source, SimConfig):
            return source
        if isinstance(source, dict):
            return cls.from_dict(source)
        return cls.from_yaml(source)

    def with_overrides(self, **overrides: Any) -> SimConfig:
        """Return a copy with the given fields replaced. ``None`` values are ignored.

        ``env_params`` is merged into the existing parameters rather than replacing them.
        """
        overrides = {k: v for k, v in overrides.items() if v is not None}
        unknown = set(overrides) - self.field_names()
        if unknown:
            raise ValueError(f"Unknown config key(s): {', '.join(sorted(unknown))}")
        if "env_params" in overrides:
            base = {} if overrides.get("env", self.env) != self.env else dict(self.env_params)
            base.update(overrides["env_params"])
            overrides["env_params"] = base
        elif "env" in overrides and overrides["env"] != self.env:
            overrides["env_params"] = {}
        return replace(self, **overrides)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("initial_orientation", "initial_velocity", "render_size"):
            data[key] = list(data[key])
        return data


def _vec3(value: Any, name: str) -> tuple[float, float, float]:
    try:
        vec = tuple(float(v) for v in value)
    except TypeError as exc:
        raise ValueError(f"{name} must be a list of 3 numbers") from exc
    if len(vec) != 3:
        raise ValueError(f"{name} must be a list of 3 numbers, got {len(vec)}")
    return vec  # type: ignore[return-value]
