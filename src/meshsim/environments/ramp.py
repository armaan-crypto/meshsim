"""Inclined ramp that runs out onto flat ground."""

from __future__ import annotations

import numpy as np

from .._bullet import p
from .._rotation import quat_from_euler_deg
from .base import (
    SURFACE_RGBA,
    Environment,
    Param,
    SpawnFrame,
    add_ground,
    require_non_negative,
    require_positive,
    set_surface,
)


class Ramp(Environment):
    """A plank tilted by ``angle`` whose lower edge meets the ground at the origin.

    The slope rises toward -X, so an object sliding down moves toward +X and
    ends up on the ground beyond x=0.
    """

    name = "ramp"
    description = "Inclined plane whose bottom edge meets flat ground at x=0. Objects slide toward +X."
    params = {
        "angle": Param(20.0, "Incline angle from horizontal, degrees (0-89)"),
        "friction": Param(1.0, "Ramp friction (multiplied with the object's friction)"),
        "restitution": Param(1.0, "Ramp restitution (multiplied with the object's restitution)"),
        "length": Param(5.0, "Length of the ramp along the slope, m"),
        "width": Param(2.0, "Width of the ramp, m"),
        "start_distance": Param(4.0, "Starting point measured up the slope from the bottom edge, m"),
        "clearance": Param(0.001, "Starting gap between the object and the ramp surface, m"),
        "ground_friction": Param(1.0, "Friction of the run-out ground"),
    }

    thickness = 0.1

    def validate(self) -> None:
        if not 0 <= self.angle < 90:
            raise ValueError(f"ramp: angle must be in [0, 90), got {self.angle}")
        require_positive(self, "length", "width")
        require_non_negative(self, "friction", "restitution", "clearance", "start_distance", "ground_friction")
        if self.start_distance > self.length:
            raise ValueError("ramp: start_distance must not exceed length")

    @property
    def _theta(self) -> float:
        return float(np.radians(self.angle))

    @property
    def up_slope(self) -> np.ndarray:
        t = self._theta
        return np.array([-np.cos(t), 0.0, np.sin(t)])

    @property
    def normal(self) -> np.ndarray:
        t = self._theta
        return np.array([np.sin(t), 0.0, np.cos(t)])

    @property
    def orientation(self) -> np.ndarray:
        # Rotating about +Y by theta maps +Z onto the ramp normal.
        return quat_from_euler_deg([0.0, self.angle, 0.0])

    def build(self, client) -> None:
        add_ground(client, self.ground_friction, self.restitution)
        half = [self.length / 2, self.width / 2, self.thickness / 2]
        center = self.up_slope * self.length / 2 - self.normal * self.thickness / 2
        collision = client.createCollisionShape(p.GEOM_BOX, halfExtents=half)
        visual = client.createVisualShape(p.GEOM_BOX, halfExtents=half, rgbaColor=SURFACE_RGBA)
        body = client.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=collision,
            baseVisualShapeIndex=visual,
            basePosition=center.tolist(),
            baseOrientation=self.orientation.tolist(),
        )
        set_surface(client, body, self.friction, self.restitution)

    def spawn_frame(self, client) -> SpawnFrame:
        return SpawnFrame(
            origin=self.up_slope * self.start_distance,
            orientation=self.orientation,
            gap=float(self.clearance),
        )
