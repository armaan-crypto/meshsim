"""Drop test: the object falls from a set height onto flat ground."""

from __future__ import annotations

import numpy as np

from .base import IDENTITY, Environment, Param, SpawnFrame, add_ground, require_non_negative, require_positive


class DropTest(Environment):
    name = "drop"
    description = "Free fall from `height` onto a flat floor at z=0."
    params = {
        "height": Param(1.0, "Gap between the object's lowest point and the floor at t=0, m"),
        "friction": Param(1.0, "Floor friction (multiplied with the object's friction)"),
        "restitution": Param(1.0, "Floor restitution (multiplied with the object's restitution)"),
    }

    def validate(self) -> None:
        require_positive(self, "height")
        require_non_negative(self, "friction", "restitution")

    def build(self, client) -> None:
        add_ground(client, self.friction, self.restitution)

    def spawn_frame(self, client) -> SpawnFrame:
        return SpawnFrame(origin=np.zeros(3), orientation=IDENTITY.copy(), gap=float(self.height))
